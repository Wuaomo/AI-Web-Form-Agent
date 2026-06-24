"""Configuration helpers for selectable LLM providers."""

from typing import cast

from app import config
from app.schemas import LLMProvider


def _normalize_provider(provider: str | None) -> str:
    return (provider or config.LLM_PROVIDER).strip().lower()


def resolve_llm_provider(provider: str | None = None) -> LLMProvider:
    """Return a supported provider id or raise a clear configuration error."""

    selected = _normalize_provider(provider)
    if selected not in config.LLM_PROVIDER_DETAILS:
        supported = ", ".join(config.LLM_PROVIDER_DETAILS)
        raise ValueError(
            f"Unsupported LLM provider '{selected}'. Use one of: {supported}."
        )
    return cast(LLMProvider, selected)


def get_provider_model(provider: LLMProvider) -> str:
    """Return the configured model name for a provider."""

    return str(getattr(config, f"{provider.upper()}_MODEL"))


def get_provider_api_key(provider: LLMProvider) -> str | None:
    """Return the configured API key for a provider, if present."""

    return getattr(config, f"{provider.upper()}_API_KEY")


def is_provider_configured(provider: LLMProvider) -> bool:
    """Return whether the selected provider has the required API key."""

    return bool(get_provider_api_key(provider))


def get_provider_setup_hint(provider: LLMProvider) -> str:
    """Return a concise user-facing setup hint for the provider."""

    details = config.LLM_PROVIDER_DETAILS[provider]
    alias_envs = details.get("api_key_alias_envs", [])
    alias_hint = (
        f" Alias also supported: {', '.join(alias_envs)}."
        if alias_envs
        else ""
    )
    return (
        f"Set {details['api_key_env']} before starting the backend. "
        f"Optionally set {details['model_env']} to change the model."
        f"{alias_hint}"
    )


def list_llm_providers() -> list[dict[str, object]]:
    """Return all selectable providers and their readiness state."""

    selected_provider = _normalize_provider(None)
    providers: list[dict[str, object]] = []
    for provider, details in config.LLM_PROVIDER_DETAILS.items():
        provider_id = resolve_llm_provider(provider)
        providers.append(
            {
                "id": provider_id,
                "display_name": details["display_name"],
                "model": get_provider_model(provider_id),
                "model_env": details["model_env"],
                "api_key_env": details["api_key_env"],
                "configured": is_provider_configured(provider_id),
                "selected": provider_id == selected_provider,
                "setup_hint": get_provider_setup_hint(provider_id),
            }
        )
    return providers
