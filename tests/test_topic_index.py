import json
from pathlib import Path

from media_to_wiki_convertor.topic_index import (
    build_topic_index,
    count_topic_index_pages,
    normalize_index_key,
    read_knowledge_payloads,
    slugify_key,
    write_topic_index,
)


def sample_knowledge(
    video_id: str = "video1",
    chunk_id: str = "0001",
    topic_name: str = "Daily standup",
    wiki_title: str = "Daily / Standup",
) -> dict:
    return {
        "source": {
            "video_id": video_id,
            "chunk_id": chunk_id,
            "start": "00:00:00",
            "end": "00:10:00",
        },
        "chunk_title": "Daily intro",
        "detected_domain": "Scrum",
        "confidence": "high",
        "why_low_confidence": "",
        "summary": "Daily помогает команде синхронизироваться.",
        "topics": [
            {
                "name": topic_name,
                "description": "Ежедневная встреча команды.",
                "evidence": "дейли очень важный звонок",
            }
        ],
        "practices": [
            {
                "title": "Делать daily коротким",
                "claim": "Daily должен быть коротким.",
                "why_it_matters": "Команда не тратит лишнее время.",
                "action_items": ["Держать фокус"],
                "evidence": "короткий звонок",
            }
        ],
        "mistakes": [
            {
                "title": "Затягивать daily",
                "description": "Daily превращается в длинный созвон.",
                "correction": "Выносить детали отдельно.",
                "evidence": "не растягивать",
            }
        ],
        "terms": [
            {
                "term": "Daily",
                "definition": "Ежедневный короткий командный звонок.",
                "evidence": "daily",
            }
        ],
        "questions": [
            {
                "question": "Зачем нужен daily?",
                "answer": "Для синхронизации и выявления проблем.",
                "evidence": "какие у кого проблемы",
            }
        ],
        "wiki_candidates": [
            {
                "title": wiki_title,
                "reason": "Отдельная важная Scrum-практика.",
                "suggested_section": "Scrum",
            }
        ],
        "notable_quotes": [],
    }


def test_normalize_index_key_unifies_case_spacing_and_separators() -> None:
    assert normalize_index_key("  Daily / Standup  ") == "daily standup"
    assert normalize_index_key("Daily—Standup!") == "daily standup"


def test_slugify_key_preserves_readable_ascii_words() -> None:
    assert slugify_key("Daily / Standup") == "daily-standup"
    assert slugify_key("Технический долг") == "технический-долг"


def test_build_topic_index_aggregates_topics_terms_and_pages() -> None:
    payloads = [
        sample_knowledge(video_id="video1", chunk_id="0001"),
        sample_knowledge(
            video_id="video2",
            chunk_id="0003",
            topic_name="daily standup",
            wiki_title="Daily Standup",
        ),
    ]

    index = build_topic_index(payloads)

    assert index["summary"]["knowledge_files"] == 2
    assert index["domains"][0]["name"] == "Scrum"
    assert index["domains"][0]["count"] == 2
    assert index["topics"][0]["key"] == "daily standup"
    assert index["topics"][0]["count"] == 2
    assert index["terms"][0]["key"] == "daily"
    assert index["wiki_candidates"][0]["key"] == "daily standup"
    assert index["pages"][0]["title"] == "Daily Standup"
    assert index["pages"][0]["source_count"] == 2
    assert index["pages"][0]["sources"] == [
        {"video_id": "video1", "chunk_id": "0001", "start": "00:00:00", "end": "00:10:00"},
        {"video_id": "video2", "chunk_id": "0003", "start": "00:00:00", "end": "00:10:00"},
    ]


def test_read_knowledge_payloads_reads_nested_json_files(tmp_path: Path) -> None:
    first = tmp_path / "extracted_knowledge" / "video1" / "0001.json"
    second = tmp_path / "extracted_knowledge" / "video2" / "0001.json"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text(json.dumps(sample_knowledge(video_id="video1")), encoding="utf-8")
    second.write_text(json.dumps(sample_knowledge(video_id="video2")), encoding="utf-8")

    payloads = read_knowledge_payloads(tmp_path)

    assert [payload["source"]["video_id"] for payload in payloads] == ["video1", "video2"]


def test_write_topic_index_writes_summary_files_and_page_files(tmp_path: Path) -> None:
    index = build_topic_index([sample_knowledge()])

    output_dir = write_topic_index(tmp_path, index)

    assert output_dir == tmp_path / "topic_index"
    assert (output_dir / "topics.json").exists()
    assert (output_dir / "terms.json").exists()
    assert (output_dir / "wiki_candidates.json").exists()
    assert (output_dir / "pages.json").exists()
    assert (output_dir / "pages" / "daily-standup.json").exists()
    assert count_topic_index_pages(tmp_path) == 1


def test_count_topic_index_pages_prefers_pages_json_over_stale_files(tmp_path: Path) -> None:
    pages_dir = tmp_path / "topic_index" / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "stale-a.json").write_text("{}", encoding="utf-8")
    (pages_dir / "stale-b.json").write_text("{}", encoding="utf-8")
    (tmp_path / "topic_index" / "pages.json").write_text(
        json.dumps([{"title": "Fresh"}]),
        encoding="utf-8",
    )

    assert count_topic_index_pages(tmp_path) == 1
