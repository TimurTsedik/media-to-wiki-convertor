from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Callable, Protocol

from media_to_wiki_convertor.knowledge import default_transport, validate_openai_api_key


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
    ) -> "OpenAIArticleClient":
        api_key = os.environ.get(api_key_env)
        if api_key is None:
            raise RuntimeError(f"Missing API key. Set {api_key_env} in your shell or .env.")
        validate_openai_api_key(api_key, api_key_env)
        return cls(api_key=api_key, model=model, output_language=output_language)

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
    known_links = "\n".join(f"- [[{title}]]" for title in known_titles)
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

## Коротко
2-4 предложения.

## Зачем это важно

## Основные идеи

## Практики

## Типичные ошибки

## Связанные темы

## Источники
Список источников в формате:
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
