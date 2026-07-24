"""Optional LangChain structured-output adapter for answer suggestions.

This module provides a stable integration point for a future LangChain
adapter. When LangChain is not installed (the current state), the adapter
raises ``LangChainUnavailableError`` so the caller can fall back to rules.

When LangChain is added later, only ``_invoke_model`` and ``is_available``
need to be implemented — the validation and fallback logic stays unchanged.

Safety contract:
- All model output must pass through ``validate_answer_suggestion_payload``.
- The prompt instructs the model: suggest only, never execute actions,
  never invent source_ids, never output sensitive values.
- On any error, the caller falls back to rules — the demo never breaks.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.suggestion_types import (
    AnswerSuggestion,
    validate_answer_suggestion_payload,
)

logger = logging.getLogger(__name__)


class LangChainUnavailableError(RuntimeError):
    """Raised when LangChain is not installed or not configured."""


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------


def is_available() -> bool:
    """Return True if LangChain is installed and an API key is configured."""

    try:
        import langchain  # noqa: F401
    except ImportError:
        return False

    from app import config

    return bool(
        getattr(config, "OPENAI_API_KEY", None)
        or getattr(config, "GEMINI_API_KEY", None)
        or getattr(config, "DEEPSEEK_API_KEY", None)
    )


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a security questionnaire answer suggestion assistant. "
    "For each question, return a JSON object matching the AnswerSuggestion schema. "
    "Rules:\n"
    "1. Only suggest values backed by provided profile data, memory hits, or policy evidence.\n"
    "2. Never invent source_ids or memory_ids — only use IDs from the input context.\n"
    "3. Never output sensitive values (passwords, OTPs, payment data, API keys).\n"
    "4. If no evidence supports an answer, set answer_status to 'unsupported' and suggested_value to null.\n"
    "5. Do not execute browser actions, clicks, or submissions.\n"
    "6. Output only the JSON array of suggestions."
)


# ---------------------------------------------------------------------------
# Internal model invocation (stub for future LangChain integration)
# ---------------------------------------------------------------------------


def _invoke_model(input_payload: dict[str, object]) -> list[dict[str, object]]:
    """Call the LLM and return raw suggestion dicts.

    This is the single integration point for LangChain. When LangChain is
    installed, replace the body with a structured-output chain call.
    """

    raise LangChainUnavailableError(
        "LangChain is not installed. Install langchain and configure an API key "
        "to use LLM-powered suggestions."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def suggest_answers_with_langchain(
    input_payload: dict[str, object],
) -> list[AnswerSuggestion]:
    """Generate suggestions using LangChain structured output.

    Parameters
    ----------
    input_payload:
        A dict containing ``questions``, ``profile``, ``memory_hits``,
        and ``policy_sources`` keys for the LLM prompt context.

    Returns
    -------
    list[AnswerSuggestion]
        Validated suggestions — every item passes schema validation.

    Raises
    ------
    LangChainUnavailableError
        When LangChain is not installed or no API key is configured.
        Callers should catch this and fall back to rules mode.
    """

    if not is_available():
        raise LangChainUnavailableError(
            "LangChain structured output is not available. "
            "Falling back to rules mode."
        )

    raw_items = _invoke_model(input_payload)

    suggestions: list[AnswerSuggestion] = []
    for raw in raw_items:
        try:
            suggestion = validate_answer_suggestion_payload(raw)
        except ValueError as exc:
            logger.warning(
                "LangChain output failed schema validation, skipping: %s", exc
            )
            continue
        suggestions.append(suggestion)

    return suggestions
