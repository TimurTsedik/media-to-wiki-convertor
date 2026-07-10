from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
from typing import Any
from urllib.parse import quote

from media_to_wiki_convertor.labels import heading_translation_map, label_aliases, wiki_labels
from media_to_wiki_convertor.manifest import VideoRecord, read_manifest


START_HERE_NOTE = "00 Start Here.md"
COURSE_ROOT = "01 Course Materials"
ARTICLE_ROOT = "02 Reference Wiki"
INDEX_ROOT = "03 Indexes"
SOURCE_ROOT = "04 Sources"
TRANSCRIPT_ROOT = "05 Transcripts"
SYSTEM_ROOT = "99 System"
LEGACY_MANAGED_PATHS = (
    "Wiki",
    "Index",
    "Sources",
    "90 Transcripts",
    "90 Transcripts.md",
    "Course Materials",
    "00 Home.md",
)

MANAGED_DIRS = (
    COURSE_ROOT,
    ARTICLE_ROOT,
    INDEX_ROOT,
    SOURCE_ROOT,
    TRANSCRIPT_ROOT,
    SYSTEM_ROOT,
)
LINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
BACKTICK_SOURCE_REF_PATTERN = re.compile(r"`([^`\n]+)`")
MARKDOWN_SOURCE_LINK_PATTERN = re.compile(r"\[([^\]\n]+)\]\(([^)\n]+)\)")
BRACKETED_BACKTICK_SOURCE_REF_PATTERN = re.compile(r"\[`([^`\n]+)`\]")
BRACKETED_PREFIXED_SOURCE_REF_PATTERN = re.compile(
    r"\[((?:source|video|video_id|course-source-pack):[A-Za-z0-9_-]+[#/:][A-Za-z0-9_-]+)\]"
)
BRACKETED_BARE_SOURCE_REF_PATTERN = re.compile(r"\[([A-Za-z0-9_-]+[#/:][A-Za-z0-9_-]+)\]")
BRACKETED_SOURCE_REF_PATTERN = re.compile(r"\[([A-Za-z0-9_-]+):([A-Za-z0-9_-]+)\]")
PREFIXED_SOURCE_REF_PATTERN = re.compile(
    r"\b(?:source|video|video_id|course-source-pack):([A-Za-z0-9_-]+)[#/:](?:chunk[\s:-]*)?([A-Za-z0-9_-]+)"
)
BARE_SOURCE_REF_PATTERN = re.compile(r"(?<![:/])\b([A-Za-z0-9_-]+)#([A-Za-z0-9_-]+)\b")
INVALID_FILENAME_CHARS = set(':\\?#^[]|')


@dataclass(frozen=True)
class VaultBuildResult:
    vault: Path
    articles: int
    source_notes: int
    transcript_notes: int
    indexes: int


def build_obsidian_vault(raw_data: Path, vault: Path, output_language: str = "ru") -> VaultBuildResult:
    pages = read_json_list(raw_data / "article_plan" / "pages.json")
    if not pages:
        raise ValueError("No article plan pages found. Run build-article-plan first.")

    draft_dir = raw_data / "draft_articles"
    missing = [str(page["slug"]) for page in pages if not (draft_dir / f"{page['slug']}.md").exists()]
    if missing:
        raise ValueError(f"Missing draft article files: {', '.join(missing[:10])}")

    vault.mkdir(parents=True, exist_ok=True)
    for path in LEGACY_MANAGED_PATHS:
        remove_generated_path(vault / path)
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
        markdown = localize_known_markdown_headings(markdown, output_language)
        markdown, unknown_links = rewrite_article_links(markdown, link_targets)
        for unknown_link in unknown_links:
            unlinked_mentions[unknown_link].add(str(page["title"]))
        markdown = add_article_frontmatter(markdown, page)
        markdown = add_article_transcript_sources(
            markdown,
            page,
            records_by_id,
            output_language=output_language,
        )
        write_text(output_path, markdown)

        for source in page.get("sources", []):
            source_pages[(str(source["video_id"]), str(source["chunk_id"]))].append(page)

    add_catalog_source_pages(raw_data, source_pages)
    source_notes = write_source_notes(raw_data, vault, source_pages, records_by_id)
    transcript_notes = write_transcript_notes(
        raw_data,
        vault,
        source_pages,
        output_language=output_language,
    )
    indexes = write_indexes(
        raw_data,
        vault,
        pages,
        source_pages,
        unlinked_mentions,
        records_by_id,
        output_language=output_language,
    )
    write_course_materials(raw_data, vault, pages, output_language=output_language)
    write_home(raw_data, vault, pages, source_notes, transcript_notes, output_language=output_language)

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
    return Path(ARTICLE_ROOT, *parts[:-1], f"{parts[-1]}.md")


