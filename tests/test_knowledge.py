import json
from pathlib import Path
from urllib import error, request
from io import BytesIO

from media_to_wiki_convertor.knowledge import (
    AnthropicKnowledgeClient,
    GeminiKnowledgeClient,
    KNOWLEDGE_SCHEMA,
    OpenAIKnowledgeClient,
    build_extraction_prompt,
    chunk_payloads,
    count_existing_knowledge,
    default_transport,
    knowledge_output_path,
    select_chunk_payloads,
    validate_api_key,
)


def sample_chunk() -> dict:
    return {
        "video_id": "abc123",
        "title": "Recording 2026",
        "source_path": "/videos/recording.mp4",
        "chunk_id": "0001",
        "start_hms": "00:00:00",
        "end_hms": "00:10:00",
        "text": "В этом фрагменте обсуждают, как писать CV через impact и метрики.",
    }


def test_build_extraction_prompt_treats_video_title_as_unreliable_metadata() -> None:
    prompt = build_extraction_prompt(sample_chunk(), output_language="en")

    assert "Название видео может быть техническим" in prompt
    assert "Не используй название видео для вывода тем" in prompt
    assert "write extracted knowledge in en" in prompt
    assert "VIDEO_ID: abc123" in prompt
    assert "CHUNK_ID: 0001" in prompt
    assert "TRANSCRIPT:" in prompt
    assert "как писать CV через impact" in prompt


def test_knowledge_schema_requires_source_and_core_fields() -> None:
    properties = KNOWLEDGE_SCHEMA["schema"]["properties"]

    assert "chunk_title" in properties
    assert "detected_domain" in properties
    assert "practices" in properties
    assert "wiki_candidates" in properties
    assert "source" in properties
    assert KNOWLEDGE_SCHEMA["schema"]["required"] == [
        "source",
        "chunk_title",
        "detected_domain",
        "confidence",
        "why_low_confidence",
        "summary",
        "topics",
        "practices",
        "mistakes",
        "terms",
        "questions",
        "wiki_candidates",
        "notable_quotes",
    ]


def test_openai_client_builds_responses_api_request_with_json_schema() -> None:
    requests: list[dict] = []

    def fake_transport(url: str, headers: dict[str, str], payload: dict) -> dict:
        requests.append({"url": url, "headers": headers, "payload": payload})
        return {"output_text": json.dumps({"ok": True})}

    client = OpenAIKnowledgeClient(
        api_key="secret",
        model="gpt-5.4-mini",
        output_language="en",
        transport=fake_transport,
    )

    result = client.extract(sample_chunk())

    assert result == {"ok": True}
    request = requests[0]
    assert request["url"] == "https://api.openai.com/v1/responses"
    assert request["headers"]["Authorization"] == "Bearer secret"
    assert request["payload"]["model"] == "gpt-5.4-mini"
    assert request["payload"]["text"]["format"] == KNOWLEDGE_SCHEMA
    assert request["payload"]["input"][0]["role"] == "system"
    assert "языке: en" in request["payload"]["input"][0]["content"]
    assert request["payload"]["input"][1]["role"] == "user"
    assert "output_language: write extracted knowledge in en" in request["payload"]["input"][1][
        "content"
    ]


def test_openai_client_strips_api_key_whitespace() -> None:
    requests: list[dict] = []

    def fake_transport(url: str, headers: dict[str, str], payload: dict) -> dict:
        requests.append({"headers": headers})
        return {"output_text": json.dumps({"ok": True})}

    client = OpenAIKnowledgeClient(
        api_key=" secret\n",
        model="gpt-5.4-mini",
        transport=fake_transport,
    )

    client.extract(sample_chunk())

    assert requests[0]["headers"]["Authorization"] == "Bearer secret"


def test_openai_client_rejects_placeholder_api_key() -> None:
    try:
        OpenAIKnowledgeClient(api_key="placeholder-api-key", model="gpt-5.4-mini")
    except RuntimeError as exc:
        assert "OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("placeholder OPENAI_API_KEY was accepted")


def test_validate_api_key_error_is_provider_generic() -> None:
    try:
        validate_api_key("пример-key", api_key_env="GEMINI_API_KEY", provider="gemini")
    except RuntimeError as exc:
        message = str(exc)
        assert "GEMINI_API_KEY" in message
        assert "gemini" in message
        assert "OpenAI API key" not in message
    else:
        raise AssertionError("non-ASCII Gemini API key was accepted")


def test_default_transport_error_messages_are_provider_generic(monkeypatch) -> None:
    def raise_http_error(*args, **kwargs):
        raise error.HTTPError(
            url="https://api.example.test",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=BytesIO(b'{"error":"bad key"}'),
        )

    monkeypatch.setattr("media_to_wiki_convertor.knowledge.request.urlopen", raise_http_error)

    try:
        default_transport("https://api.example.test", {}, {})
    except RuntimeError as exc:
        message = str(exc)
        assert "LLM provider API error 401" in message
        assert "OpenAI" not in message
        assert "OPENAI_API_KEY" not in message
    else:
        raise AssertionError("HTTPError was not converted to RuntimeError")


def test_default_transport_value_errors_are_provider_generic(monkeypatch) -> None:
    def raise_value_error(*args, **kwargs):
        raise ValueError("bad request")

    monkeypatch.setattr("media_to_wiki_convertor.knowledge.request.urlopen", raise_value_error)

    try:
        default_transport("https://api.example.test", {}, {})
    except RuntimeError as exc:
        message = str(exc)
        assert "Invalid LLM provider request" in message
        assert "OpenAI" not in message
        assert "OPENAI_API_KEY" not in message
    else:
        raise AssertionError("ValueError was not converted to RuntimeError")


