"""Tests for environment-backed application configuration."""

import importlib

from app import config


def test_deepseek_api_key_accepts_legacy_alias(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEKAPI", "alias-key")

    reloaded_config = importlib.reload(config)

    try:
        assert reloaded_config.DEEPSEEK_API_KEY == "alias-key"
    finally:
        importlib.reload(config)
