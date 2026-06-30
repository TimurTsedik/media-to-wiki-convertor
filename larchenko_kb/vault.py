from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
from typing import Any


MANAGED_DIRS = ("Wiki", "Index", "Sources")
LINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
INVALID_FILENAME_CHARS = set(':\\?#^[]|')


@dataclass(frozen=True)
class VaultBuildResult:
    vault: Path
    articles: int
    source_notes: int
    indexes: int


def build_obsidian_vault(raw_data: Path, vault: Path) -> VaultBuildResult:
    pages = read_json_list(raw_data / "article_plan" / "pages.json")
    if not pages:
        raise ValueError("No article plan pages found. Run build-article-plan first.")

    draft_dir = raw_data / "draft_articles"
    missing = [str(page["slug"]) for page in pages if not (draft_dir / f"{page['slug']}.md").exists()]
    if missing:
        raise ValueError(f"Missing draft article files: {', '.join(missing[:10])}")

    vault.mkdir(parents=True, exist_ok=True)
    for dirname in MANAGED_DIRS:
        reset_dir(vault / dirname)

    link_targets = {str(page["title"]): note_target_for_title(str(page["title"])) for page in pages}
    source_pages: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    unlinked_mentions: dict[str, set[str]] = defaultdict(set)

    for page in pages:
        draft_path = draft_dir / f"{page['slug']}.md"
        output_path = vault / note_path_for_title(str(page["title"]))
        markdown = draft_path.read_text(encoding="utf-8")
        markdown, unknown_links = rewrite_article_links(markdown, link_targets)
        for unknown_link in unknown_links:
            unlinked_mentions[unknown_link].add(str(page["title"]))
        markdown = add_article_frontmatter(markdown, page)
        write_text(output_path, markdown)

        for source in page.get("sources", []):
            source_pages[(str(source["video_id"]), str(source["chunk_id"]))].append(page)

    indexes = write_indexes(raw_data, vault, pages, source_pages, unlinked_mentions)
    source_notes = write_source_notes(raw_data, vault, source_pages)
    write_home(raw_data, vault, pages, source_notes)

    return VaultBuildResult(
        vault=vault,
        articles=len(pages),
        source_notes=source_notes,
        indexes=indexes,
    )


def note_path_for_title(title: str) -> Path:
    parts = [sanitize_filename_part(part) for part in title.split("/")]
    parts = [part for part in parts if part]
    if not parts:
        parts = ["Untitled"]
    return Path("Wiki", *parts[:-1], f"{parts[-1]}.md")


def note_target_for_title(title: str) -> str:
    return note_path_for_title(title).with_suffix("").as_posix()


def sanitize_filename_part(value: str) -> str:
    cleaned = " ".join(value.strip().split())
    cleaned = "".join("-" if char in INVALID_FILENAME_CHARS else char for char in cleaned)
    cleaned = cleaned.strip(" .")
    return cleaned or "Untitled"


def rewrite_known_links(markdown: str, link_targets: dict[str, str]) -> str:
    rewritten, _unknown_links = rewrite_article_links(markdown, link_targets)
    return rewritten


def rewrite_article_links(markdown: str, link_targets: dict[str, str]) -> tuple[str, set[str]]:
    unknown_links: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        alias = match.group(2)
        base_target, separator, heading = target.partition("#")
        if base_target not in link_targets:
            unknown_links.add(base_target)
            return alias if alias is not None else target

        rewritten_target = link_targets[base_target]
        if separator:
            rewritten_target = f"{rewritten_target}#{heading}"
        label = alias if alias is not None else base_target
        return f"[[{rewritten_target}|{label}]]"

    return LINK_PATTERN.sub(replace, markdown), unknown_links


def add_article_frontmatter(markdown: str, page: dict[str, Any]) -> str:
    aliases = [str(alias) for alias in page.get("aliases", [])]
    domains = [str(domain) for domain in page.get("domains", [])]
    lines = [
        "---",
        f"title: {yaml_string(str(page.get('title', '')))}",
        "aliases:",
        *[f"  - {yaml_string(alias)}" for alias in aliases],
        "domains:",
        *[f"  - {yaml_string(domain)}" for domain in domains],
        f"tier: {yaml_string(str(page.get('tier', '')))}",
        f"source_count: {int(page.get('source_count', 0))}",
        "---",
        "",
    ]
    return "\n".join(lines) + markdown.lstrip()


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_indexes(
    raw_data: Path,
    vault: Path,
    pages: list[dict[str, Any]],
    source_pages: dict[tuple[str, str], list[dict[str, Any]]],
    unlinked_mentions: dict[str, set[str]],
) -> int:
    write_text(vault / "Index" / "Articles.md", render_articles_index(pages))
    write_text(vault / "Index" / "Domains.md", render_domains_index(pages))
    write_text(vault / "Index" / "Sources.md", render_sources_index(source_pages))
    write_text(vault / "Index" / "Deferred Topics.md", render_deferred_index(raw_data))
    write_text(vault / "Index" / "Unlinked Mentions.md", render_unlinked_mentions(unlinked_mentions))
    return 5


