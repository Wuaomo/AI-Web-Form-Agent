"""Tests for environment-backed application configuration."""

import importlib

from app import config


def test_default_llm_provider_is_deepseek(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    reloaded_config = importlib.reload(config)

    try:
        assert reloaded_config.LLM_PROVIDER == "deepseek"
    finally:
        importlib.reload(config)


def test_deepseek_api_key_accepts_legacy_alias(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEKAPI", "alias-key")

    reloaded_config = importlib.reload(config)

    try:
        assert reloaded_config.DEEPSEEK_API_KEY == "alias-key"
    finally:
        importlib.reload(config)
