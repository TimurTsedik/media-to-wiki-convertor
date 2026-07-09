import json
from pathlib import Path

from media_to_wiki_convertor.article_plan import (
    build_article_plan,
    build_source_pack,
    canonical_article_key,
    count_article_plan_pages,
    read_topic_pages,
    write_article_plan,
)


def make_page(
    title: str,
    video_id: str,
    chunk_id: str,
    source_count: int = 1,
    count: int = 1,
) -> dict:
    return {
        "key": title.casefold(),
        "slug": title.casefold().replace(" ", "-"),
        "title": title,
        "variants": [title],
        "count": count,
        "source_count": source_count,
        "suggested_sections": ["Scrum"],
        "domains": ["Scrum"],
        "sources": [
            {"video_id": video_id, "chunk_id": chunk_id, "start": "00:00:00", "end": "00:10:00"}
        ],
        "items": [{"title": title, "source": {"video_id": video_id, "chunk_id": chunk_id}}],
    }


def test_canonical_article_key_groups_parenthetical_acronym() -> None:
    assert canonical_article_key("Spec Driven Development (SDD)") == "spec driven development"
    assert canonical_article_key("Daily / Standup") == "daily standup"


def test_build_article_plan_merges_aliases_and_filters_by_source_count() -> None:
    pages = [
        make_page("Spec Driven Development", "a", "0001", source_count=1),
        make_page("Spec Driven Development (SDD)", "b", "0001", source_count=1),
        make_page("Singleton Topic", "c", "0001", source_count=1),
    ]

    plan = build_article_plan(pages, min_sources=2)

    assert plan["summary"]["topic_pages"] == 3
    assert plan["summary"]["article_pages"] == 1
    assert plan["pages"][0]["title"] == "Spec Driven Development"
    assert plan["pages"][0]["aliases"] == ["Spec Driven Development (SDD)"]
    assert plan["pages"][0]["source_count"] == 2
    assert plan["pages"][0]["tier"] == "supporting"
    assert plan["deferred"][0]["title"] == "Singleton Topic"


def test_read_topic_pages_loads_pages_json(tmp_path: Path) -> None:
    path = tmp_path / "topic_index" / "pages.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps([make_page("Daily", "a", "0001")]), encoding="utf-8")

    pages = read_topic_pages(tmp_path)

    assert pages[0]["title"] == "Daily"


def test_build_source_pack_includes_knowledge_and_chunk_text(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "extracted_knowledge" / "a" / "0001.json"
    chunk_path = tmp_path / "chunks" / "a" / "0001.json"
    knowledge_path.parent.mkdir(parents=True)
    chunk_path.parent.mkdir(parents=True)
    knowledge_path.write_text(
        json.dumps(
            {
                "source": {"video_id": "a", "chunk_id": "0001", "start": "00:00:00", "end": "00:10:00"},
                "chunk_title": "Daily intro",
                "summary": "Daily помогает синхронизации.",
                "topics": [{"name": "Daily", "description": "Meeting", "evidence": "daily"}],
                "practices": [],
                "mistakes": [],
                "terms": [],
                "questions": [],
                "wiki_candidates": [],
            }
        ),
        encoding="utf-8",
    )
    chunk_path.write_text(json.dumps({"text": "Полный текст чанка."}), encoding="utf-8")
    article = {
        "title": "Daily",
        "slug": "daily",
        "sources": [{"video_id": "a", "chunk_id": "0001", "start": "00:00:00", "end": "00:10:00"}],
    }

    pack = build_source_pack(tmp_path, article)

    assert pack["article"]["title"] == "Daily"
    assert pack["sources"][0]["chunk_text"] == "Полный текст чанка."
    assert pack["sources"][0]["knowledge"]["summary"] == "Daily помогает синхронизации."


def test_write_article_plan_writes_pages_aliases_and_source_packs(tmp_path: Path) -> None:
    article = {
        "title": "Daily",
        "slug": "daily",
        "aliases": ["Daily standup"],
        "sources": [{"video_id": "a", "chunk_id": "0001", "start": "00:00:00", "end": "00:10:00"}],
    }
    knowledge_path = tmp_path / "extracted_knowledge" / "a" / "0001.json"
    chunk_path = tmp_path / "chunks" / "a" / "0001.json"
    knowledge_path.parent.mkdir(parents=True)
    chunk_path.parent.mkdir(parents=True)
    knowledge_path.write_text(json.dumps({"summary": "ok"}), encoding="utf-8")
    chunk_path.write_text(json.dumps({"text": "text"}), encoding="utf-8")
    plan = {"summary": {"article_pages": 1}, "pages": [article], "deferred": []}

    output_dir = write_article_plan(tmp_path, plan)

    assert output_dir == tmp_path / "article_plan"
    assert (output_dir / "pages.json").exists()
    assert (output_dir / "aliases.json").exists()
    assert (output_dir / "source_packs" / "daily.json").exists()
    assert count_article_plan_pages(tmp_path) == 1