def note_target_for_title(title: str) -> str:
    return note_path_for_title(title).with_suffix("").as_posix()


def source_chunk_target(video_id: str, chunk_id: str) -> str:
    return f"{SOURCE_ROOT}/Chunks/{video_id}/{chunk_id}"


def catalog_target(catalog_key: str) -> str:
    return f"{INDEX_ROOT}/Catalog/{catalog_key}"


def rewrite_legacy_vault_target(target: str) -> str:
    legacy_roots = {
        "Wiki": ARTICLE_ROOT,
        "Sources": SOURCE_ROOT,
        "Course Materials": COURSE_ROOT,
        "Index": INDEX_ROOT,
        "90 Transcripts": TRANSCRIPT_ROOT,
    }
    for legacy_root, current_root in legacy_roots.items():
        if target == legacy_root:
            return current_root
        legacy_prefix = f"{legacy_root}/"
        if target.startswith(legacy_prefix):
            return f"{current_root}/{target.removeprefix(legacy_prefix)}"
    return ""


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
    output_language: str = "ru",
) -> str:
    sources = page.get("sources", [])
    if not sources:
        return markdown

    labels = wiki_labels(output_language)
    lines = ["", f"## {labels.source_transcripts}", ""]
    seen_video_ids: set[str] = set()
    for source in sources:
        video_id = str(source.get("video_id", ""))
        if not video_id or video_id in seen_video_ids:
            continue
        seen_video_ids.add(video_id)
        link = transcript_link(video_id, records_by_id)
        if link:
            lines.append(f"- {link}")

    lines.extend(["", f"## {labels.source_chunks}", ""])
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
            f"- [[{source_chunk_target(video_id, chunk_id)}|{video_id}/{chunk_id}]]{time_range}"
        )

    return markdown.rstrip() + "\n" + "\n".join(lines).rstrip() + "\n"


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def localize_known_markdown_headings(markdown: str, output_language: str = "ru") -> str:
    translations = heading_translation_map(output_language)
    if not translations:
        return markdown

    def replace(match: re.Match[str]) -> str:
        marker = match.group("marker")
        title = match.group("title").strip()
        localized_title = translations.get(title)
        if localized_title is None:
            return match.group(0)
        return f"{marker} {localized_title}"

    return re.sub(
        r"^(?P<marker>#{2,6})\s+(?P<title>.+?)\s*$",
        replace,
        markdown,
        flags=re.M,
    )


def write_indexes(
    raw_data: Path,
    vault: Path,
    pages: list[dict[str, Any]],
    source_pages: dict[tuple[str, str], list[dict[str, Any]]],
    unlinked_mentions: dict[str, set[str]],
    records_by_id: dict[str, VideoRecord],
    output_language: str = "ru",
) -> int:
    write_text(vault / INDEX_ROOT / "Articles.md", render_articles_index(pages))
    write_text(vault / INDEX_ROOT / "Domains.md", render_domains_index(pages))
    write_text(vault / INDEX_ROOT / "Sources.md", render_sources_index(source_pages, records_by_id))
    write_text(
        vault / INDEX_ROOT / "Deferred Topics.md",
        render_deferred_index(raw_data, output_language=output_language),
    )
    write_text(
        vault / INDEX_ROOT / "Unlinked Mentions.md",
        render_unlinked_mentions(unlinked_mentions, output_language=output_language),
    )
    catalog_indexes = write_catalog_indexes(
        raw_data,
        vault,
        pages,
        output_language=output_language,
    )
    return 5 + catalog_indexes


