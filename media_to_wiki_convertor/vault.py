from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
from typing import Any
from urllib.parse import quote

from media_to_wiki_convertor.manifest import VideoRecord, read_manifest


MANAGED_DIRS = ("Wiki", "Index", "Sources", "90 Transcripts", "Course Materials")
LINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
BRACKETED_SOURCE_REF_PATTERN = re.compile(r"\[([A-Za-z0-9_-]+):([A-Za-z0-9_-]+)\]")
PREFIXED_SOURCE_REF_PATTERN = re.compile(r"\bsource:([A-Za-z0-9_-]+)[#/:]([A-Za-z0-9_-]+)")
INVALID_FILENAME_CHARS = set(':\\?#^[]|')


@dataclass(frozen=True)
class VaultBuildResult:
    vault: Path
    articles: int
    source_notes: int
    transcript_notes: int
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

    records_by_id = {record.video_id: record for record in read_manifest(raw_data)}
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
        markdown = add_article_transcript_sources(markdown, page, records_by_id)
        write_text(output_path, markdown)

        for source in page.get("sources", []):
            source_pages[(str(source["video_id"]), str(source["chunk_id"]))].append(page)

    add_catalog_source_pages(raw_data, source_pages)
    source_notes = write_source_notes(raw_data, vault, source_pages, records_by_id)
    transcript_notes = write_transcript_notes(raw_data, vault, source_pages)
    indexes = write_indexes(raw_data, vault, pages, source_pages, unlinked_mentions, records_by_id)
    write_course_materials(raw_data, vault, pages)
    write_home(raw_data, vault, pages, source_notes, transcript_notes)

    return VaultBuildResult(
        vault=vault,
        articles=len(pages),
        source_notes=source_notes,
        transcript_notes=transcript_notes,
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


def add_article_transcript_sources(
    markdown: str,
    page: dict[str, Any],
    records_by_id: dict[str, VideoRecord],
) -> str:
    sources = page.get("sources", [])
    if not sources:
        return markdown

    lines = ["", "## Исходные транскрибации", ""]
    seen_video_ids: set[str] = set()
    for source in sources:
        video_id = str(source.get("video_id", ""))
        if not video_id or video_id in seen_video_ids:
            continue
        seen_video_ids.add(video_id)
        link = transcript_link(video_id, records_by_id)
        if link:
            lines.append(f"- {link}")

    lines.extend(["", "## Source chunks", ""])
    seen_chunks: set[tuple[str, str]] = set()
    for source in sources:
        video_id = str(source.get("video_id", ""))
        chunk_id = str(source.get("chunk_id", ""))
        if not video_id or not chunk_id or (video_id, chunk_id) in seen_chunks:
            continue
        seen_chunks.add((video_id, chunk_id))
        start = str(source.get("start", ""))
        end = str(source.get("end", ""))
        time_range = f" {start}-{end}" if start or end else ""
        lines.append(
            f"- [[Sources/Chunks/{video_id}/{chunk_id}|{video_id}/{chunk_id}]]{time_range}"
        )

    return markdown.rstrip() + "\n" + "\n".join(lines).rstrip() + "\n"


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_indexes(
    raw_data: Path,
    vault: Path,
    pages: list[dict[str, Any]],
    source_pages: dict[tuple[str, str], list[dict[str, Any]]],
    unlinked_mentions: dict[str, set[str]],
    records_by_id: dict[str, VideoRecord],
) -> int:
    write_text(vault / "Index" / "Articles.md", render_articles_index(pages))
    write_text(vault / "Index" / "Domains.md", render_domains_index(pages))
    write_text(vault / "Index" / "Sources.md", render_sources_index(source_pages, records_by_id))
    write_text(vault / "Index" / "Deferred Topics.md", render_deferred_index(raw_data))
    write_text(vault / "Index" / "Unlinked Mentions.md", render_unlinked_mentions(unlinked_mentions))
    catalog_indexes = write_catalog_indexes(raw_data, vault, pages)
    return 5 + catalog_indexes


def write_home(
    raw_data: Path,
    vault: Path,
    pages: list[dict[str, Any]],
    source_notes: int,
    transcript_notes: int,
) -> None:
    summary = read_json_object(raw_data / "article_plan" / "summary.json")
    has_catalog = bool(read_json_list(raw_data / "catalog" / "categories.json"))
    has_course_materials = bool(read_json_list(raw_data / "course_plan" / "chapters.json"))
    chunks_count = count_files(raw_data / "chunks", "*.json")
    knowledge_count = count_files(raw_data / "extracted_knowledge", "*.json")
    drafts_count = count_files(raw_data / "draft_articles", "*.md")
    navigation = [
        "- [[Index/Articles|Articles]]",
        "- [[Index/Domains|Domains]]",
    ]
    if has_catalog:
        navigation.append("- [[Index/Catalog|Catalog]]")
    if has_course_materials:
        navigation.append(
            "- [[Course Materials/00 Справочные материалы по курсу|Справочные материалы по курсу]]"
        )
    navigation.extend(
        [
            "- [[Index/Sources|Sources]]",
            "- [[90 Transcripts|Transcripts]]",
            "- [[Index/Deferred Topics|Deferred Topics]]",
            "- [[Index/Unlinked Mentions|Unlinked Mentions]]",
        ]
    )
    lines = [
        "# Larchenko Training Wiki",
        "",
        "## Навигация",
        *navigation,
        "",
        "## Статус базы",
        f"- Wiki-статей: {len(pages)}",
        f"- Source notes: {source_notes}",
        f"- Transcript notes: {transcript_notes}",
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


def render_sources_index(
    source_pages: dict[tuple[str, str], list[dict[str, Any]]],
    records_by_id: dict[str, VideoRecord],
) -> str:
    lines = ["# Sources", ""]
    for video_id, chunk_id in sorted(source_pages):
        pages = source_pages[(video_id, chunk_id)]
        links = ", ".join(source_page_link(page) for page in pages)
        transcript = transcript_link(video_id, records_by_id)
        transcript_part = f" — {transcript}" if transcript else ""
        lines.append(
            f"- [[Sources/Chunks/{video_id}/{chunk_id}|{video_id}/{chunk_id}]]"
            f"{transcript_part} — {links}"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_catalog_indexes(raw_data: Path, vault: Path, pages: list[dict[str, Any]]) -> int:
    categories = read_json_list(raw_data / "catalog" / "categories.json")
    if not categories:
        return 0

    known_titles = {str(page.get("title", "")) for page in pages}
    write_text(vault / "Index" / "Catalog.md", render_catalog_index(categories))
    for category in categories:
        key = str(category.get("key", "")).strip() or sanitize_filename_part(
            str(category.get("title", "Catalog"))
        )
        write_text(
            vault / "Index" / "Catalog" / f"{key}.md",
            render_catalog_category(category, known_titles),
        )
    return 1 + len(categories)


def render_catalog_index(categories: list[dict[str, Any]]) -> str:
    lines = ["# Catalog", ""]
    for category in categories:
        title = str(category.get("title", "Untitled"))
        key = str(category.get("key", "untitled"))
        article_count = int(category.get("article_count", 0))
        deferred_count = int(category.get("deferred_count", 0))
        source_count = int(category.get("source_count", 0))
        lines.append(
            f"- [[Index/Catalog/{key}|{title}]] — "
            f"articles={article_count}; topics={deferred_count}; sources={source_count}"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_catalog_category(category: dict[str, Any], known_titles: set[str]) -> str:
    title = str(category.get("title", "Untitled"))
    lines = [
        f"# {title}",
        "",
        f"- Articles: {int(category.get('article_count', 0))}",
        f"- Deferred topics: {int(category.get('deferred_count', 0))}",
        f"- Sources: {int(category.get('source_count', 0))}",
        "",
        "## Articles",
        "",
    ]
    articles = category.get("articles", [])
    if articles:
        for article in articles:
            article_title = str(article.get("title", "Untitled"))
            label = article_link({"title": article_title}) if article_title in known_titles else article_title
            lines.append(
                f"- {label} — sources={int(article.get('source_count', 0))}; "
                f"mentions={int(article.get('count', 0))}"
            )
    else:
        lines.append("Нет статей.")

    lines.extend(["", "## Catalog Topics", ""])
    topics = category.get("topics", [])
    if topics:
        for topic in topics:
            topic_title = str(topic.get("title", "Untitled"))
            chunks = catalog_topic_source_links(topic)
            chunks_suffix = f"; chunks={', '.join(chunks)}" if chunks else ""
            lines.append(
                f"- {topic_title} — sources={int(topic.get('source_count', 0))}; "
                f"mentions={int(topic.get('count', 0))}{chunks_suffix}"
            )
    else:
        lines.append("Нет отложенных тем.")

    return "\n".join(lines).rstrip() + "\n"


def write_course_materials(raw_data: Path, vault: Path, pages: list[dict[str, Any]]) -> int:
    chapters = read_json_list(raw_data / "course_plan" / "chapters.json")
    if not chapters:
        return 0

    known_titles = {str(page.get("title", "")) for page in pages}
    write_text(
        vault / "Course Materials" / "00 Справочные материалы по курсу.md",
        render_course_materials_index(chapters),
    )
    for chapter in chapters:
        key = str(chapter.get("key", "")).strip() or sanitize_filename_part(
            str(chapter.get("title", "chapter"))
        )
        draft_path = raw_data / "course_materials" / f"{key}.md"
        if draft_path.exists() and draft_path.stat().st_size > 0:
            markdown = rewrite_course_material_links(
                draft_path.read_text(encoding="utf-8"),
                {title: note_target_for_title(title) for title in known_titles},
                source_targets=course_chapter_source_targets(chapter),
            )
            appendix = render_course_chapter_reference_appendix(chapter)
            if appendix:
                markdown = markdown.rstrip() + "\n\n" + appendix
        else:
            markdown = render_course_chapter(chapter, known_titles)
        write_text(
            vault / "Course Materials" / f"{key}.md",
            markdown,
        )
    return 1 + len(chapters)


def render_course_materials_index(chapters: list[dict[str, Any]]) -> str:
    lines = ["# Справочные материалы по курсу", ""]
    for chapter in chapters:
        key = str(chapter.get("key", "chapter"))
        title = str(chapter.get("title", "Untitled"))
        article_count = int(chapter.get("article_count", 0))
        topic_count = int(chapter.get("topic_count", 0))
        lines.append(
            f"- [[Course Materials/{key}|{title}]] — "
            f"articles={article_count}; topics={topic_count}"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_course_chapter(chapter: dict[str, Any], known_titles: set[str]) -> str:
    title = str(chapter.get("title", "Untitled"))
    lines = [
        f"# {title}",
        "",
        "## Карта раздела",
        "",
    ]
    articles = chapter.get("articles", [])
    if articles:
        for article in articles:
            article_title = str(article.get("title", "Untitled"))
            label = article_link({"title": article_title}) if article_title in known_titles else article_title
            lines.append(
                f"- {label} — sources={int(article.get('source_count', 0))}; "
                f"mentions={int(article.get('count', 0))}"
            )
    else:
        lines.append("Пока нет отдельных wiki-статей.")

    lines.extend(["", "## Подтемы курса", ""])
    topics = chapter.get("topics", [])
    if topics:
        for topic in topics:
            topic_title = str(topic.get("title", "Untitled"))
            chunks = catalog_topic_source_links(topic)
            chunks_suffix = f"; chunks={', '.join(chunks)}" if chunks else ""
            lines.append(
                f"### {topic_title}\n\n"
                f"- Sources: {int(topic.get('source_count', 0))}\n"
                f"- Mentions: {int(topic.get('count', 0))}{chunks_suffix}\n"
            )
    else:
        lines.append("Пока нет подтем из расширенного списка.")

    return "\n".join(lines).rstrip() + "\n"


def render_course_chapter_reference_appendix(chapter: dict[str, Any]) -> str:
    topics = chapter.get("topics", [])
    if not topics:
        return ""

    lines = ["## Полный список подтем и источников", ""]
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        topic_title = str(topic.get("title", "Untitled"))
        chunks = catalog_topic_source_links(topic)
        chunks_suffix = f" — {', '.join(chunks)}" if chunks else ""
        lines.append(f"- {topic_title}{chunks_suffix}")
    return "\n".join(lines).rstrip() + "\n"


def rewrite_course_material_links(
    markdown: str,
    link_targets: dict[str, str],
    source_targets: set[tuple[str, str]] | None = None,
) -> str:
    known_vault_prefixes = ("Wiki/", "Sources/", "Course Materials/", "Index/", "90 Transcripts/")
    source_targets = source_targets or set()

    def replace(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        alias = match.group(2)
        base_target, separator, heading = target.partition("#")
        if base_target.startswith(known_vault_prefixes):
            return match.group(0)
        if base_target not in link_targets:
            return alias if alias is not None else target

        rewritten_target = link_targets[base_target]
        if separator:
            rewritten_target = f"{rewritten_target}#{heading}"
        label = alias if alias is not None else base_target
        return f"[[{rewritten_target}|{label}]]"

    rewritten = LINK_PATTERN.sub(replace, markdown)
    rewritten = rewrite_course_material_source_refs(rewritten, source_targets)
    return rewritten


def rewrite_course_material_source_refs(
    markdown: str,
    source_targets: set[tuple[str, str]],
) -> str:
    def source_link(video_id: str, chunk_id: str) -> str | None:
        if (video_id, chunk_id) not in source_targets:
            return None
        return f"[[Sources/Chunks/{video_id}/{chunk_id}|{video_id}/{chunk_id}]]"

    def replace_bracketed(match: re.Match[str]) -> str:
        video_id = match.group(1)
        chunk_id = match.group(2)
        return source_link(video_id, chunk_id) or match.group(0)

    def replace_prefixed(match: re.Match[str]) -> str:
        video_id = match.group(1)
        chunk_id = match.group(2)
        return source_link(video_id, chunk_id) or match.group(0)

    rewritten = BRACKETED_SOURCE_REF_PATTERN.sub(replace_bracketed, markdown)
    return PREFIXED_SOURCE_REF_PATTERN.sub(replace_prefixed, rewritten)


def course_chapter_source_targets(chapter: dict[str, Any]) -> set[tuple[str, str]]:
    targets: set[tuple[str, str]] = set()
    for topic in chapter.get("topics", []):
        if not isinstance(topic, dict):
            continue
        for source in topic.get("sources", []):
            if not isinstance(source, dict):
                continue
            video_id = str(source.get("video_id", "")).strip()
            chunk_id = str(source.get("chunk_id", "")).strip()
            if video_id and chunk_id:
                targets.add((video_id, chunk_id))
    return targets


def catalog_topic_source_links(topic: dict[str, Any]) -> list[str]:
    links: list[str] = []
    for source in topic.get("sources", []):
        if not isinstance(source, dict):
            continue
        video_id = str(source.get("video_id", "")).strip()
        chunk_id = str(source.get("chunk_id", "")).strip()
        if not video_id or not chunk_id:
            continue
        links.append(f"[[Sources/Chunks/{video_id}/{chunk_id}|{video_id}/{chunk_id}]]")
    return links


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


def source_page_link(page: dict[str, Any]) -> str:
    catalog_key = str(page.get("catalog_key", "")).strip()
    if catalog_key:
        title = str(page.get("title", "Catalog Topic"))
        return f"[[Index/Catalog/{catalog_key}|{title}]]"
    return article_link(page)


def add_catalog_source_pages(
    raw_data: Path,
    source_pages: dict[tuple[str, str], list[dict[str, Any]]],
) -> None:
    for category in read_json_list(raw_data / "catalog" / "categories.json"):
        catalog_key = str(category.get("key", "")).strip()
        catalog_title = str(category.get("title", "Catalog"))
        if not catalog_key:
            continue
        for topic in category.get("topics", []):
            if not isinstance(topic, dict):
                continue
            topic_title = str(topic.get("title", "Catalog Topic"))
            for source in topic.get("sources", []):
                if not isinstance(source, dict):
                    continue
                video_id = str(source.get("video_id", "")).strip()
                chunk_id = str(source.get("chunk_id", "")).strip()
                if not video_id or not chunk_id:
                    continue
                source_pages[(video_id, chunk_id)].append(
                    {
                        "title": topic_title,
                        "catalog_key": catalog_key,
                        "catalog_title": catalog_title,
                        "sources": [source],
                    }
                )


def write_source_notes(
    raw_data: Path,
    vault: Path,
    source_pages: dict[tuple[str, str], list[dict[str, Any]]],
    records_by_id: dict[str, VideoRecord],
) -> int:
    for video_id, chunk_id in sorted(source_pages):
        pages = source_pages[(video_id, chunk_id)]
        chunk = read_json_object(raw_data / "chunks" / video_id / f"{chunk_id}.json")
        source = find_source(pages, video_id, chunk_id)
        start = source.get("start") or chunk.get("start_hms", "")
        end = source.get("end") or chunk.get("end_hms", "")
        transcript = transcript_link(video_id, records_by_id)
        lines = [
            f"# {video_id}/{chunk_id}",
            "",
            f"- Video: `{video_id}`",
            f"- Chunk: `{chunk_id}`",
            f"- Time: `{start}-{end}`",
            f"- Full transcript: {transcript}" if transcript else "- Full transcript: not found",
            "- Used by:",
            *[f"  - {source_page_link(page)}" for page in pages],
            "",
            "## Transcript Chunk",
            "",
            str(chunk.get("text", "")).strip(),
            "",
        ]
        write_text(vault / "Sources" / "Chunks" / video_id / f"{chunk_id}.md", "\n".join(lines))
    return len(source_pages)


def transcript_link(video_id: str, records_by_id: dict[str, VideoRecord]) -> str:
    record = records_by_id.get(video_id)
    if record is None:
        return ""
    return f"[[90 Transcripts/{record.video_id}|{record.title}]]"


def write_transcript_notes(
    raw_data: Path,
    vault: Path,
    source_pages: dict[tuple[str, str], list[dict[str, Any]]],
) -> int:
    records = read_manifest(raw_data)
    transcript_records = [record for record in records if transcript_paths(raw_data, record.video_id)]
    lines = ["# 90 Transcripts", ""]
    if not transcript_records:
        lines.append("Транскрипции пока не найдены.")
        write_text(vault / "90 Transcripts.md", "\n".join(lines) + "\n")
        return 0

    for record in sorted(transcript_records, key=lambda item: item.title.casefold()):
        write_transcript_note(raw_data, vault, record, source_pages)
        lines.append(f"- [[90 Transcripts/{record.video_id}|{record.title}]]")

    write_text(vault / "90 Transcripts.md", "\n".join(lines).rstrip() + "\n")
    return len(transcript_records)


def write_transcript_note(
    raw_data: Path,
    vault: Path,
    record: VideoRecord,
    source_pages: dict[tuple[str, str], list[dict[str, Any]]],
) -> None:
    transcript_files = transcript_paths(raw_data, record.video_id)
    used_chunks = sorted(
        chunk_id for video_id, chunk_id in source_pages if video_id == record.video_id
    )
    lines = [
        f"# {record.title}",
        "",
        f"- Video ID: `{record.video_id}`",
        f"- Source video: {file_link(Path(record.path), record.title)}",
        "- Transcript files:",
    ]
    for label, path in transcript_files:
        lines.append(f"  - {file_link(path, label)}")

    if used_chunks:
        lines.extend(["", "## Used Source Chunks", ""])
        for chunk_id in used_chunks:
            lines.append(
                f"- [[Sources/Chunks/{record.video_id}/{chunk_id}|{record.video_id}/{chunk_id}]]"
            )
    write_text(vault / "90 Transcripts" / f"{record.video_id}.md", "\n".join(lines) + "\n")


def transcript_paths(raw_data: Path, video_id: str) -> list[tuple[str, Path]]:
    transcript_dir = raw_data / "transcripts"
    candidates = [
        ("TXT", transcript_dir / f"{video_id}.txt"),
        ("SRT", transcript_dir / f"{video_id}.srt"),
        ("JSON", transcript_dir / f"{video_id}.json"),
    ]
    return [(label, path) for label, path in candidates if path.exists()]


def file_link(path: Path, label: str) -> str:
    absolute = path.expanduser().resolve()
    return f"[{escape_markdown_link_label(label)}](file://{quote(str(absolute))})"


def escape_markdown_link_label(label: str) -> str:
    return label.replace("\\", "\\\\").replace("[", r"\[").replace("]", r"\]")


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
