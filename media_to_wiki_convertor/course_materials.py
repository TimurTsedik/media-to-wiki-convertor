from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Callable, Protocol

from media_to_wiki_convertor.draft_articles import parse_response_text
from media_to_wiki_convertor.knowledge import (
    default_transport,
    gemini_url,
    parse_anthropic_text,
    parse_gemini_text,
    validate_api_key,
    validate_openai_api_key,
)

DEFAULT_MAX_PROMPT_TOPICS = 8
DEFAULT_MAX_CHUNK_CHARS = 350


Transport = Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class DraftCourseMaterialResult:
    output_path: Path
    skipped: bool


class CourseMaterialClient(Protocol):
    def draft(self, source_pack: dict[str, Any], known_titles: list[str]) -> str:
        ...


class OpenAICourseMaterialClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        output_language: str = "ru",
        endpoint: str = "https://api.openai.com/v1/responses",
        transport: Transport | None = None,
        max_topics: int = DEFAULT_MAX_PROMPT_TOPICS,
        max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    ) -> None:
        self.api_key = validate_openai_api_key(api_key)
        self.model = model
        self.output_language = output_language
        self.endpoint = endpoint
        self.transport = transport or default_transport
        self.max_topics = max_topics
        self.max_chunk_chars = max_chunk_chars

    @classmethod
    def from_env(
        cls,
        model: str,
        output_language: str = "ru",
        api_key_env: str = "OPENAI_API_KEY",
        endpoint: str = "https://api.openai.com/v1/responses",
        max_topics: int = DEFAULT_MAX_PROMPT_TOPICS,
        max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    ) -> "OpenAICourseMaterialClient":
        api_key = os.environ.get(api_key_env)
        if api_key is None:
            raise RuntimeError(f"Missing API key. Set {api_key_env} in your shell or .env.")
        validate_openai_api_key(api_key, api_key_env)
        return cls(
            api_key=api_key,
            model=model,
            output_language=output_language,
            endpoint=endpoint,
            max_topics=max_topics,
            max_chunk_chars=max_chunk_chars,
        )

    def draft(self, source_pack: dict[str, Any], known_titles: list[str]) -> str:
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": build_course_material_system_prompt(self.output_language)},
                {
                    "role": "user",
                    "content": build_course_material_prompt(
                        source_pack,
                        known_titles,
                        output_language=self.output_language,
                        max_topics=self.max_topics,
                        max_chunk_chars=self.max_chunk_chars,
                    ),
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = self.transport(self.endpoint, headers, payload)
        return parse_response_text(response).strip() + "\n"


class AnthropicCourseMaterialClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        output_language: str = "ru",
        endpoint: str = "https://api.anthropic.com/v1/messages",
        transport: Transport | None = None,
        max_tokens: int = 8192,
        max_topics: int = DEFAULT_MAX_PROMPT_TOPICS,
        max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    ) -> None:
        self.api_key = validate_api_key(
            api_key,
            api_key_env="ANTHROPIC_API_KEY",
            provider="anthropic",
        )
        self.model = model
        self.output_language = output_language
        self.endpoint = endpoint
        self.transport = transport or default_transport
        self.max_tokens = max_tokens
        self.max_topics = max_topics
        self.max_chunk_chars = max_chunk_chars

    @classmethod
    def from_env(
        cls,
        model: str,
        output_language: str = "ru",
        api_key_env: str = "ANTHROPIC_API_KEY",
        endpoint: str = "https://api.anthropic.com/v1/messages",
        max_topics: int = DEFAULT_MAX_PROMPT_TOPICS,
        max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    ) -> "AnthropicCourseMaterialClient":
        api_key = os.environ.get(api_key_env)
        if api_key is None:
            raise RuntimeError(f"Missing API key for anthropic. Set {api_key_env} in your shell or .env.")
        validate_api_key(api_key, api_key_env=api_key_env, provider="anthropic")
        return cls(
            api_key=api_key,
            model=model,
            output_language=output_language,
            endpoint=endpoint,
            max_topics=max_topics,
            max_chunk_chars=max_chunk_chars,
        )

    def draft(self, source_pack: dict[str, Any], known_titles: list[str]) -> str:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": build_course_material_system_prompt(self.output_language),
            "messages": [
                {
                    "role": "user",
                    "content": build_course_material_prompt(
                        source_pack,
                        known_titles,
                        output_language=self.output_language,
                        max_topics=self.max_topics,
                        max_chunk_chars=self.max_chunk_chars,
                    ),
                }
            ],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        response = self.transport(self.endpoint, headers, payload)
        return parse_anthropic_text(response).strip() + "\n"


class GeminiCourseMaterialClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        output_language: str = "ru",
        endpoint: str = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        transport: Transport | None = None,
        max_topics: int = DEFAULT_MAX_PROMPT_TOPICS,
        max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    ) -> None:
        self.api_key = validate_api_key(
            api_key,
            api_key_env="GEMINI_API_KEY",
            provider="gemini",
        )
        self.model = model
        self.output_language = output_language
        self.endpoint = endpoint
        self.transport = transport or default_transport
        self.max_topics = max_topics
        self.max_chunk_chars = max_chunk_chars

    @classmethod
    def from_env(
        cls,
        model: str,
        output_language: str = "ru",
        api_key_env: str = "GEMINI_API_KEY",
        endpoint: str = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        max_topics: int = DEFAULT_MAX_PROMPT_TOPICS,
        max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    ) -> "GeminiCourseMaterialClient":
        api_key = os.environ.get(api_key_env)
        if api_key is None:
            raise RuntimeError(f"Missing API key for gemini. Set {api_key_env} in your shell or .env.")
        validate_api_key(api_key, api_key_env=api_key_env, provider="gemini")
        return cls(
            api_key=api_key,
            model=model,
            output_language=output_language,
            endpoint=endpoint,
            max_topics=max_topics,
            max_chunk_chars=max_chunk_chars,
        )

    def draft(self, source_pack: dict[str, Any], known_titles: list[str]) -> str:
        prompt = "\n\n".join(
            [
                build_course_material_system_prompt(self.output_language),
                build_course_material_prompt(
                    source_pack,
                    known_titles,
                    output_language=self.output_language,
                    max_topics=self.max_topics,
                    max_chunk_chars=self.max_chunk_chars,
                ),
            ]
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ]
        }
        headers = {"Content-Type": "application/json"}
        response = self.transport(gemini_url(self.endpoint, self.model, self.api_key), headers, payload)
        return parse_gemini_text(response).strip() + "\n"


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
