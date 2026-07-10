from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import time
from typing import Any, Callable
from urllib import error, request
from urllib.parse import quote, urlencode


def build_system_prompt(output_language: str = "ru") -> str:
    return f"""Ты извлекаешь знания из транскрипта тренинга для создания Obsidian wiki.

Твоя задача НЕ пересказать транскрипт.
Твоя задача извлечь только полезные, проверяемые единицы знания:
- темы
- практические советы
- ошибки
- термины
- вопросы и ответы
- кандидаты в wiki-страницы

Используй только информацию из данного фрагмента.
Не добавляй внешние знания.
Если фрагмент пустой, шумный или не содержит полезного знания, верни пустые массивы.
Пиши результат на языке: {output_language}.
Сохраняй технические термины на английском, если так естественнее.
Не выдумывай факты, примеры, технологии или причинно-следственные связи.
Каждый элемент должен быть связан с source timestamp через общий объект source.
Ответь только валидным JSON, соответствующим схеме."""


SYSTEM_PROMPT = build_system_prompt()


KNOWLEDGE_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "name": "training_chunk_knowledge",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "source": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "video_id": {"type": "string"},
                    "chunk_id": {"type": "string"},
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                },
                "required": ["video_id", "chunk_id", "start", "end"],
            },
            "chunk_title": {"type": "string"},
            "detected_domain": {"type": "string"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "why_low_confidence": {"type": "string"},
            "summary": {"type": "string"},
            "topics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["name", "description", "evidence"],
                },
            },
            "practices": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "claim": {"type": "string"},
                        "why_it_matters": {"type": "string"},
                        "action_items": {"type": "array", "items": {"type": "string"}},
                        "evidence": {"type": "string"},
                    },
                    "required": ["title", "claim", "why_it_matters", "action_items", "evidence"],
                },
            },
            "mistakes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "correction": {"type": "string"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["title", "description", "correction", "evidence"],
                },
            },
            "terms": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "term": {"type": "string"},
                        "definition": {"type": "string"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["term", "definition", "evidence"],
                },
            },
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "question": {"type": "string"},
                        "answer": {"type": "string"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["question", "answer", "evidence"],
                },
            },
            "wiki_candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "reason": {"type": "string"},
                        "suggested_section": {"type": "string"},
                    },
                    "required": ["title", "reason", "suggested_section"],
                },
            },
            "notable_quotes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "quote": {"type": "string"},
                        "why_notable": {"type": "string"},
                    },
                    "required": ["quote", "why_notable"],
                },
            },
        },
        "required": [
            "source",
            "chunk_title",
            "detected_domain",
            "confidence",
            "why_low_confidence",
            "summary",
            "topics",
            "practices",
            "mistakes",
            "terms",
            "questions",
            "wiki_candidates",
            "notable_quotes",
        ],
    },
}


Transport = Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]]


def validate_api_key(
    api_key: str,
    api_key_env: str = "OPENAI_API_KEY",
    provider: str = "LLM provider",
) -> str:
    cleaned = api_key.strip()
    if not cleaned:
        raise RuntimeError(f"Missing API key for {provider}. Set {api_key_env} in your shell or .env.")
    if any(char.isspace() for char in cleaned):
        raise RuntimeError(
            f"Invalid {api_key_env} for {provider}: remove spaces or line breaks from the key."
        )
    try:
        cleaned.encode("ascii")
    except UnicodeEncodeError as exc:
        raise RuntimeError(
            f"Invalid {api_key_env} for {provider}: use an ASCII API key."
        ) from exc

    lowered = cleaned.lower()
    placeholder_markers = ("your-new-key", "your_new_key", "placeholder", "example")
    if any(marker in lowered for marker in placeholder_markers):
        raise RuntimeError(
            f"Invalid {api_key_env} for {provider}: replace the placeholder with a real API key."
        )
    return cleaned