def test_default_transport_retries_transient_url_errors(monkeypatch) -> None:
    attempts = 0

    def flaky_urlopen(req: request.Request, timeout: int):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise error.URLError("temporary outage")

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self) -> bytes:
                return b'{"ok": true}'

        return Response()

    monkeypatch.setattr("media_to_wiki_convertor.knowledge.request.urlopen", flaky_urlopen)
    monkeypatch.setattr("media_to_wiki_convertor.knowledge.time.sleep", lambda seconds: None)

    assert default_transport("https://api.example.test", {}, {}) == {"ok": True}
    assert attempts == 2


def test_anthropic_and_gemini_knowledge_clients_name_provider_api_key_envs() -> None:
    cases = [
        (AnthropicKnowledgeClient, "ANTHROPIC_API_KEY", "anthropic"),
        (GeminiKnowledgeClient, "GEMINI_API_KEY", "gemini"),
    ]
    for client_cls, api_key_env, provider in cases:
        try:
            client_cls(api_key="placeholder-api-key", model="model-test")
        except RuntimeError as exc:
            message = str(exc)
            assert api_key_env in message
            assert provider in message
            assert "OpenAI API key" not in message
        else:
            raise AssertionError(f"placeholder {api_key_env} was accepted")


def test_anthropic_knowledge_client_builds_messages_request_and_parses_json() -> None:
    requests: list[dict] = []

    def fake_transport(url: str, headers: dict[str, str], payload: dict) -> dict:
        requests.append({"url": url, "headers": headers, "payload": payload})
        return {"content": [{"type": "text", "text": json.dumps({"ok": True})}]}

    client = AnthropicKnowledgeClient(
        api_key="anthropic-secret",
        model="claude-test",
        output_language="en",
        transport=fake_transport,
    )

    result = client.extract(sample_chunk())

    assert result == {"ok": True}
    request = requests[0]
    assert request["url"] == "https://api.anthropic.com/v1/messages"
    assert request["headers"] == {
        "x-api-key": "anthropic-secret",
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    assert request["payload"]["model"] == "claude-test"
    assert request["payload"]["max_tokens"] > 0
    assert "языке: en" in request["payload"]["system"]
    assert request["payload"]["messages"][0]["role"] == "user"
    assert "output_language: write extracted knowledge in en" in request["payload"]["messages"][0][
        "content"
    ]


def test_gemini_knowledge_client_builds_generate_content_request_and_parses_json() -> None:
    requests: list[dict] = []

    def fake_transport(url: str, headers: dict[str, str], payload: dict) -> dict:
        requests.append({"url": url, "headers": headers, "payload": payload})
        return {
            "candidates": [
                {"content": {"parts": [{"text": json.dumps({"ok": True})}]}}
            ]
        }

    client = GeminiKnowledgeClient(
        api_key="gemini-secret",
        model="gemini-test",
        output_language="en",
        transport=fake_transport,
    )

    result = client.extract(sample_chunk())

    assert result == {"ok": True}
    request = requests[0]
    assert request["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
        "?key=gemini-secret"
    )
    assert request["headers"] == {"Content-Type": "application/json"}
    assert request["payload"]["contents"][0]["role"] == "user"
    text = request["payload"]["contents"][0]["parts"][0]["text"]
    assert "языке: en" in text
    assert "output_language: write extracted knowledge in en" in text


def test_chunk_payloads_iterates_chunk_json_files(tmp_path: Path) -> None:
    chunk_dir = tmp_path / "chunks" / "abc123"
    chunk_dir.mkdir(parents=True)
    (chunk_dir / "0002.json").write_text(json.dumps({**sample_chunk(), "chunk_id": "0002"}), encoding="utf-8")
    (chunk_dir / "0001.json").write_text(json.dumps(sample_chunk()), encoding="utf-8")

    payloads = list(chunk_payloads(tmp_path))

    assert [payload["chunk_id"] for payload in payloads] == ["0001", "0002"]


def test_select_chunk_payloads_can_take_sample_per_video() -> None:
    payloads = [
        {"video_id": "a", "chunk_id": "0001"},
        {"video_id": "a", "chunk_id": "0002"},
        {"video_id": "a", "chunk_id": "0003"},
        {"video_id": "b", "chunk_id": "0001"},
        {"video_id": "b", "chunk_id": "0002"},
    ]

    selected = select_chunk_payloads(payloads, limit=None, sample_per_video=2)

    assert selected == [
        {"video_id": "a", "chunk_id": "0001"},
        {"video_id": "a", "chunk_id": "0002"},
        {"video_id": "b", "chunk_id": "0001"},
        {"video_id": "b", "chunk_id": "0002"},
    ]


def test_select_chunk_payloads_applies_limit_after_sample_per_video() -> None:
    payloads = [
        {"video_id": "a", "chunk_id": "0001"},
        {"video_id": "a", "chunk_id": "0002"},
        {"video_id": "b", "chunk_id": "0001"},
        {"video_id": "b", "chunk_id": "0002"},
    ]

    selected = select_chunk_payloads(payloads, limit=3, sample_per_video=2)

    assert selected == [
        {"video_id": "a", "chunk_id": "0001"},
        {"video_id": "a", "chunk_id": "0002"},
        {"video_id": "b", "chunk_id": "0001"},
    ]


def test_knowledge_output_path_uses_video_and_chunk_id(tmp_path: Path) -> None:
    assert knowledge_output_path(tmp_path, "abc123", "0001") == (
        tmp_path / "extracted_knowledge" / "abc123" / "0001.json"
    )


def test_count_existing_knowledge_counts_json_files(tmp_path: Path) -> None:
    path = tmp_path / "extracted_knowledge" / "abc123" / "0001.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    (path.parent / "notes.md").write_text("not counted", encoding="utf-8")

    assert count_existing_knowledge(tmp_path) == 1
