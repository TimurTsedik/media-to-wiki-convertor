from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from larchenko_kb.topic_index import normalize_index_key, slugify_key


def canonical_article_key(title: str) -> str:
    without_parentheses = re.sub(r"\([^)]{1,16}\)", "", title)
    return normalize_index_key(without_parentheses)


def read_topic_pages(raw_data: Path) -> list[dict[str, Any]]:
    path = raw_data / "topic_index" / "pages.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def build_article_plan(
    topic_pages: list[dict[str, Any]],
    min_sources: int = 2,
    max_pages: int | None = None,
) -> dict[str, Any]:
    if min_sources <= 0:
        raise ValueError("min_sources must be positive")
    if max_pages is not None and max_pages <= 0:
        raise ValueError("max_pages must be positive")

    grouped = group_topic_pages(topic_pages)
    articles: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []

    for group in grouped:
        article = article_from_group(group)
        if article["source_count"] >= min_sources:
            articles.append(article)
        else:
            deferred.append(article)

    articles = sorted(articles, key=lambda page: (-page["score"], page["title"].casefold()))
    if max_pages is not None:
        deferred.extend(articles[max_pages:])
        articles = articles[:max_pages]
    deferred = sorted(deferred, key=lambda page: (-page["score"], page["title"].casefold()))

    for article in articles:
        article["tier"] = tier_for_article(article)

    return {
        "summary": {
            "topic_pages": len(topic_pages),
            "canonical_groups": len(grouped),
            "article_pages": len(articles),
            "deferred_pages": len(deferred),
            "min_sources": min_sources,
            "max_pages": max_pages,
        },
        "pages": articles,
        "deferred": deferred,
    }


def group_topic_pages(topic_pages: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for page in topic_pages:
        key = canonical_article_key(str(page.get("title", "")))
        if not key:
            continue
        groups.setdefault(key, []).append(page)
    return list(groups.values())


def article_from_group(group: list[dict[str, Any]]) -> dict[str, Any]:
    variants = sorted(
        {
            variant
            for page in group
            for variant in [str(page.get("title", "")), *page.get("variants", [])]
            if str(variant).strip()
        },
        key=lambda value: (len(value), value.casefold()),
    )
    title = preferred_article_title(variants)
    aliases = [variant for variant in variants if variant != title]
    sources = unique_sources(source for page in group for source in page.get("sources", []))
    domains = sorted({domain for page in group for domain in page.get("domains", []) if domain})
    sections = sorted(
        {section for page in group for section in page.get("suggested_sections", []) if section}
    )
    items = [item for page in group for item in page.get("items", [])]
    count = sum(int(page.get("count", 0)) for page in group)
    source_count = len(sources)

    return {
        "key": canonical_article_key(title),
        "slug": slugify_key(title),
        "title": title,
        "aliases": aliases,
        "tier": "deferred",
        "score": score_article(source_count=source_count, count=count, aliases=len(aliases)),
        "count": count,
        "source_count": source_count,
        "domains": domains,
        "suggested_sections": sections,
        "sources": sources,
        "items": items,
    }


def preferred_article_title(variants: list[str]) -> str:
    no_parentheses = [variant for variant in variants if "(" not in variant and ")" not in variant]
    candidates = no_parentheses or variants
    return sorted(candidates, key=lambda value: (-sum(char.isupper() for char in value), len(value)))[0]


def unique_sources(sources: Any) -> list[dict[str, str]]:
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for source in sources:
        normalized = {
            "video_id": str(source.get("video_id", "")),
            "chunk_id": str(source.get("chunk_id", "")),
            "start": str(source.get("start", "")),
            "end": str(source.get("end", "")),
        }
        key = (
            normalized["video_id"],
            normalized["chunk_id"],
            normalized["start"],
            normalized["end"],
        )
        if key not in seen:
            seen.add(key)
            unique.append(normalized)
    return sorted(unique, key=lambda item: (item["video_id"], item["chunk_id"]))


def score_article(source_count: int, count: int, aliases: int) -> int:
    return source_count * 100 + count * 10 + aliases


def tier_for_article(article: dict[str, Any]) -> str:
    if int(article["source_count"]) >= 4:
        return "core"
    if int(article["source_count"]) >= 2:
        return "supporting"
    return "candidate"


def build_source_pack(raw_data: Path, article: dict[str, Any]) -> dict[str, Any]:
    sources = []
    for source in article.get("sources", []):
        video_id = str(source.get("video_id", ""))
        chunk_id = str(source.get("chunk_id", ""))
        knowledge = read_json_if_exists(raw_data / "extracted_knowledge" / video_id / f"{chunk_id}.json")
        chunk = read_json_if_exists(raw_data / "chunks" / video_id / f"{chunk_id}.json")
        sources.append(
            {
                "source": source,
                "knowledge": compact_knowledge(knowledge),
                "chunk_text": str(chunk.get("text", "")),
            }
        )
    return {
        "article": {
            "title": article["title"],
            "slug": article["slug"],
            "aliases": article.get("aliases", []),
            "tier": article.get("tier", ""),
            "domains": article.get("domains", []),
            "suggested_sections": article.get("suggested_sections", []),
        },
        "sources": sources,
    }


def compact_knowledge(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": payload.get("source", {}),
        "chunk_title": payload.get("chunk_title", ""),
        "detected_domain": payload.get("detected_domain", ""),
        "confidence": payload.get("confidence", ""),
        "summary": payload.get("summary", ""),
        "topics": payload.get("topics", []),
        "practices": payload.get("practices", []),
        "mistakes": payload.get("mistakes", []),
        "terms": payload.get("terms", []),
        "questions": payload.get("questions", []),
        "wiki_candidates": payload.get("wiki_candidates", []),
    }


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_article_plan(raw_data: Path, plan: dict[str, Any]) -> Path:
    output_dir = raw_data / "article_plan"
    source_packs_dir = output_dir / "source_packs"
    source_packs_dir.mkdir(parents=True, exist_ok=True)

    for stale_path in source_packs_dir.glob("*.json"):
        stale_path.unlink()

    write_json(output_dir / "summary.json", plan["summary"])
    write_json(output_dir / "pages.json", plan["pages"])
    write_json(output_dir / "deferred.json", plan["deferred"])
    write_json(output_dir / "aliases.json", build_alias_index(plan["pages"]))

    for article in plan["pages"]:
        write_json(source_packs_dir / f"{article['slug']}.json", build_source_pack(raw_data, article))

    return output_dir


def build_alias_index(articles: list[dict[str, Any]]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for article in articles:
        aliases[article["title"]] = article["title"]
        for alias in article.get("aliases", []):
            aliases[alias] = article["title"]
    return dict(sorted(aliases.items(), key=lambda item: item[0].casefold()))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def count_article_plan_pages(raw_data: Path) -> int:
    path = raw_data / "article_plan" / "pages.json"
    if not path.exists():
        return 0
    return len(json.loads(path.read_text(encoding="utf-8")))