def validate_openai_api_key(api_key: str, api_key_env: str = "OPENAI_API_KEY") -> str:
    return validate_api_key(api_key, api_key_env=api_key_env, provider="openai")


@dataclass(frozen=True)
class KnowledgeExtractionResult:
    output_path: Path
    skipped: bool


class OpenAIKnowledgeClient:
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
    ) -> "OpenAIKnowledgeClient":
        api_key = os.environ.get(api_key_env)
        if api_key is None:
            raise RuntimeError(f"Missing API key. Set {api_key_env} in your shell or .env.")
        validate_openai_api_key(api_key, api_key_env)
        return cls(api_key=api_key, model=model, output_language=output_language, endpoint=endpoint)

    def extract(self, chunk: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": build_system_prompt(self.output_language)},
                {
                    "role": "user",
                    "content": build_extraction_prompt(
                        chunk,
                        output_language=self.output_language,
                    ),
                },
            ],
            "text": {"format": KNOWLEDGE_SCHEMA},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = self.transport(self.endpoint, headers, payload)
        return parse_response_output(response)


class AnthropicKnowledgeClient:
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
    ) -> "AnthropicKnowledgeClient":
        api_key = os.environ.get(api_key_env)
        if api_key is None:
            raise RuntimeError(f"Missing API key for anthropic. Set {api_key_env} in your shell or .env.")
        validate_api_key(api_key, api_key_env=api_key_env, provider="anthropic")
        return cls(api_key=api_key, model=model, output_language=output_language, endpoint=endpoint)

    def extract(self, chunk: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": build_system_prompt(self.output_language),
            "messages": [
                {
                    "role": "user",
                    "content": build_extraction_prompt(
                        chunk,
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
        return json.loads(parse_anthropic_text(response))


class GeminiKnowledgeClient:
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
    ) -> "GeminiKnowledgeClient":
        api_key = os.environ.get(api_key_env)
        if api_key is None:
            raise RuntimeError(f"Missing API key for gemini. Set {api_key_env} in your shell or .env.")
        validate_api_key(api_key, api_key_env=api_key_env, provider="gemini")
        return cls(api_key=api_key, model=model, output_language=output_language, endpoint=endpoint)

    def extract(self, chunk: dict[str, Any]) -> dict[str, Any]:
        prompt = "\n\n".join(
            [
                build_system_prompt(self.output_language),
                build_extraction_prompt(chunk, output_language=self.output_language),
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
        return json.loads(parse_gemini_text(response))


TRANSIENT_HTTP_CODES = {408, 429, 500, 502, 503, 504}


def default_transport(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method="POST")
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            with request.urlopen(req, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code not in TRANSIENT_HTTP_CODES or attempt == max_attempts:
                raise RuntimeError(f"LLM provider API error {exc.code}: {body}") from exc
            time.sleep(2 ** (attempt - 1))
        except error.URLError as exc:
            if attempt == max_attempts:
                raise RuntimeError(f"LLM provider network error: {exc.reason}") from exc
            time.sleep(2 ** (attempt - 1))
        except ValueError as exc:
            raise RuntimeError("Invalid LLM provider request. Check configured API key formatting.") from exc

    raise RuntimeError("LLM provider request failed after retries.")


def parse_response_output(response: dict[str, Any]) -> dict[str, Any]:
    if "output_text" in response:
        return json.loads(str(response["output_text"]))

    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and "text" in content:
                return json.loads(str(content["text"]))

    raise ValueError("OpenAI response did not contain output text.")


def parse_anthropic_text(response: dict[str, Any]) -> str:
    text = "".join(
        str(content["text"])
        for content in response.get("content", [])
        if content.get("type") == "text" and "text" in content
    )
    if text:
        return text
    raise ValueError("Anthropic response did not contain text content.")


def parse_gemini_text(response: dict[str, Any]) -> str:
    parts: list[str] = []
    for candidate in response.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            if "text" in part:
                parts.append(str(part["text"]))
    if parts:
        return "".join(parts)
    raise ValueError("Gemini response did not contain text content.")


def gemini_url(endpoint: str, model: str, api_key: str) -> str:
    url = endpoint.replace("{model}", quote(model, safe=""))
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode({'key': api_key})}"


def build_extraction_prompt(chunk: dict[str, Any], output_language: str = "ru") -> str:
    return f"""SOURCE:
VIDEO_ID: {chunk["video_id"]}
ORIGINAL_VIDEO_TITLE: {chunk.get("title", "")}
CHUNK_ID: {chunk["chunk_id"]}
TIME_RANGE: {chunk.get("start_hms", "")}-{chunk.get("end_hms", "")}

Important:
Название видео может быть техническим, неполным или неинформативным.
Не используй название видео для вывода тем.
Определяй темы, практики, ошибки, термины и wiki-кандидаты только из TRANSCRIPT.

Extraction rules:
- output_language: write extracted knowledge in {output_language}.
- chunk_title: короткое человеческое название этого фрагмента.
- detected_domain: область знания, например CV, Interview, Architecture, AWS, Scrum, Career.
- confidence: high, если фрагмент содержательный; medium, если есть шум; low, если мало полезного знания.
- why_low_confidence: пустая строка, если confidence не low.
- summary: 2-4 предложения без внешних фактов.
- topics: шире собирай возможные темы, но evidence бери только из текста.
- practices/mistakes/terms/questions: заполняй только если это явно есть в тексте.
- wiki_candidates: предлагай страницы, которые позже можно объединить в учебник.
- notable_quotes: только короткие цитаты, если они действительно полезны.

TRANSCRIPT:
{chunk.get("text", "")}
"""


def chunk_payloads(raw_data: Path) -> list[dict[str, Any]]:
    chunk_dir = raw_data / "chunks"
    payloads: list[dict[str, Any]] = []
    if not chunk_dir.exists():
        return payloads

    for path in sorted(chunk_dir.glob("*/*.json"), key=lambda item: (item.parent.name, item.name)):
        payloads.append(json.loads(path.read_text(encoding="utf-8")))
    return payloads


def select_chunk_payloads(
    payloads: list[dict[str, Any]],
    limit: int | None = None,
    sample_per_video: int | None = None,
) -> list[dict[str, Any]]:
    selected = payloads

    if sample_per_video is not None:
        if sample_per_video <= 0:
            raise ValueError("sample_per_video must be positive")

        counts_by_video: dict[str, int] = {}
        sampled: list[dict[str, Any]] = []
        for payload in payloads:
            video_id = str(payload["video_id"])
            count = counts_by_video.get(video_id, 0)
            if count >= sample_per_video:
                continue
            sampled.append(payload)
            counts_by_video[video_id] = count + 1
        selected = sampled

    if limit is not None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        selected = selected[:limit]

    return selected


def knowledge_output_path(raw_data: Path, video_id: str, chunk_id: str) -> Path:
    return raw_data / "extracted_knowledge" / video_id / f"{chunk_id}.json"


def extract_chunk_knowledge(
    raw_data: Path,
    chunk: dict[str, Any],
    client: OpenAIKnowledgeClient,
    force: bool = False,
) -> KnowledgeExtractionResult:
    output_path = knowledge_output_path(raw_data, str(chunk["video_id"]), str(chunk["chunk_id"]))
    if output_path.exists() and output_path.stat().st_size > 0 and not force:
        return KnowledgeExtractionResult(output_path=output_path, skipped=True)

    knowledge = client.extract(chunk)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(knowledge, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return KnowledgeExtractionResult(output_path=output_path, skipped=False)


def count_existing_knowledge(raw_data: Path) -> int:
    output_dir = raw_data / "extracted_knowledge"
    if not output_dir.exists():
        return 0
    return sum(1 for path in output_dir.glob("*/*.json") if path.is_file() and path.stat().st_size > 0)
