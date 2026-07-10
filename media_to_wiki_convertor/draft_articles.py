from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Callable, Protocol

from media_to_wiki_convertor.knowledge import (
    default_transport,
    gemini_url,
    parse_anthropic_text,
    parse_gemini_text,
    validate_api_key,
    validate_openai_api_key,
)
from media_to_wiki_convertor.labels import wiki_labels


def build_article_system_prompt(output_language: str = "ru") -> str:
    return f"""Ты пишешь учебные Markdown-статьи для Obsidian wiki по материалам тренинга.

Твоя задача: превратить source-backed материалы в осмысленную wiki-статью.
Не пересказывай звонок по порядку.
Не добавляй внешние знания.
Не выдумывай практики, термины, примеры, технологии или причинно-следственные связи.
Если в источниках мало информации для раздела, пропусти раздел или напиши коротко.
Пиши статью на языке: {output_language}.
Сохраняй технические термины на английском, если так естественнее.
Не оборачивай ответ в markdown code fence."""


ARTICLE_SYSTEM_PROMPT = build_article_system_prompt()


Transport = Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class DraftArticleResult:
    output_path: Path
    skipped: bool


class ArticleClient(Protocol):
    def draft(self, source_pack: dict[str, Any], known_titles: list[str]) -> str:
        ...


class OpenAIArticleClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        output_language: str = "ru",
        endpoint: str = "https://api.openai.com/v1/responses",
        transport: Transport | None = None,
    ) -> None:
        self.api_key = validate_openai_api_key(api_key)
        self.model = model
        self.output_language = output_language
        self.endpoint = endpoint
        self.transport = transport or default_transport

    @classmethod
    def from_env(
        cls,
        model: str,
        output_language: str = "ru",
        api_key_env: str = "OPENAI_API_KEY",
        endpoint: str = "https://api.openai.com/v1/responses",
    ) -> "OpenAIArticleClient":
        api_key = os.environ.get(api_key_env)
        if api_key is None:
            raise RuntimeError(f"Missing API key. Set {api_key_env} in your shell or .env.")
        validate_openai_api_key(api_key, api_key_env)
        return cls(api_key=api_key, model=model, output_language=output_language, endpoint=endpoint)

    def draft(self, source_pack: dict[str, Any], known_titles: list[str]) -> str:
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": build_article_system_prompt(self.output_language)},
                {
                    "role": "user",
                    "content": build_article_prompt(
                        source_pack,
                        known_titles,
                        output_language=self.output_language,
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


class AnthropicArticleClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        output_language: str = "ru",
        endpoint: str = "https://api.anthropic.com/v1/messages",
        transport: Transport | None = None,
        max_tokens: int = 8192,
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

    @classmethod
    def from_env(
        cls,
        model: str,
        output_language: str = "ru",
        api_key_env: str = "ANTHROPIC_API_KEY",
        endpoint: str = "https://api.anthropic.com/v1/messages",
    ) -> "AnthropicArticleClient":
        api_key = os.environ.get(api_key_env)
        if api_key is None:
            raise RuntimeError(f"Missing API key for anthropic. Set {api_key_env} in your shell or .env.")
        validate_api_key(api_key, api_key_env=api_key_env, provider="anthropic")
        return cls(api_key=api_key, model=model, output_language=output_language, endpoint=endpoint)

    def draft(self, source_pack: dict[str, Any], known_titles: list[str]) -> str:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": build_article_system_prompt(self.output_language),
            "messages": [
                {
                    "role": "user",
                    "content": build_article_prompt(
                        source_pack,
                        known_titles,
                        output_language=self.output_language,
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


class GeminiArticleClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        output_language: str = "ru",
        endpoint: str = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        transport: Transport | None = None,
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

    @classmethod
    def from_env(
        cls,
        model: str,
        output_language: str = "ru",
        api_key_env: str = "GEMINI_API_KEY",
        endpoint: str = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
    ) -> "GeminiArticleClient":
        api_key = os.environ.get(api_key_env)
        if api_key is None:
            raise RuntimeError(f"Missing API key for gemini. Set {api_key_env} in your shell or .env.")
        validate_api_key(api_key, api_key_env=api_key_env, provider="gemini")
        return cls(api_key=api_key, model=model, output_language=output_language, endpoint=endpoint)

    def draft(self, source_pack: dict[str, Any], known_titles: list[str]) -> str:
        prompt = "\n\n".join(
            [
                build_article_system_prompt(self.output_language),
                build_article_prompt(
                    source_pack,
                    known_titles,
                    output_language=self.output_language,
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


def parse_response_text(response: dict[str, Any]) -> str:
    if "output_text" in response:
        return str(response["output_text"])

    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and "text" in content:
                return str(content["text"])

    raise ValueError("OpenAI response did not contain output text.")


def build_article_prompt(
    source_pack: dict[str, Any],
    known_titles: list[str],
    output_language: str = "ru",
) -> str:
    article = source_pack.get("article", {})
    labels = wiki_labels(output_language)
    known_links = "\n".join(f"- [[{title}]]" for title in known_titles)
    summary_instruction = "2-4 sentences." if labels.sources == "Sources" else "2-4 предложения."
    source_format_intro = (
        "Source list format:" if labels.sources == "Sources" else "Список источников в формате:"
    )
    return f"""ARTICLE:
title: {article.get("title", "")}
aliases: {", ".join(article.get("aliases", []))}
tier: {article.get("tier", "")}
domains: {", ".join(article.get("domains", []))}
suggested_sections: {", ".join(article.get("suggested_sections", []))}

Important:
Используй только SOURCE_PACK.
Не добавляй знания, которых нет в SOURCE_PACK.
Пиши статью на языке: {output_language}.
Ставь Obsidian-ссылки только на статьи из KNOWN_ARTICLE_TITLES.
Если упоминаешь связанную тему из списка, используй формат [[Название статьи]].
Статья должна быть полезной как учебный материал, а не как протокол встречи.

Required Markdown shape:
# {article.get("title", "")}

## {labels.article_summary}
{summary_instruction}

## {labels.article_why}

## {labels.article_core_ideas}

## {labels.article_practices}

## {labels.article_mistakes}

## {labels.article_related}

## {labels.sources}
{source_format_intro}
- video_id/chunk_id start-end

KNOWN_ARTICLE_TITLES:
{known_links}

SOURCE_PACK:
{json.dumps(source_pack, ensure_ascii=False, indent=2)}
"""


def read_article_pages(raw_data: Path) -> list[dict[str, Any]]:
    path = raw_data / "article_plan" / "pages.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def select_source_packs(
    raw_data: Path,
    pages: list[dict[str, Any]],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")

    selected_pages = pages[:limit] if limit is not None else pages
    packs: list[dict[str, Any]] = []
    for page in selected_pages:
        path = raw_data / "article_plan" / "source_packs" / f"{page['slug']}.json"
        if path.exists():
            packs.append(json.loads(path.read_text(encoding="utf-8")))
    return packs


def draft_output_path(raw_data: Path, slug: str) -> Path:
    return raw_data / "draft_articles" / f"{slug}.md"


def draft_article(
    raw_data: Path,
    source_pack: dict[str, Any],
    client: ArticleClient,
    known_titles: list[str],
    force: bool = False,
) -> DraftArticleResult:
    article = source_pack["article"]
    output_path = draft_output_path(raw_data, str(article["slug"]))
    if output_path.exists() and output_path.stat().st_size > 0 and not force:
        return DraftArticleResult(output_path=output_path, skipped=True)

    markdown = client.draft(source_pack, known_titles)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return DraftArticleResult(output_path=output_path, skipped=False)


def count_draft_articles(raw_data: Path) -> int:
    output_dir = raw_data / "draft_articles"
    if not output_dir.exists():
        return 0
    return sum(1 for path in output_dir.glob("*.md") if path.is_file() and path.stat().st_size > 0)
