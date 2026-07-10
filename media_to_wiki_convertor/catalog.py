from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from typing import Any

from media_to_wiki_convertor.topic_index import normalize_index_key, slugify_key


UNCATEGORIZED = "Uncategorized"
WEAK_TITLE_TOKENS = {
    "and",
    "for",
    "the",
    "with",
    "from",
    "into",
    "overview",
    "intro",
    "introduction",
    "basic",
    "basics",
    "advanced",
    "skill",
    "skills",
    "pattern",
    "patterns",
    "practice",
    "practices",
}
DOMAIN_ACRONYMS = {
    "ai": "AI",
    "api": "API",
    "aws": "AWS",
    "ci": "CI",
    "cd": "CD",
    "cv": "CV",
    "devops": "DevOps",
    "llm": "LLM",
    "ml": "ML",
    "mvp": "MVP",
    "qa": "QA",
    "rag": "RAG",
    "sdd": "SDD",
    "sql": "SQL",
    "ui": "UI",
    "ux": "UX",
}


def read_article_plan_pages(raw_data: Path) -> list[dict[str, Any]]:
    return read_json_list(raw_data / "article_plan" / "pages.json")


def read_deferred_topics(raw_data: Path) -> list[dict[str, Any]]:
    return read_json_list(raw_data / "article_plan" / "deferred.json")


def build_catalog(
    pages: list[dict[str, Any]],
    deferred: list[dict[str, Any]],
) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    article_categories: dict[str, list[dict[str, Any]]] = defaultdict(list)
    topic_categories: dict[str, str] = {}

    for page in pages:
        category = category_for_item(page)
        category_row = grouped.setdefault(category["key"], empty_category(category))
        article = compact_article(page)
        category_row["articles"].append(article)
        article_categories[category["key"]].append(article)

    for topic in deferred:
        category = category_for_item(topic)
        category_row = grouped.setdefault(category["key"], empty_category(category))
        compact_topic = compact_catalog_topic(topic)
        category_row["topics"].append(compact_topic)
        topic_categories[str(topic.get("title", ""))] = category["title"]

    categories = finalize_categories(list(grouped.values()))
    merge_suggestions, orphan_topics = build_merge_suggestions(
        deferred,
        article_categories,
        topic_categories,
    )

    return {
        "summary": {
            "categories": len(categories),
            "articles": len(pages),
            "deferred_topics": len(deferred),
            "merge_suggestions": len(merge_suggestions),
            "orphan_topics": len(orphan_topics),
        },
        "categories": categories,
        "merge_suggestions": merge_suggestions,
        "orphan_topics": orphan_topics,
    }


def category_for_item(item: dict[str, Any]) -> dict[str, str]:
    label = first_non_empty(item.get("domains", []))
    if not label:
        label = first_item_domain(item)
    if not label:
        label = first_non_empty(item.get("suggested_sections", []))
    if not label:
        label = UNCATEGORIZED
    title = normalize_category_title(label)
    return {"key": slugify_key(title), "title": title}


def first_item_domain(item: dict[str, Any]) -> str:
    for child in item.get("items", []):
        if not isinstance(child, dict):
            continue
        domain = str(child.get("domain", "")).strip()
        if domain:
            return domain
        domains = child.get("domains", [])
        value = first_non_empty(domains)
        if value:
            return value
    return ""


def first_non_empty(values: Any) -> str:
    if isinstance(values, str):
        return values.strip()
    try:
        for value in values:
            text = str(value).strip()
            if text:
                return text
    except TypeError:
        return ""
    return ""


def normalize_category_title(value: str) -> str:
    key = normalize_index_key(value)
    if not key:
        return UNCATEGORIZED
    if key == normalize_index_key(UNCATEGORIZED):
        return UNCATEGORIZED
    return " ".join(DOMAIN_ACRONYMS.get(part, part.capitalize()) for part in key.split())


def empty_category(category: dict[str, str]) -> dict[str, Any]:
    return {
        "key": category["key"],
        "title": category["title"],
        "article_count": 0,
        "deferred_count": 0,
        "source_count": 0,
        "articles": [],
        "topics": [],
    }


def compact_article(page: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(page.get("title", "")).strip() or "Untitled",
        "slug": str(page.get("slug", "")).strip() or slugify_key(str(page.get("title", ""))),
        "source_count": item_source_count(page),
        "count": item_count(page),
    }


