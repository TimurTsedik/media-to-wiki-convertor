from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_catalog_categories(raw_data: Path) -> list[dict[str, Any]]:
    return read_json_list(raw_data / "catalog" / "categories.json")


def build_course_plan(catalog_categories: list[dict[str, Any]]) -> dict[str, Any]:
    chapters = [chapter_from_category(category) for category in catalog_categories]
    return {
        "summary": {
            "chapters": len(chapters),
            "articles": sum(int(chapter["article_count"]) for chapter in chapters),
            "topics": sum(int(chapter["topic_count"]) for chapter in chapters),
            "sources": sum(int(chapter["source_count"]) for chapter in chapters),
        },
        "chapters": chapters,
    }


def chapter_from_category(category: dict[str, Any]) -> dict[str, Any]:
    articles = [
        compact_article(article)
        for article in category.get("articles", [])
        if isinstance(article, dict)
    ]
    topics = [
        compact_topic(topic)
        for topic in category.get("topics", [])
        if isinstance(topic, dict)
    ]
    return {
        "key": str(category.get("key", "")).strip() or "untitled",
        "title": str(category.get("title", "")).strip() or "Untitled",
        "article_count": len(articles),
        "topic_count": len(topics),
        "source_count": int(category.get("source_count") or source_count(articles, topics)),
        "articles": articles,
        "topics": topics,
    }


def compact_article(article: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(article.get("title", "")).strip() or "Untitled",
        "slug": str(article.get("slug", "")).strip(),
        "source_count": int(article.get("source_count") or 0),
        "count": int(article.get("count") or 0),
    }


def compact_topic(topic: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "title": str(topic.get("title", "")).strip() or "Untitled",
        "source_count": int(topic.get("source_count") or 0),
        "count": int(topic.get("count") or 0),
    }
    sources = compact_sources(topic)
    if sources:
        compact["sources"] = sources
    return compact


def compact_sources(item: dict[str, Any]) -> list[dict[str, str]]:
    compact: list[dict[str, str]] = []
    sources = item.get("sources", [])
    if not isinstance(sources, list):
        return compact
    for source in sources:
        if not isinstance(source, dict):
            continue
        video_id = str(source.get("video_id", "")).strip()
        chunk_id = str(source.get("chunk_id", "")).strip()
        if not video_id or not chunk_id:
            continue
        row = {"video_id": video_id, "chunk_id": chunk_id}
        start = str(source.get("start", "")).strip()
        end = str(source.get("end", "")).strip()
        if start:
            row["start"] = start
        if end:
            row["end"] = end
        compact.append(row)
    return compact


def source_count(articles: list[dict[str, Any]], topics: list[dict[str, Any]]) -> int:
    return sum(int(item.get("source_count") or 0) for item in [*articles, *topics])


def write_course_plan(raw_data: Path, plan: dict[str, Any]) -> Path:
    output_dir = raw_data / "course_plan"
    source_packs_dir = output_dir / "source_packs"
    source_packs_dir.mkdir(parents=True, exist_ok=True)

    for stale_path in source_packs_dir.glob("*.json"):
        stale_path.unlink()

    write_json(output_dir / "summary.json", plan["summary"])
    write_json(output_dir / "chapters.json", plan["chapters"])
    for chapter in plan["chapters"]:
        write_json(source_packs_dir / f"{chapter['key']}.json", build_source_pack(raw_data, chapter))
    return output_dir


def build_source_pack(raw_data: Path, chapter: dict[str, Any]) -> dict[str, Any]:
    return {
        "chapter": {
            "key": chapter["key"],
            "title": chapter["title"],
            "article_count": chapter["article_count"],
            "topic_count": chapter["topic_count"],
            "source_count": chapter["source_count"],
        },
        "articles": chapter.get("articles", []),
        "topics": [topic_with_source_text(raw_data, topic) for topic in chapter.get("topics", [])],
    }


def topic_with_source_text(raw_data: Path, topic: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(topic)
    enriched["sources"] = [
        source_with_chunk_text(raw_data, source)
        for source in topic.get("sources", [])
        if isinstance(source, dict)
    ]
    return enriched


def source_with_chunk_text(raw_data: Path, source: dict[str, Any]) -> dict[str, str]:
    row = {key: str(value) for key, value in source.items()}
    video_id = row.get("video_id", "")
    chunk_id = row.get("chunk_id", "")
    chunk = read_json_object(raw_data / "chunks" / video_id / f"{chunk_id}.json")
    row["chunk_text"] = str(chunk.get("text", ""))
    row["start"] = row.get("start") or str(chunk.get("start_hms", ""))
    row["end"] = row.get("end") or str(chunk.get("end_hms", ""))
    return row


def count_course_plan_chapters(raw_data: Path) -> int:
    return len(read_json_list(raw_data / "course_plan" / "chapters.json"))


def read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected JSON list: {path}")
    return payload


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
