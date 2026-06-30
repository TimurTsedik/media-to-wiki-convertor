import json
from pathlib import Path

from larchenko_kb.knowledge import (
    KNOWLEDGE_SCHEMA,
    OpenAIKnowledgeClient,
    build_extraction_prompt,
    chunk_payloads,
    count_existing_knowledge,
    knowledge_output_path,
    select_chunk_payloads,
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
    prompt = build_extraction_prompt(sample_chunk())

    assert "Название видео может быть техническим" in prompt
    assert "Не используй название видео для вывода тем" in prompt
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
    assert request["payload"]["input"][1]["role"] == "user"


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