def compact_catalog_topic(topic: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "title": str(topic.get("title", "")).strip() or "Untitled",
        "source_count": item_source_count(topic),
        "count": item_count(topic),
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


def item_source_count(item: dict[str, Any]) -> int:
    if "source_count" in item:
        return int(item.get("source_count") or 0)
    return len(item.get("sources", []))


def item_count(item: dict[str, Any]) -> int:
    if "count" in item:
        return int(item.get("count") or 0)
    items = item.get("items", [])
    return len(items) if items else 1


def finalize_categories(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for category in categories:
        category["articles"] = sorted(
            category["articles"],
            key=lambda item: (-int(item["count"]), -int(item["source_count"]), item["title"].casefold()),
        )
        category["topics"] = sorted(
            category["topics"],
            key=lambda item: (-int(item["count"]), -int(item["source_count"]), item["title"].casefold()),
        )
        category["article_count"] = len(category["articles"])
        category["deferred_count"] = len(category["topics"])
        category["source_count"] = sum(
            int(item["source_count"]) for item in [*category["articles"], *category["topics"]]
        )

    return sorted(
        categories,
        key=lambda category: (
            -(int(category["article_count"]) + int(category["deferred_count"])),
            -int(category["source_count"]),
            str(category["title"]).casefold(),
        ),
    )


def build_merge_suggestions(
    deferred: list[dict[str, Any]],
    article_categories: dict[str, list[dict[str, Any]]],
    topic_categories: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    suggestions: list[dict[str, Any]] = []
    orphans: list[dict[str, Any]] = []

    for topic in sorted(deferred, key=lambda item: str(item.get("title", "")).casefold()):
        topic_title = str(topic.get("title", "")).strip() or "Untitled"
        category = category_for_item(topic)
        candidates = article_categories.get(category["key"], [])
        suggestion = best_merge_suggestion(topic_title, category["title"], candidates)
        if suggestion is None:
            action = "needs_review" if category["title"] == UNCATEGORIZED else "catalog_only"
            suggestion = {
                "topic_title": topic_title,
                "topic_category": topic_categories.get(topic_title, category["title"]),
                "article_title": "",
                "article_slug": "",
                "action": action,
                "score": 0.0,
                "reason": "no same-category article overlap",
            }
            orphans.append(compact_catalog_topic(topic) | {"category": category["title"]})
        suggestions.append(suggestion)

    return suggestions, sorted(
        orphans,
        key=lambda item: (str(item["category"]).casefold(), str(item["title"]).casefold()),
    )


def best_merge_suggestion(
    topic_title: str,
    category_title: str,
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    normalized_topic = normalize_index_key(topic_title)
    topic_tokens = title_tokens(topic_title)
    best: tuple[int, float, str, dict[str, Any], str, str] | None = None

    for article in candidates:
        article_title = str(article["title"])
        normalized_article = normalize_index_key(article_title)
        article_tokens = title_tokens(article_title)

        if normalized_topic == normalized_article:
            rank = 3
            score = 1.0
            action = "merge_as_alias"
            reason = "normalized title match"
        else:
            overlap = topic_tokens & article_tokens
            containment = len(overlap) / max(1, min(len(topic_tokens), len(article_tokens)))
            union_score = len(overlap) / max(1, len(topic_tokens | article_tokens))
            if containment >= 0.8 and len(overlap) >= 2:
                rank = 2
                score = round(containment, 3)
                action = "merge_as_section"
                reason = "high token containment"
            elif len(overlap) >= 2:
                rank = 1
                score = round(union_score, 3)
                action = "merge_as_section"
                reason = "same-category title token overlap"
            else:
                continue

        candidate = (rank, score, article_title.casefold(), article, action, reason)
        if best is None or candidate[:2] > best[:2] or (
            candidate[0] == best[0] and candidate[1] == best[1] and candidate[2] < best[2]
        ):
            best = candidate

    if best is None:
        return None

    _rank, score, _title_key, article, action, reason = best
    return {
        "topic_title": topic_title,
        "topic_category": category_title,
        "article_title": str(article["title"]),
        "article_slug": str(article["slug"]),
        "action": action,
        "score": score,
        "reason": reason,
    }


def title_tokens(title: str) -> set[str]:
    return {
        token
        for token in normalize_index_key(title).split()
        if len(token) > 2 and token not in WEAK_TITLE_TOKENS
    }


def write_catalog(raw_data: Path, catalog: dict[str, Any]) -> Path:
    output_dir = raw_data / "catalog"
    write_json(output_dir / "summary.json", catalog["summary"])
    write_json(output_dir / "categories.json", catalog["categories"])
    write_json(output_dir / "merge_suggestions.json", catalog["merge_suggestions"])
    write_json(output_dir / "orphan_topics.json", catalog["orphan_topics"])
    return output_dir


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected JSON list: {path}")
    return payload


def count_catalog_categories(raw_data: Path) -> int:
    return len(read_json_list(raw_data / "catalog" / "categories.json"))