def write_home(
    raw_data: Path,
    vault: Path,
    pages: list[dict[str, Any]],
    source_notes: int,
    transcript_notes: int,
    output_language: str = "ru",
) -> None:
    summary = read_json_object(raw_data / "article_plan" / "summary.json")
    labels = wiki_labels(output_language)
    has_catalog = bool(read_json_list(raw_data / "catalog" / "categories.json"))
    has_course_materials = bool(read_json_list(raw_data / "course_plan" / "chapters.json"))
    chunks_count = count_files(raw_data / "chunks", "*.json")
    knowledge_count = count_files(raw_data / "extracted_knowledge", "*.json")
    drafts_count = count_files(raw_data / "draft_articles", "*.md")
    navigation = [
        f"- [[{INDEX_ROOT}/Articles|Articles]]",
        f"- [[{INDEX_ROOT}/Domains|Domains]]",
    ]
    if has_catalog:
        navigation.append(f"- [[{INDEX_ROOT}/Catalog|Catalog]]")
    if has_course_materials:
        navigation.append(
            f"- [[{COURSE_ROOT}/00 {labels.course_materials_title}|{labels.course_materials_title}]]"
        )
    navigation.extend(
        [
            f"- [[{INDEX_ROOT}/Sources|Sources]]",
            f"- [[{TRANSCRIPT_ROOT}|Transcripts]]",
            f"- [[{INDEX_ROOT}/Deferred Topics|Deferred Topics]]",
            f"- [[{INDEX_ROOT}/Unlinked Mentions|Unlinked Mentions]]",
        ]
    )
    lines = [
        f"# {labels.vault_title}",
        "",
        f"## {labels.navigation}",
        *navigation,
        "",
        f"## {labels.vault_status}",
        f"- {labels.wiki_articles_count}: {len(pages)}",
        f"- Source notes: {source_notes}",
        f"- Transcript notes: {transcript_notes}",
        f"- Draft articles: {drafts_count}",
        f"- Transcript chunks: {chunks_count}",
        f"- Extracted knowledge files: {knowledge_count}",
        f"- Topic pages before article planning: {summary.get('topic_pages', 0)}",
        f"- Deferred topics: {summary.get('deferred_pages', 0)}",
        "",
        f"## {labels.main_articles}",
    ]
    for page in pages[:15]:
        lines.append(f"- {article_link(page)}")
    write_text(vault / START_HERE_NOTE, "\n".join(lines) + "\n")


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
            f"- [[{source_chunk_target(video_id, chunk_id)}|{video_id}/{chunk_id}]]"
            f"{transcript_part} — {links}"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_catalog_indexes(
    raw_data: Path,
    vault: Path,
    pages: list[dict[str, Any]],
    output_language: str = "ru",
) -> int:
    categories = read_json_list(raw_data / "catalog" / "categories.json")
    if not categories:
        return 0

    known_titles = {str(page.get("title", "")) for page in pages}
    write_text(vault / INDEX_ROOT / "Catalog.md", render_catalog_index(categories))
    for category in categories:
        key = str(category.get("key", "")).strip() or sanitize_filename_part(
            str(category.get("title", "Catalog"))
        )
        write_text(
            vault / INDEX_ROOT / "Catalog" / f"{key}.md",
            render_catalog_category(
                category,
                known_titles,
                output_language=output_language,
            ),
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
            f"- [[{catalog_target(key)}|{title}]] — "
            f"articles={article_count}; topics={deferred_count}; sources={source_count}"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_catalog_category(
    category: dict[str, Any],
    known_titles: set[str],
    output_language: str = "ru",
) -> str:
    title = str(category.get("title", "Untitled"))
    labels = wiki_labels(output_language)
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
        lines.append(labels.no_catalog_articles)

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
        lines.append(labels.no_catalog_topics)

    return "\n".join(lines).rstrip() + "\n"


def write_course_materials(
    raw_data: Path,
    vault: Path,
    pages: list[dict[str, Any]],
    output_language: str = "ru",
) -> int:
    chapters = read_json_list(raw_data / "course_plan" / "chapters.json")
    if not chapters:
        return 0

    labels = wiki_labels(output_language)
    known_titles = {str(page.get("title", "")) for page in pages}
    source_alias_targets = course_article_source_alias_targets(pages)
    course_link_targets = {title: note_target_for_title(title) for title in known_titles}
    write_text(
        vault / COURSE_ROOT / f"00 {labels.course_materials_title}.md",
        render_course_materials_index(chapters, output_language=output_language),
    )
    for chapter in chapters:
        key = str(chapter.get("key", "")).strip() or sanitize_filename_part(
            str(chapter.get("title", "chapter"))
        )
        draft_path = raw_data / "course_materials" / f"{key}.md"
        if draft_path.exists() and draft_path.stat().st_size > 0:
            markdown = rewrite_course_material_links(
                localize_known_markdown_headings(
                    draft_path.read_text(encoding="utf-8"),
                    output_language,
                ),
                course_link_targets,
                source_targets=course_chapter_source_targets(chapter),
                source_alias_targets=source_alias_targets,
            )
            appendix = render_course_chapter_reference_appendix(
                chapter,
                output_language=output_language,
            )
            if appendix:
                markdown = markdown.rstrip() + "\n\n" + appendix
            markdown = rewrite_course_material_map_links(
                markdown,
                chapter_key=key,
                link_targets=course_link_targets,
                output_language=output_language,
            )
        else:
            markdown = render_course_chapter(chapter, known_titles, output_language=output_language)
        write_text(
            vault / COURSE_ROOT / f"{key}.md",
            markdown,
        )
    return 1 + len(chapters)


def render_course_materials_index(
    chapters: list[dict[str, Any]],
    output_language: str = "ru",
) -> str:
    labels = wiki_labels(output_language)
    lines = [f"# {labels.course_materials_title}", ""]
    for chapter in chapters:
        key = str(chapter.get("key", "chapter"))
        title = str(chapter.get("title", "Untitled"))
        article_count = int(chapter.get("article_count", 0))
        topic_count = int(chapter.get("topic_count", 0))
        lines.append(
            f"- [[{COURSE_ROOT}/{key}|{title}]] — "
            f"articles={article_count}; topics={topic_count}"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_course_chapter(
    chapter: dict[str, Any],
    known_titles: set[str],
    output_language: str = "ru",
) -> str:
    title = str(chapter.get("title", "Untitled"))
    labels = wiki_labels(output_language)
    lines = [
        f"# {title}",
        "",
        f"## {labels.course_section_map}",
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
        lines.append(labels.no_course_articles)

    lines.extend(["", f"## {labels.course_topics}", ""])
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
        lines.append(labels.no_course_topics)

    return "\n".join(lines).rstrip() + "\n"


def render_course_chapter_reference_appendix(
    chapter: dict[str, Any],
    output_language: str = "ru",
) -> str:
    topics = chapter.get("topics", [])
    if not topics:
        return ""

    labels = wiki_labels(output_language)
    lines = [f"## {labels.full_topic_source_index}", ""]
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
    source_alias_targets: dict[tuple[str, str], tuple[str, str]] | None = None,
) -> str:
    known_vault_prefixes = (
        f"{ARTICLE_ROOT}/",
        f"{SOURCE_ROOT}/",
        f"{COURSE_ROOT}/",
        f"{INDEX_ROOT}/",
        f"{TRANSCRIPT_ROOT}/",
    )
    source_targets = source_targets or set()
    source_alias_targets = source_alias_targets or {}

    def replace(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        alias = match.group(2)
        base_target, separator, heading = target.partition("#")
        legacy_target = rewrite_legacy_vault_target(base_target)
        if legacy_target:
            rewritten_target = legacy_target
            if separator:
                rewritten_target = f"{rewritten_target}#{heading}"
            label = alias if alias is not None else base_target.rsplit("/", 1)[-1]
            return f"[[{rewritten_target}|{label}]]"
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
    rewritten = rewrite_course_material_source_refs(
        rewritten,
        source_targets,
        source_alias_targets,
    )
    return rewritten


def rewrite_course_material_map_links(
    markdown: str,
    chapter_key: str,
    link_targets: dict[str, str],
    output_language: str = "ru",
) -> str:
    labels = wiki_labels(output_language)
    section_map_pattern = markdown_h2_section_pattern(
        label_aliases("course_section_map", output_language)
    )
    match = re.search(section_map_pattern, markdown, flags=re.M | re.S)
    if not match:
        return markdown

    section_map_heading = match.group("heading")
    headings = course_material_heading_titles(markdown)
    reference_appendix_heading = find_h2_heading(
        markdown,
        label_aliases("full_topic_source_index", output_language),
    )
    has_reference_appendix = bool(reference_appendix_heading)
    reference_anchor = reference_appendix_heading or labels.full_topic_source_index
    rewritten_lines: list[str] = []
    changed = False
    for line in match.group("body").splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            rewritten_lines.append(line)
            continue

        label = course_map_item_label(stripped[1:].strip())
        if not label:
            rewritten_lines.append(line)
            continue

        if label in link_targets:
            rewritten_lines.append(f"- [[{link_targets[label]}|{label}]]")
            changed = True
        elif label in headings:
            rewritten_lines.append(f"- [[{COURSE_ROOT}/{chapter_key}#{label}|{label}]]")
            changed = True
        elif heading := fuzzy_course_heading(label, headings):
            rewritten_lines.append(f"- [[{COURSE_ROOT}/{chapter_key}#{heading}|{label}]]")
            changed = True
        elif has_reference_appendix:
            rewritten_lines.append(
                f"- [[{COURSE_ROOT}/{chapter_key}#{reference_anchor}|{label}]]"
            )
            changed = True
        else:
            rewritten_lines.append(line)

    if not changed:
        return markdown

    replacement = f"## {section_map_heading}\n" + "\n".join(rewritten_lines)
    if match.group("body").endswith("\n"):
        replacement += "\n"
    return markdown[: match.start()] + replacement + markdown[match.end() :]


def markdown_h2_section_pattern(headings: list[str]) -> str:
    alternatives = "|".join(re.escape(heading) for heading in headings)
    return rf"^##\s+(?P<heading>{alternatives})\s*\n(?P<body>.*?)(?=^##\s+|\Z)"


def find_h2_heading(markdown: str, headings: list[str]) -> str | None:
    alternatives = "|".join(re.escape(heading) for heading in headings)
    match = re.search(rf"^##\s+(?P<heading>{alternatives})\s*$", markdown, flags=re.M)
    return match.group("heading") if match else None


def course_material_heading_titles(markdown: str) -> set[str]:
    titles: set[str] = set()
    for match in re.finditer(r"^###\s+(.+?)\s*$", markdown, flags=re.M):
        label = course_map_item_label(match.group(1).strip())
        if label:
            titles.add(label)
    return titles


def fuzzy_course_heading(label: str, headings: set[str]) -> str | None:
    label_tokens = course_heading_tokens(label)
    if not label_tokens:
        return None

    best_heading = None
    best_score = 0.0
    for heading in headings:
        heading_tokens = course_heading_tokens(heading)
        if not heading_tokens:
            continue
        overlap = label_tokens & heading_tokens
        score = len(overlap) / max(1, min(len(label_tokens), len(heading_tokens)))
        if score > best_score:
            best_score = score
            best_heading = heading
    if best_score > 0.5:
        return best_heading
    return None


def course_heading_tokens(value: str) -> set[str]:
    normalized = value.casefold().replace("/", " ")
    return {
        token
        for token in re.findall(r"[\w#+.-]+", normalized)
        if len(token) > 1
    }


def course_map_item_label(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    value = value.split(" — ", 1)[0].strip()
    markdown_link = re.fullmatch(r"\[([^\]]+)\]\([^)]+\)", value)
    if markdown_link:
        value = markdown_link.group(1).strip()
    wikilink = re.fullmatch(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]", value)
    if wikilink:
        value = (wikilink.group(2) or wikilink.group(1)).strip()
        if "/" in value and wikilink.group(2) is None:
            value = value.rsplit("/", 1)[-1]
    return value.strip()


def rewrite_course_material_source_refs(
    markdown: str,
    source_targets: set[tuple[str, str]],
    source_alias_targets: dict[tuple[str, str], tuple[str, str]],
) -> str:
    wikilink_placeholders: dict[str, str] = {}

    def protect_wikilink(match: re.Match[str]) -> str:
        key = f"@@COURSE_WIKILINK_{len(wikilink_placeholders)}@@"
        wikilink_placeholders[key] = match.group(0)
        return key

    def restore_wikilinks(value: str) -> str:
        for key, wikilink in wikilink_placeholders.items():
            value = value.replace(key, wikilink)
        return value

    def source_link(video_id: str, chunk_id: str) -> str | None:
        video_id = canonical_source_video_id(video_id)
        source_target = (video_id, chunk_id)
        if source_target in source_alias_targets:
            video_id, chunk_id = source_alias_targets[source_target]
        elif source_target not in source_targets:
            return None
        return f"[[{source_chunk_target(video_id, chunk_id)}|{video_id}/{chunk_id}]]"

    def replace_backticked(match: re.Match[str]) -> str:
        source_ref = extract_course_source_ref(match.group(1))
        if not source_ref:
            return match.group(0)
        video_id, chunk_id = source_ref
        return source_link(video_id, chunk_id) or match.group(0)

    def replace_markdown_link(match: re.Match[str]) -> str:
        label = match.group(1)
        url = match.group(2)
        source_ref = (
            extract_course_markdown_source_ref(label, url)
            or extract_course_source_ref(url)
            or extract_course_source_ref(label)
        )
        if not source_ref:
            return match.group(0)
        video_id, chunk_id = source_ref
        return source_link(video_id, chunk_id) or match.group(0)

    def replace_bracketed_backtick(match: re.Match[str]) -> str:
        source_ref = extract_course_source_ref(match.group(1))
        if not source_ref:
            return match.group(0)
        video_id, chunk_id = source_ref
        return source_link(video_id, chunk_id) or match.group(0)

    def replace_bracketed_prefixed(match: re.Match[str]) -> str:
        source_ref = extract_course_source_ref(match.group(1))
        if not source_ref:
            return match.group(0)
        video_id, chunk_id = source_ref
        return source_link(video_id, chunk_id) or match.group(0)

    def replace_bracketed_bare(match: re.Match[str]) -> str:
        source_ref = extract_course_source_ref(match.group(1))
        if not source_ref:
            return match.group(0)
        video_id, chunk_id = source_ref
        return source_link(video_id, chunk_id) or match.group(0)

    def replace_bracketed(match: re.Match[str]) -> str:
        video_id = match.group(1)
        chunk_id = match.group(2)
        return source_link(video_id, chunk_id) or match.group(0)

    def replace_prefixed(match: re.Match[str]) -> str:
        video_id = match.group(1)
        chunk_id = match.group(2)
        return source_link(video_id, chunk_id) or match.group(0)

    def replace_bare(match: re.Match[str]) -> str:
        video_id = match.group(1)
        chunk_id = match.group(2)
        return source_link(video_id, chunk_id) or match.group(0)

    rewritten = LINK_PATTERN.sub(protect_wikilink, markdown)
    rewritten = MARKDOWN_SOURCE_LINK_PATTERN.sub(replace_markdown_link, rewritten)
    rewritten = BRACKETED_BACKTICK_SOURCE_REF_PATTERN.sub(replace_bracketed_backtick, rewritten)
    rewritten = BACKTICK_SOURCE_REF_PATTERN.sub(replace_backticked, rewritten)
    rewritten = BRACKETED_PREFIXED_SOURCE_REF_PATTERN.sub(replace_bracketed_prefixed, rewritten)
    rewritten = BRACKETED_BARE_SOURCE_REF_PATTERN.sub(replace_bracketed_bare, rewritten)
    rewritten = BRACKETED_SOURCE_REF_PATTERN.sub(replace_bracketed, rewritten)
    rewritten = PREFIXED_SOURCE_REF_PATTERN.sub(replace_prefixed, rewritten)
    rewritten = BARE_SOURCE_REF_PATTERN.sub(replace_bare, rewritten)
    return restore_wikilinks(rewritten)


def extract_course_markdown_source_ref(label: str, url: str) -> tuple[str, str] | None:
    source_video_url = re.search(r"source://video/([A-Za-z0-9_-]+)#", url)
    chunk_id = extract_chunk_marker(label) or extract_chunk_marker(url)
    if source_video_url and chunk_id:
        return canonical_source_video_id(source_video_url.group(1)), chunk_id
    return None


def extract_course_source_ref(value: str) -> tuple[str, str] | None:
    source_url = re.search(
        r"(?:source://|https?://[^/\s)]+/)([A-Za-z0-9_-]+)#([A-Za-z0-9_-]+)",
        value,
    )
    if source_url:
        return canonical_source_video_id(source_url.group(1)), source_url.group(2)

    prefixed = re.search(
        r"\b(?:source|video|video_id|course-source-pack):([A-Za-z0-9_-]+)[#/:](?:chunk[\s:-]*)?([A-Za-z0-9_-]+)",
        value,
    )
    if prefixed:
        return canonical_source_video_id(prefixed.group(1)), prefixed.group(2)

    bare = re.search(r"\b([A-Za-z0-9_-]+)[#/:]([A-Za-z0-9_-]+)\b", value)
    if bare:
        return canonical_source_video_id(bare.group(1)), bare.group(2)

    return None


def extract_chunk_marker(value: str) -> str | None:
    match = re.search(r"\bchunk[\s:-]*(\d{4})\b", value)
    if match:
        return match.group(1)
    return None


def canonical_source_video_id(video_id: str) -> str:
    return video_id.removeprefix("video_")


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


def course_article_source_alias_targets(pages: list[dict[str, Any]]) -> dict[tuple[str, str], tuple[str, str]]:
    targets: dict[tuple[str, str], tuple[str, str]] = {}
    for page in pages:
        slug = str(page.get("slug", "")).strip()
        if not slug:
            continue
        for index, source in enumerate(page.get("sources", []), start=1):
            if not isinstance(source, dict):
                continue
            video_id = str(source.get("video_id", "")).strip()
            chunk_id = str(source.get("chunk_id", "")).strip()
            if video_id and chunk_id:
                targets[(slug, f"{index:04d}")] = (video_id, chunk_id)
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
        links.append(f"[[{source_chunk_target(video_id, chunk_id)}|{video_id}/{chunk_id}]]")
    return links


def render_deferred_index(raw_data: Path, output_language: str = "ru") -> str:
    deferred = read_json_list(raw_data / "article_plan" / "deferred.json")
    labels = wiki_labels(output_language)
    lines = ["# Deferred Topics", ""]
    if not deferred:
        lines.append(labels.no_deferred_topics)
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


def render_unlinked_mentions(
    unlinked_mentions: dict[str, set[str]],
    output_language: str = "ru",
) -> str:
    labels = wiki_labels(output_language)
    lines = ["# Unlinked Mentions", ""]
    if not unlinked_mentions:
        lines.append(labels.no_unlinked_mentions)
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
        return f"[[{catalog_target(catalog_key)}|{title}]]"
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
        write_text(vault / SOURCE_ROOT / "Chunks" / video_id / f"{chunk_id}.md", "\n".join(lines))
    return len(source_pages)


def transcript_link(video_id: str, records_by_id: dict[str, VideoRecord]) -> str:
    record = records_by_id.get(video_id)
    if record is None:
        return ""
    return f"[[{TRANSCRIPT_ROOT}/{record.video_id}|{record.title}]]"


def write_transcript_notes(
    raw_data: Path,
    vault: Path,
    source_pages: dict[tuple[str, str], list[dict[str, Any]]],
    output_language: str = "ru",
) -> int:
    records = read_manifest(raw_data)
    transcript_records = [record for record in records if transcript_paths(raw_data, record.video_id)]
    labels = wiki_labels(output_language)
    lines = [f"# {TRANSCRIPT_ROOT}", ""]
    if not transcript_records:
        lines.append(labels.no_transcripts)
        write_text(vault / f"{TRANSCRIPT_ROOT}.md", "\n".join(lines) + "\n")
        return 0

    for record in sorted(transcript_records, key=lambda item: item.title.casefold()):
        write_transcript_note(raw_data, vault, record, source_pages)
        lines.append(f"- [[{TRANSCRIPT_ROOT}/{record.video_id}|{record.title}]]")

    write_text(vault / f"{TRANSCRIPT_ROOT}.md", "\n".join(lines).rstrip() + "\n")
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
                f"- [[{source_chunk_target(record.video_id, chunk_id)}|{record.video_id}/{chunk_id}]]"
            )
    write_text(vault / TRANSCRIPT_ROOT / f"{record.video_id}.md", "\n".join(lines) + "\n")


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
    wiki_dir = vault / ARTICLE_ROOT
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


def remove_generated_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
