from __future__ import annotations

from media_to_wiki_convertor.config import LLMConfig
from media_to_wiki_convertor.draft_articles import OpenAIArticleClient
from media_to_wiki_convertor.knowledge import OpenAIKnowledgeClient


SUPPORTED_PROVIDERS = ("openai", "openai-compatible")


class UnsupportedLLMProviderError(RuntimeError):
    pass


def create_knowledge_client(config: LLMConfig, output_language: str) -> OpenAIKnowledgeClient:
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
    raise_unsupported_provider(config.provider)


def create_article_client(config: LLMConfig, output_language: str) -> OpenAIArticleClient:
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
    raise_unsupported_provider(config.provider)


def raise_unsupported_provider(provider: str):
    supported = ", ".join(SUPPORTED_PROVIDERS)
    raise UnsupportedLLMProviderError(
        f"Unsupported LLM provider: {provider}. Supported providers: {supported}."
    )
