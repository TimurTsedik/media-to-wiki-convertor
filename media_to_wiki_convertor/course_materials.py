from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Protocol


DEFAULT_MAX_PROMPT_TOPICS = 30
DEFAULT_MAX_CHUNK_CHARS = 900


@dataclass(frozen=True)
class DraftCourseMaterialResult:
    output_path: Path
    skipped: bool


class CourseMaterialClient(Protocol):
    def draft(self, source_pack: dict[str, Any], known_titles: list[str]) -> str:
        ...


def build_course_material_system_prompt(output_language: str = "ru") -> str:
    return f"""Ты пишешь справочные материалы по курсу для Obsidian.

Твоя задача: превратить source-backed план главы в связный справочный материал.
Не переписывай существующие wiki-статьи целиком.
Не добавляй внешние знания.
Не выдумывай факты, практики, технологии или связи.
Используй только COURSE_SOURCE_PACK.
Пиши на языке: {output_language}.
Сохраняй технические термины на английском, если так естественнее.
Не оборачивай ответ в markdown code fence."""


def build_course_material_prompt(
    source_pack: dict[str, Any],
    known_titles: list[str],
    output_language: str = "ru",
    max_topics: int = DEFAULT_MAX_PROMPT_TOPICS,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> str:
    prompt_pack = compact_source_pack_for_prompt(
        source_pack,
        max_topics=max_topics,
        max_chunk_chars=max_chunk_chars,
    )
    chapter = prompt_pack.get("chapter", {})
    known_links = "\n".join(f"- [[{title}]]" for title in known_titles)
    return f"""COURSE CHAPTER:
title: {chapter.get("title", "")}
key: {chapter.get("key", "")}
articles: {chapter.get("article_count", 0)}
topics: {chapter.get("topic_count", 0)}
sources: {chapter.get("source_count", 0)}

Important:
Используй только COURSE_SOURCE_PACK.
Не добавляй знания, которых нет в COURSE_SOURCE_PACK.
Пиши на языке: {output_language}.
Это страница из раздела "Справочные материалы по курсу".
Ставь Obsidian-ссылки на существующие статьи только из KNOWN_ARTICLE_TITLES.
Если упоминаешь существующую статью, используй формат [[Название статьи]].
Для каждой подтемы сохраняй ссылки на source chunks.
Материал должен читаться как справочная глава курса, а не как протокол встречи.

Required Markdown shape:
# {chapter.get("title", "")}

## Коротко
3-6 предложений: что объединяет темы этой главы и зачем она нужна.

## Карта раздела
Список ссылок на существующие wiki-статьи из COURSE_SOURCE_PACK. Не придумывай новые wiki-статьи.

## Подтемы курса
Для важных подтем сделай подразделы третьего уровня.
В каждом подразделе:
- 2-5 предложений по материалам источников
- bullets с практическими замечаниями, если они есть в sources
- строка "Источники:" со ссылками на chunks

## Связанные материалы
Ссылки только на KNOWN_ARTICLE_TITLES, если связь явно следует из COURSE_SOURCE_PACK.

KNOWN_ARTICLE_TITLES:
{known_links}

COURSE_SOURCE_PACK:
{json.dumps(prompt_pack, ensure_ascii=False, indent=2)}
"""


def compact_source_pack_for_prompt(
    source_pack: dict[str, Any],
    max_topics: int = DEFAULT_MAX_PROMPT_TOPICS,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> dict[str, Any]:
    if max_topics <= 0:
        raise ValueError("max_topics must be positive")
    if max_chunk_chars <= 0:
        raise ValueError("max_chunk_chars must be positive")

    compact = dict(source_pack)
    topics = source_pack.get("topics", [])
    compact["topics"] = [
        compact_topic_for_prompt(topic, max_chunk_chars)
        for topic in topics[:max_topics]
        if isinstance(topic, dict)
    ]
    compact["prompt_limits"] = {
        "max_topics": max_topics,
        "max_chunk_chars": max_chunk_chars,
        "original_topics": len(topics) if isinstance(topics, list) else 0,
    }
    return compact


def compact_topic_for_prompt(topic: dict[str, Any], max_chunk_chars: int) -> dict[str, Any]:
    compact = dict(topic)
    compact["sources"] = [
        compact_source_for_prompt(source, max_chunk_chars)
        for source in topic.get("sources", [])
        if isinstance(source, dict)
    ]
    return compact


def compact_source_for_prompt(source: dict[str, Any], max_chunk_chars: int) -> dict[str, str]:
    compact = {key: str(value) for key, value in source.items()}
    chunk_text = compact.get("chunk_text", "")
    if len(chunk_text) > max_chunk_chars:
        compact["chunk_text"] = chunk_text[:max_chunk_chars].rstrip() + "..."
    return compact


def read_course_chapters(raw_data: Path) -> list[dict[str, Any]]:
    return read_json_list(raw_data / "course_plan" / "chapters.json")


def select_course_source_packs(
    raw_data: Path,
    chapters: list[dict[str, Any]],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")

    selected_chapters = chapters[:limit] if limit is not None else chapters
    packs: list[dict[str, Any]] = []
    for chapter in selected_chapters:
        path = raw_data / "course_plan" / "source_packs" / f"{chapter['key']}.json"
        if path.exists():
            packs.append(json.loads(path.read_text(encoding="utf-8")))
    return packs


def draft_output_path(raw_data: Path, chapter_key: str) -> Path:
    return raw_data / "course_materials" / f"{chapter_key}.md"


def draft_course_material(
    raw_data: Path,
    source_pack: dict[str, Any],
    client: CourseMaterialClient,
    known_titles: list[str],
    force: bool = False,
) -> DraftCourseMaterialResult:
    chapter = source_pack["chapter"]
    output_path = draft_output_path(raw_data, str(chapter["key"]))
    if output_path.exists() and output_path.stat().st_size > 0 and not force:
        return DraftCourseMaterialResult(output_path=output_path, skipped=True)

    markdown = client.draft(source_pack, known_titles)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return DraftCourseMaterialResult(output_path=output_path, skipped=False)


def count_course_materials(raw_data: Path) -> int:
    output_dir = raw_data / "course_materials"
    if not output_dir.exists():
        return 0
    return sum(1 for path in output_dir.glob("*.md") if path.is_file() and path.stat().st_size > 0)


def read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected JSON list: {path}")
    return payload
