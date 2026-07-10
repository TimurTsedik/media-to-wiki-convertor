from __future__ import annotations

from media_to_wiki_convertor.config import (
    LLMConfig,
    default_llm_api_key_env,
    default_llm_base_url,
)
from media_to_wiki_convertor.course_materials import (
    DEFAULT_MAX_CHUNK_CHARS,
    DEFAULT_MAX_PROMPT_TOPICS,
    AnthropicCourseMaterialClient,
    GeminiCourseMaterialClient,
    OpenAICourseMaterialClient,
)
from media_to_wiki_convertor.draft_articles import (
    AnthropicArticleClient,
    GeminiArticleClient,
    OpenAIArticleClient,
)
from media_to_wiki_convertor.knowledge import (
    AnthropicKnowledgeClient,
    GeminiKnowledgeClient,
    OpenAIKnowledgeClient,
)


SUPPORTED_PROVIDERS = ("openai", "openai-compatible", "anthropic", "gemini")


class UnsupportedLLMProviderError(RuntimeError):
    pass


def create_knowledge_client(
    config: LLMConfig,
    output_language: str,
) -> OpenAIKnowledgeClient | AnthropicKnowledgeClient | GeminiKnowledgeClient:
    if config.provider == "openai":
        return OpenAIKnowledgeClient.from_env(
            model=config.model,
            output_language=output_language,
        )
    if config.provider == "openai-compatible":
        return OpenAIKnowledgeClient.from_env(
            model=config.model,
            output_language=output_language,
            api_key_env=config.api_key_env,
            endpoint=config.base_url,
        )
    if config.provider == "anthropic":
        return AnthropicKnowledgeClient.from_env(
            model=config.model,
            output_language=output_language,
            api_key_env=config.api_key_env or default_llm_api_key_env(config.provider),
            endpoint=config.base_url or default_llm_base_url(config.provider),
        )
    if config.provider == "gemini":
        return GeminiKnowledgeClient.from_env(
            model=config.model,
            output_language=output_language,
            api_key_env=config.api_key_env or default_llm_api_key_env(config.provider),
            endpoint=config.base_url or default_llm_base_url(config.provider),
        )
    raise_unsupported_provider(config.provider)


def create_article_client(
    config: LLMConfig,
    output_language: str,
) -> OpenAIArticleClient | AnthropicArticleClient | GeminiArticleClient:
    if config.provider == "openai":
        return OpenAIArticleClient.from_env(
            model=config.model,
            output_language=output_language,
        )
    if config.provider == "openai-compatible":
        return OpenAIArticleClient.from_env(
            model=config.model,
            output_language=output_language,
            api_key_env=config.api_key_env,
            endpoint=config.base_url,
        )
    if config.provider == "anthropic":
        return AnthropicArticleClient.from_env(
            model=config.model,
            output_language=output_language,
            api_key_env=config.api_key_env or default_llm_api_key_env(config.provider),
            endpoint=config.base_url or default_llm_base_url(config.provider),
        )
    if config.provider == "gemini":
        return GeminiArticleClient.from_env(
            model=config.model,
            output_language=output_language,
            api_key_env=config.api_key_env or default_llm_api_key_env(config.provider),
            endpoint=config.base_url or default_llm_base_url(config.provider),
        )
    raise_unsupported_provider(config.provider)


def create_course_material_client(
    config: LLMConfig,
    output_language: str,
    max_topics: int = DEFAULT_MAX_PROMPT_TOPICS,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> OpenAICourseMaterialClient | AnthropicCourseMaterialClient | GeminiCourseMaterialClient:
    if config.provider == "openai":
        return OpenAICourseMaterialClient.from_env(
            model=config.model,
            output_language=output_language,
            max_topics=max_topics,
            max_chunk_chars=max_chunk_chars,
        )
    if config.provider == "openai-compatible":
        return OpenAICourseMaterialClient.from_env(
            model=config.model,
            output_language=output_language,
            api_key_env=config.api_key_env,
            endpoint=config.base_url,
            max_topics=max_topics,
            max_chunk_chars=max_chunk_chars,
        )
    if config.provider == "anthropic":
        return AnthropicCourseMaterialClient.from_env(
            model=config.model,
            output_language=output_language,
            api_key_env=config.api_key_env or default_llm_api_key_env(config.provider),
            endpoint=config.base_url or default_llm_base_url(config.provider),
            max_topics=max_topics,
            max_chunk_chars=max_chunk_chars,
        )
    if config.provider == "gemini":
        return GeminiCourseMaterialClient.from_env(
            model=config.model,
            output_language=output_language,
            api_key_env=config.api_key_env or default_llm_api_key_env(config.provider),
            endpoint=config.base_url or default_llm_base_url(config.provider),
            max_topics=max_topics,
            max_chunk_chars=max_chunk_chars,
        )
    raise_unsupported_provider(config.provider)


def raise_unsupported_provider(provider: str):
    supported = ", ".join(SUPPORTED_PROVIDERS)
    raise UnsupportedLLMProviderError(
        f"Unsupported LLM provider: {provider}. Supported providers: {supported}."
    )
