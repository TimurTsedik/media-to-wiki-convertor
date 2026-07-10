from __future__ import annotations

from media_to_wiki_convertor.config import LLMConfig
from media_to_wiki_convertor.draft_articles import OpenAIArticleClient
from media_to_wiki_convertor.knowledge import OpenAIKnowledgeClient
from media_to_wiki_convertor.llm_clients import (
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


def test_factory_rejects_unsupported_provider_with_clear_error() -> None:
    try:
        create_knowledge_client(
            LLMConfig(provider="anthropic", model="claude-test"),
            output_language="en",
        )
    except UnsupportedLLMProviderError as exc:
        message = str(exc)
        assert "Unsupported LLM provider: anthropic" in message
        assert "openai" in message
        assert "openai-compatible" in message
    else:
        raise AssertionError("unsupported provider was accepted")
