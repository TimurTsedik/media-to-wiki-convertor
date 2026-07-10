from __future__ import annotations

from media_to_wiki_convertor.config import LLMConfig, default_llm_api_key_env, default_llm_base_url
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
from media_to_wiki_convertor.llm_clients import (
    SUPPORTED_PROVIDERS,
    UnsupportedLLMProviderError,
    create_article_client,
    create_knowledge_client,
)


def test_factory_creates_openai_knowledge_client_from_default_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")

    client = create_knowledge_client(
        LLMConfig(provider="openai", model="gpt-test"),
        output_language="en",
    )

    assert isinstance(client, OpenAIKnowledgeClient)
    assert client.model == "gpt-test"
    assert client.output_language == "en"
    assert client.endpoint == "https://api.openai.com/v1/responses"


def test_factory_creates_responses_compatible_clients_with_custom_endpoint_and_env(monkeypatch) -> None:
    monkeypatch.setenv("CUSTOM_API_KEY", "compatible-secret")
    config = LLMConfig(
        provider="openai-compatible",
        model="compatible-model",
        base_url="https://llm.example.test/v1/responses",
        api_key_env="CUSTOM_API_KEY",
    )

    knowledge_client = create_knowledge_client(config, output_language="en")
    article_client = create_article_client(config, output_language="en")

    assert isinstance(knowledge_client, OpenAIKnowledgeClient)
    assert isinstance(article_client, OpenAIArticleClient)
    assert knowledge_client.endpoint == "https://llm.example.test/v1/responses"
    assert article_client.endpoint == "https://llm.example.test/v1/responses"
    assert knowledge_client.api_key == "compatible-secret"
    assert article_client.api_key == "compatible-secret"


def test_factory_creates_anthropic_clients_from_default_env(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    config = LLMConfig(
        provider="anthropic",
        model="claude-test",
        base_url=default_llm_base_url("anthropic"),
        api_key_env=default_llm_api_key_env("anthropic"),
    )

    knowledge_client = create_knowledge_client(config, output_language="en")
    article_client = create_article_client(config, output_language="en")

    assert isinstance(knowledge_client, AnthropicKnowledgeClient)
    assert isinstance(article_client, AnthropicArticleClient)
    assert knowledge_client.endpoint == "https://api.anthropic.com/v1/messages"
    assert article_client.endpoint == "https://api.anthropic.com/v1/messages"
    assert knowledge_client.api_key == "anthropic-secret"
    assert article_client.api_key == "anthropic-secret"


def test_factory_creates_gemini_clients_from_default_env(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    config = LLMConfig(
        provider="gemini",
        model="gemini-test",
        base_url=default_llm_base_url("gemini"),
        api_key_env=default_llm_api_key_env("gemini"),
    )

    knowledge_client = create_knowledge_client(config, output_language="en")
    article_client = create_article_client(config, output_language="en")

    assert isinstance(knowledge_client, GeminiKnowledgeClient)
    assert isinstance(article_client, GeminiArticleClient)
    assert knowledge_client.endpoint == (
        "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    )
    assert article_client.endpoint == (
        "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    )
    assert knowledge_client.api_key == "gemini-secret"
    assert article_client.api_key == "gemini-secret"


def test_factory_rejects_unsupported_provider_with_clear_error() -> None:
    try:
        create_knowledge_client(
            LLMConfig(provider="unknown-provider", model="model-test"),
            output_language="en",
        )
    except UnsupportedLLMProviderError as exc:
        message = str(exc)
        assert "Unsupported LLM provider: unknown-provider" in message
        for provider in SUPPORTED_PROVIDERS:
            assert provider in message
    else:
        raise AssertionError("unsupported provider was accepted")
