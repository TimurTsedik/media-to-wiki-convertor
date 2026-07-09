import json
from pathlib import Path

from media_to_wiki_convertor.draft_articles import (
    OpenAIArticleClient,
    build_article_prompt,
    count_draft_articles,
    draft_article,
    draft_output_path,
    read_article_pages,
    select_source_packs,
)


def sample_source_pack() -> dict:
    return {
        "article": {
            "title": "Daily / Standup",
            "slug": "daily-standup",
            "aliases": ["Daily standup"],
            "tier": "supporting",
            "domains": ["Scrum"],
            "suggested_sections": ["Scrum"],
        },
        "sources": [
            {
                "source": {
                    "video_id": "abc123",
                    "chunk_id": "0001",
                    "start": "00:00:00",
                    "end": "00:10:00",
                },
                "knowledge": {
                    "chunk_title": "Введение в daily",
                    "summary": "Daily помогает синхронизации команды.",
                    "practices": [
                        {
                            "title": "Делать daily коротким",
                            "claim": "Daily должен быть коротким.",
                            "why_it_matters": "Так команда не тратит лишнее время.",
                            "action_items": ["Выносить детали после звонка"],
                            "evidence": "короткий звонок",
                        }
                    ],
                    "mistakes": [],
                    "terms": [],
                    "questions": [],
                },
                "chunk_text": "Это должен быть очень короткий звонок.",
            }
        ],
    }


def test_build_article_prompt_is_source_bound_and_names_known_links() -> None:
    prompt = build_article_prompt(
        sample_source_pack(),
        known_titles=["Daily / Standup", "Sprint planning"],
    )

    assert "Используй только SOURCE_PACK" in prompt
    assert "Daily / Standup" in prompt
    assert "KNOWN_ARTICLE_TITLES" in prompt
    assert "[[Sprint planning]]" in prompt
    assert "## Источники" in prompt
    assert "abc123" in prompt


def test_openai_article_client_builds_responses_request_and_returns_markdown() -> None:
    requests: list[dict] = []

    def fake_transport(url: str, headers: dict[str, str], payload: dict) -> dict:
        requests.append({"url": url, "headers": headers, "payload": payload})
        return {"output_text": "# Daily / Standup\n\n## Коротко\nТекст."}

    client = OpenAIArticleClient(
        api_key="secret",
        model="gpt-5.4-mini",
        transport=fake_transport,
    )

    markdown = client.draft(sample_source_pack(), known_titles=["Daily / Standup"])

    assert markdown.startswith("# Daily / Standup")
    request = requests[0]
    assert request["url"] == "https://api.openai.com/v1/responses"
    assert request["headers"]["Authorization"] == "Bearer secret"
    assert request["payload"]["model"] == "gpt-5.4-mini"
    assert request["payload"]["input"][0]["role"] == "system"
    assert request["payload"]["input"][1]["role"] == "user"


def test_openai_article_client_strips_api_key_whitespace() -> None:
    requests: list[dict] = []

    def fake_transport(url: str, headers: dict[str, str], payload: dict) -> dict:
        requests.append({"headers": headers})
        return {"output_text": "# Daily / Standup\n\nТекст."}

    client = OpenAIArticleClient(
        api_key=" secret\n",
        model="gpt-5.4-mini",
        transport=fake_transport,
    )

    client.draft(sample_source_pack(), known_titles=["Daily / Standup"])

    assert requests[0]["headers"]["Authorization"] == "Bearer secret"


def test_openai_article_client_rejects_placeholder_api_key() -> None:
    try:
        OpenAIArticleClient(api_key="placeholder-api-key", model="gpt-5.4-mini")
    except RuntimeError as exc:
        assert "OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("placeholder OPENAI_API_KEY was accepted")


def test_read_article_pages_loads_pages_json(tmp_path: Path) -> None:
    path = tmp_path / "article_plan" / "pages.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps([{"title": "Daily / Standup", "slug": "daily-standup"}]),
        encoding="utf-8",
    )

    assert read_article_pages(tmp_path) == [{"title": "Daily / Standup", "slug": "daily-standup"}]


def test_select_source_packs_follows_article_page_order_and_limit(tmp_path: Path) -> None:
    source_packs_dir = tmp_path / "article_plan" / "source_packs"
    source_packs_dir.mkdir(parents=True)
    for slug in ["b", "a"]:
        (source_packs_dir / f"{slug}.json").write_text(
            json.dumps({"article": {"slug": slug}}),
            encoding="utf-8",
        )
    pages = [{"slug": "b", "title": "B"}, {"slug": "a", "title": "A"}]

    selected = select_source_packs(tmp_path, pages, limit=1)

    assert [pack["article"]["slug"] for pack in selected] == ["b"]


def test_draft_output_path_uses_article_slug(tmp_path: Path) -> None:
    assert draft_output_path(tmp_path, "daily-standup") == tmp_path / "draft_articles" / "daily-standup.md"


def test_draft_article_writes_markdown_and_skips_existing(tmp_path: Path) -> None:
    calls = 0

    class FakeClient:
        def draft(self, source_pack: dict, known_titles: list[str]) -> str:
            nonlocal calls
            calls += 1
            return "# Daily / Standup\n\nТекст."

    result = draft_article(
        tmp_path,
        sample_source_pack(),
        FakeClient(),
        known_titles=["Daily / Standup"],
    )
    second = draft_article(
        tmp_path,
        sample_source_pack(),
        FakeClient(),
        known_titles=["Daily / Standup"],
    )

    assert result.skipped is False
    assert second.skipped is True
    assert calls == 1
    assert result.output_path.read_text(encoding="utf-8").startswith("# Daily / Standup")
    assert count_draft_articles(tmp_path) == 1
