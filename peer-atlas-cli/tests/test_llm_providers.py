"""Tests for LLM provider registration and client instantiation."""

from __future__ import annotations

from peer_atlas_cli.llm_client import (
    PROVIDERS,
    AnthropicClient,
    GeminiClient,
    OpenAICompatibleClient,
    get_client,
)


def test_all_providers_registered() -> None:
    assert "openai" in PROVIDERS
    assert "anthropic" in PROVIDERS
    assert "gemini" in PROVIDERS


def test_provider_types() -> None:
    assert PROVIDERS["openai"] is OpenAICompatibleClient
    assert PROVIDERS["anthropic"] is AnthropicClient
    assert PROVIDERS["gemini"] is GeminiClient


def test_openai_client_instantiates() -> None:
    c = OpenAICompatibleClient(api_key="test", model="gpt-4o")
    assert c._model == "gpt-4o"
    assert "api.openai.com" in c._base


def test_anthropic_client_instantiates() -> None:
    c = AnthropicClient(api_key="sk-ant-test", model="claude-sonnet-4-6")
    assert c._model == "claude-sonnet-4-6"
    assert "api.anthropic.com" in c._base


def test_anthropic_client_custom_base_url() -> None:
    c = AnthropicClient(api_key="key", model="m", base_url="https://proxy.example.com")
    assert c._base == "https://proxy.example.com"


def test_gemini_client_instantiates() -> None:
    c = GeminiClient(api_key="AIza-test", model="gemini-2.0-flash")
    assert c._model == "gemini-2.0-flash"
    assert "generativelanguage.googleapis.com" in c._base


def test_gemini_client_is_openai_compatible_subclass() -> None:
    assert issubclass(GeminiClient, OpenAICompatibleClient)


def test_gemini_client_custom_base_url() -> None:
    c = GeminiClient(api_key="key", model="m", base_url="https://custom.example.com")
    assert c._base == "https://custom.example.com"


def test_get_client_openai() -> None:
    c = get_client("openai", api_key="k", model="gpt-4o", base_url=None)
    assert isinstance(c, OpenAICompatibleClient)


def test_get_client_anthropic() -> None:
    c = get_client("anthropic", api_key="k", model="claude-sonnet-4-6", base_url=None)
    assert isinstance(c, AnthropicClient)


def test_get_client_gemini() -> None:
    c = get_client("gemini", api_key="k", model="gemini-2.0-flash", base_url=None)
    assert isinstance(c, GeminiClient)


def test_get_client_case_insensitive() -> None:
    c = get_client("ANTHROPIC", api_key="k", model="m", base_url=None)
    assert isinstance(c, AnthropicClient)


def test_get_client_unknown_provider_exits() -> None:
    import pytest
    with pytest.raises(SystemExit):
        get_client("unknown_provider", api_key="k", model="m", base_url=None)
