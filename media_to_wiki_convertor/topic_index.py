from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import shutil
from typing import Any


def normalize_index_key(value: str) -> str:
    normalized = value.casefold().strip()
    normalized = re.sub(r"[/\\|:;,.!?()\[\]{}\"'`]+", " ", normalized)
    normalized = normalized.replace("—", " ").replace("–", " ").replace("-", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def slugify_key(value: str) -> str:
    key = normalize_index_key(value)
    slug = re.sub(r"[^\w]+", "-", key, flags=re.UNICODE)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "untitled"


def read_knowledge_payloads(raw_data: Path) -> list[dict[str, Any]]:
    root = raw_data / "extracted_knowledge"
    if not root.exists():
        return []

    payloads: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/*.json"), key=lambda item: (item.parent.name, item.name)):
        payloads.append(json.loads(path.read_text(encoding="utf-8")))
    return payloads


def build_topic_index(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    domains = Counter(str(payload.get("detected_domain", "")).strip() for payload in payloads)
    domains.pop("", None)

    topics: dict[str, dict[str, Any]] = {}
    terms: dict[str, dict[str, Any]] = {}
    wiki_candidates: dict[str, dict[str, Any]] = {}

    for payload in payloads:
        source = source_from_payload(payload)
        for topic in payload.get("topics", []):
            add_index_entry(
                topics,
                title=str(topic.get("name", "")),
                source=source,
                payload={
                    "description": str(topic.get("description", "")),
                    "evidence": str(topic.get("evidence", "")),
                    "chunk_title": str(payload.get("chunk_title", "")),
                    "domain": str(payload.get("detected_domain", "")),
                },
            )
        for term in payload.get("terms", []):
            add_index_entry(
                terms,
                title=str(term.get("term", "")),
                source=source,
                payload={
                    "definition": str(term.get("definition", "")),
                    "evidence": str(term.get("evidence", "")),
                    "chunk_title": str(payload.get("chunk_title", "")),
                    "domain": str(payload.get("detected_domain", "")),
                },
            )
        for candidate in payload.get("wiki_candidates", []):
            add_index_entry(
                wiki_candidates,
                title=str(candidate.get("title", "")),
                source=source,
                payload={
                    "reason": str(candidate.get("reason", "")),
                    "suggested_section": str(candidate.get("suggested_section", "")),
                    "chunk_title": str(payload.get("chunk_title", "")),
                    "domain": str(payload.get("detected_domain", "")),
                },
            )

    pages = build_pages(wiki_candidates)
    return {
        "summary": {
            "knowledge_files": len(payloads),
            "domains": len(domains),
            "topics": len(topics),
            "terms": len(terms),
            "wiki_candidates": len(wiki_candidates),
            "pages": len(pages),
        },
        "domains": counter_to_rows(domains),
        "topics": entries_to_rows(topics),
        "terms": entries_to_rows(terms),
        "wiki_candidates": entries_to_rows(wiki_candidates),
        "pages": pages,
    }


def source_from_payload(payload: dict[str, Any]) -> dict[str, str]:
    source = payload.get("source", {})
    return {
        "video_id": str(source.get("video_id", "")),
        "chunk_id": str(source.get("chunk_id", "")),
        "start": str(source.get("start", "")),
        "end": str(source.get("end", "")),
    }


def add_index_entry(
    entries: dict[str, dict[str, Any]],
    title: str,
    source: dict[str, str],
    payload: dict[str, Any],
) -> None:
    title = title.strip()
    if not title:
        return

    key = normalize_index_key(title)
    entry = entries.setdefault(
        key,
        {
            "key": key,
            "title": title,
            "variants": [],
            "items": [],
            "sources": [],
        },
    )
    if title not in entry["variants"]:
        entry["variants"].append(title)
    if source not in entry["sources"]:
        entry["sources"].append(source)
    entry["items"].append({"title": title, "source": source, **payload})


def counter_to_rows(counter: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"name": name, "count": count}
        for name, count in sorted(counter.items(), key=lambda item: (-item[1], item[0].casefold()))
    ]


def entries_to_rows(entries: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in entries.values():
        rows.append(
            {
                "key": entry["key"],
                "title": preferred_title(entry["variants"]),
                "variants": sorted(entry["variants"], key=lambda value: (len(value), value.casefold())),
                "count": len(entry["items"]),
                "source_count": len(entry["sources"]),
                "sources": entry["sources"],
                "items": entry["items"],
            }
        )
    return sorted(rows, key=lambda row: (-row["count"], row["title"].casefold()))


def build_pages(wiki_candidates: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for row in entries_to_rows(wiki_candidates):
        sections = sorted(
            {
                str(item.get("suggested_section", "")).strip()
                for item in row["items"]
                if str(item.get("suggested_section", "")).strip()
            }
        )
        domains = sorted(
            {
                str(item.get("domain", "")).strip()
                for item in row["items"]
                if str(item.get("domain", "")).strip()
            }
        )
        pages.append(
            {
                "key": row["key"],
                "slug": slugify_key(row["title"]),
                "title": row["title"],
                "variants": row["variants"],
                "count": row["count"],
                "source_count": row["source_count"],
                "suggested_sections": sections,
                "domains": domains,
                "sources": row["sources"],
                "items": row["items"],
            }
        )
    return pages


def preferred_title(variants: list[str]) -> str:
    return sorted(variants, key=lambda value: (-sum(char.isupper() for char in value), len(value)))[0]


def write_topic_index(raw_data: Path, index: dict[str, Any]) -> Path:
    output_dir = raw_data / "topic_index"
    pages_dir = output_dir / "pages"
    if pages_dir.exists():
        shutil.rmtree(pages_dir)
    pages_dir.mkdir(parents=True, exist_ok=True)

    write_json(output_dir / "summary.json", index["summary"])
    write_json(output_dir / "domains.json", index["domains"])
    write_json(output_dir / "topics.json", index["topics"])
    write_json(output_dir / "terms.json", index["terms"])
    write_json(output_dir / "wiki_candidates.json", index["wiki_candidates"])
    write_json(output_dir / "pages.json", index["pages"])

    for page in index["pages"]:
        write_json(pages_dir / f"{page['slug']}.json", page)

    return output_dir


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def count_topic_index_pages(raw_data: Path) -> int:
    pages_json = raw_data / "topic_index" / "pages.json"
    if pages_json.exists():
        return len(json.loads(pages_json.read_text(encoding="utf-8")))

    pages_dir = raw_data / "topic_index" / "pages"
    if not pages_dir.exists():
        return 0
    return sum(1 for path in pages_dir.glob("*.json") if path.is_file() and path.stat().st_size > 0)