def write_home(raw_data: Path, vault: Path, pages: list[dict[str, Any]], source_notes: int) -> None:
    summary = read_json_object(raw_data / "article_plan" / "summary.json")
    chunks_count = count_files(raw_data / "chunks", "*.json")
    knowledge_count = count_files(raw_data / "extracted_knowledge", "*.json")
    drafts_count = count_files(raw_data / "draft_articles", "*.md")
    lines = [
        "# Larchenko Training Wiki",
        "",
        "## Навигация",
        "- [[Index/Articles|Articles]]",
        "- [[Index/Domains|Domains]]",
        "- [[Index/Sources|Sources]]",
        "- [[Index/Deferred Topics|Deferred Topics]]",
        "- [[Index/Unlinked Mentions|Unlinked Mentions]]",
        "",
        "## Статус базы",
        f"- Wiki-статей: {len(pages)}",
        f"- Source notes: {source_notes}",
        f"- Draft articles: {drafts_count}",
        f"- Transcript chunks: {chunks_count}",
        f"- Extracted knowledge files: {knowledge_count}",
        f"- Topic pages before article planning: {summary.get('topic_pages', 0)}",
        f"- Deferred topics: {summary.get('deferred_pages', 0)}",
        "",
        "## Основные статьи",
    ]
    for page in pages[:15]:
        lines.append(f"- {article_link(page)}")
    write_text(vault / "00 Home.md", "\n".join(lines) + "\n")


def render_articles_index(pages: list[dict[str, Any]]) -> str:
    lines = ["# Articles", ""]
    by_tier: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for page in pages:
        by_tier[str(page.get("tier", "other"))].append(page)

    for tier in sorted(by_tier):
        lines.extend([f"## {tier}", ""])
        for page in by_tier[tier]:
            domains = ", ".join(str(domain) for domain in page.get("domains", []))
            suffix = f" — {domains}" if domains else ""
            lines.append(f"- {article_link(page)}{suffix}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_domains_index(pages: list[dict[str, Any]]) -> str:
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for page in pages:
        domains = page.get("domains", []) or ["Unsorted"]
        for domain in domains:
            by_domain[str(domain)].append(page)

    lines = ["# Domains", ""]
    for domain in sorted(by_domain, key=str.casefold):
        lines.extend([f"## {domain}", ""])
        for page in sorted(by_domain[domain], key=lambda item: str(item["title"]).casefold()):
            lines.append(f"- {article_link(page)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_sources_index(source_pages: dict[tuple[str, str], list[dict[str, Any]]]) -> str:
    lines = ["# Sources", ""]
    for video_id, chunk_id in sorted(source_pages):
        pages = source_pages[(video_id, chunk_id)]
        links = ", ".join(article_link(page) for page in pages)
        lines.append(f"- [[Sources/Chunks/{video_id}/{chunk_id}|{video_id}/{chunk_id}]] — {links}")
    return "\n".join(lines).rstrip() + "\n"


def render_deferred_index(raw_data: Path) -> str:
    deferred = read_json_list(raw_data / "article_plan" / "deferred.json")
    lines = ["# Deferred Topics", ""]
    if not deferred:
        lines.append("Нет отложенных тем.")
        return "\n".join(lines) + "\n"

    for item in deferred:
        title = str(item.get("title") or item.get("key") or item.get("slug") or "Untitled")
        domains = ", ".join(str(domain) for domain in item.get("domains", []))
        source_count = item.get("source_count", item.get("count", 0))
        suffix_parts = []
        if domains:
            suffix_parts.append(domains)
        if source_count:
            suffix_parts.append(f"sources={source_count}")
        suffix = f" — {'; '.join(suffix_parts)}" if suffix_parts else ""
        lines.append(f"- {title}{suffix}")
    return "\n".join(lines).rstrip() + "\n"


def render_unlinked_mentions(unlinked_mentions: dict[str, set[str]]) -> str:
    lines = ["# Unlinked Mentions", ""]
    if not unlinked_mentions:
        lines.append("Нет неразрешенных wiki-упоминаний.")
        return "\n".join(lines) + "\n"

    for mention in sorted(unlinked_mentions, key=str.casefold):
        pages = sorted(unlinked_mentions[mention], key=str.casefold)
        page_links = ", ".join(f"[[{note_target_for_title(title)}|{title}]]" for title in pages)
        lines.append(f"- {mention} — {page_links}")
    return "\n".join(lines).rstrip() + "\n"


def article_link(page: dict[str, Any]) -> str:
    title = str(page["title"])
    return f"[[{note_target_for_title(title)}|{title}]]"


def write_source_notes(
    raw_data: Path,
    vault: Path,
    source_pages: dict[tuple[str, str], list[dict[str, Any]]],
) -> int:
    for video_id, chunk_id in sorted(source_pages):
        pages = source_pages[(video_id, chunk_id)]
        chunk = read_json_object(raw_data / "chunks" / video_id / f"{chunk_id}.json")
        source = find_source(pages, video_id, chunk_id)
        start = source.get("start") or chunk.get("start_hms", "")
        end = source.get("end") or chunk.get("end_hms", "")
        lines = [
            f"# {video_id}/{chunk_id}",
            "",
            f"- Video: `{video_id}`",
            f"- Chunk: `{chunk_id}`",
            f"- Time: `{start}-{end}`",
            "- Used by:",
            *[f"  - {article_link(page)}" for page in pages],
            "",
            "## Transcript Chunk",
            "",
            str(chunk.get("text", "")).strip(),
            "",
        ]
        write_text(vault / "Sources" / "Chunks" / video_id / f"{chunk_id}.md", "\n".join(lines))
    return len(source_pages)


def find_source(pages: list[dict[str, Any]], video_id: str, chunk_id: str) -> dict[str, Any]:
    for page in pages:
        for source in page.get("sources", []):
            if str(source.get("video_id")) == video_id and str(source.get("chunk_id")) == chunk_id:
                return source
    return {}


def count_vault_articles(vault: Path) -> int:
    wiki_dir = vault / "Wiki"
    if not wiki_dir.exists():
        return 0
    return count_files(wiki_dir, "*.md")


def count_files(root: Path, pattern: str) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob(pattern) if path.is_file())


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


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
