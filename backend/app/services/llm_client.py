"""LLM Client Boundary - A thin layer between business services and LLM providers.

Provides a minimal, stable interface for LLM interactions while hiding
provider-specific SDK details. Supports graceful fallback when LLM is unavailable
or returns invalid output.

Methods:
    complete_json: Request structured JSON output with schema validation
    summarize: Request text summarization
    classify: Request text classification/categorization
    suggest_mapping: Request form field mapping suggestions

All methods return standardized LLMResult objects that include:
    - success: Whether the call succeeded
    - content: The parsed result (dict for JSON, str for text)
    - raw_response: The raw LLM response string
    - usage: Token usage and cost metadata
    - fallback_used: Whether a fallback was triggered
    - error_type: Error type if failed
    - reason: Human-readable reason for outcome
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import config
from app.schemas import LLMProvider
from app.services.llm_provider_config import (
    resolve_llm_provider,
    is_provider_configured,
    get_provider_model,
    get_provider_api_key,
)
from app.services.llm_usage_service import record_llm_api_usage
from app.services.llm_cost_service import estimate_llm_cost

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMUsage:
    """Normalized LLM usage metrics."""

    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    latency_ms: int = 0
    estimated_cost: float = 0.0


@dataclass(frozen=True)
class LLMResult:
    """Standardized result from an LLM call."""

    success: bool
    content: Any
    raw_response: str = ""
    usage: LLMUsage | None = None
    fallback_used: bool = False
    error_type: str | None = None
    reason: str = ""


class LLMClient:
    """Thin LLM client boundary that abstracts provider-specific details."""

    def __init__(self, provider: LLMProvider | None = None):
        self.provider = provider

    def _resolve_provider(self) -> LLMProvider:
        """Resolve and return the selected LLM provider."""
        return resolve_llm_provider(self.provider)

    def _is_available(self) -> bool:
        """Check if the selected provider is configured and available."""
        try:
            provider = self._resolve_provider()
            return is_provider_configured(provider)
        except (ValueError, RuntimeError):
            return False

    def complete_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        task_id: int | None = None,
        db: Session | None = None,
    ) -> LLMResult:
        """Request structured JSON output validated against a schema.

        Args:
            prompt: The input prompt for the LLM
            schema: JSON schema to validate the response against
            task_id: Optional task ID for usage tracking
            db: Optional database session for usage logging

        Returns:
            LLMResult with parsed dict content if successful, or fallback result.
        """

        if not self._is_available():
            return self._create_unavailable_fallback("complete_json")

        start_time = time.perf_counter()
        provider = self._resolve_provider()
        model = get_provider_model(provider)

        try:
            raw_response = self._call_provider(
                provider=provider,
                model=model,
                prompt=prompt,
                response_format="json",
                schema=schema,
                task_id=task_id,
                db=db,
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Validate JSON
            parsed = self._parse_and_validate_json(raw_response, schema)

            usage = self._extract_usage(provider, model, raw_response, latency_ms)
            # Note: Usage recording is handled by the caller (e.g., field_mapper)
            # to avoid duplicate logging

            return LLMResult(
                success=True,
                content=parsed,
                raw_response=raw_response,
                usage=usage,
                reason="JSON completion successful",
            )

        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            error_type = type(exc).__name__

            usage = LLMUsage(
                provider=provider,
                model=model,
                latency_ms=latency_ms,
            )
            # Note: Usage recording is handled by the caller (e.g., field_mapper)
            # to avoid duplicate logging

            logger.warning("LLM complete_json failed: %s", exc)
            return LLMResult(
                success=False,
                content=None,
                raw_response="",
                usage=usage,
                fallback_used=True,
                error_type=error_type,
                reason=str(exc),
            )

    def summarize(
        self,
        text: str,
        *,
        task_id: int | None = None,
        db: Session | None = None,
    ) -> LLMResult:
        """Request a concise summary of the given text."""

        if not self._is_available():
            return LLMResult(
                success=False,
                content="",
                raw_response="",
                usage=None,
                fallback_used=True,
                error_type="LLM_UNAVAILABLE",
                reason="LLM provider not configured or unavailable",
            )

        start_time = time.perf_counter()
        provider = self._resolve_provider()
        model = get_provider_model(provider)

        try:
            prompt = f"""Summarize this text concisely in 3-5 sentences:

{text}

Summary:"""

            raw_response = self._call_provider(
                provider=provider,
                model=model,
                prompt=prompt,
                response_format="text",
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            usage = self._extract_usage(provider, model, raw_response, latency_ms)
            self._record_usage(task_id, db, usage)

            return LLMResult(
                success=True,
                content=raw_response.strip(),
                raw_response=raw_response,
                usage=usage,
                reason="Summarization successful",
            )

        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            error_type = type(exc).__name__

            usage = LLMUsage(
                provider=provider,
                model=model,
                latency_ms=latency_ms,
            )
            self._record_failure_usage(task_id, db, usage, error_type)

            logger.warning("LLM summarize failed: %s", exc)
            return LLMResult(
                success=False,
                content="",
                raw_response="",
                usage=usage,
                fallback_used=True,
                error_type=error_type,
                reason=str(exc),
            )

    def classify(
        self,
        text: str,
        categories: list[str],
        *,
        task_id: int | None = None,
        db: Session | None = None,
    ) -> LLMResult:
        """Classify text into one of the given categories."""

        if not self._is_available():
            return LLMResult(
                success=False,
                content="UNKNOWN",
                raw_response="",
                usage=None,
                fallback_used=True,
                error_type="LLM_UNAVAILABLE",
                reason="LLM provider not configured or unavailable",
            )

        start_time = time.perf_counter()
        provider = self._resolve_provider()
        model = get_provider_model(provider)

        try:
            prompt = f"""Classify this text into one of these categories: {', '.join(categories)}

Text: {text}

Category:"""

            raw_response = self._call_provider(
                provider=provider,
                model=model,
                prompt=prompt,
                response_format="text",
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            usage = self._extract_usage(provider, model, raw_response, latency_ms)
            self._record_usage(task_id, db, usage)

            category = raw_response.strip()
            if category not in categories:
                category = "UNKNOWN"

            return LLMResult(
                success=True,
                content=category,
                raw_response=raw_response,
                usage=usage,
                reason=f"Classification successful: {category}",
            )

        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            error_type = type(exc).__name__

            usage = LLMUsage(
                provider=provider,
                model=model,
                latency_ms=latency_ms,
            )
            self._record_failure_usage(task_id, db, usage, error_type)

            logger.warning("LLM classify failed: %s", exc)
            return LLMResult(
                success=False,
                content="UNKNOWN",
                raw_response="",
                usage=usage,
                fallback_used=True,
                error_type=error_type,
                reason=str(exc),
            )

    def suggest_mapping(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        task_id: int | None = None,
        db: Session | None = None,
    ) -> LLMResult:
        """Request form field mapping suggestions.

        This is a specialized variant of complete_json optimized for
        form field to profile key mapping tasks.

        Args:
            prompt: The mapping prompt with form field details
            schema: JSON schema for the mapping response
            task_id: Optional task ID for usage tracking
            db: Optional database session for usage logging

        Returns:
            LLMResult with parsed mapping dict if successful.
        """
        return self.complete_json(prompt, schema, task_id=task_id, db=db)

    def _create_unavailable_fallback(self, operation: str) -> LLMResult:
        """Create a standardized fallback result when LLM is unavailable."""
        logger.warning("LLM unavailable, falling back to rules for %s", operation)
        return LLMResult(
            success=False,
            content=None,
            raw_response="",
            usage=None,
            fallback_used=True,
            error_type="LLM_UNAVAILABLE",
            reason="LLM provider not configured or unavailable",
        )

    def _call_provider(
        self,
        provider: LLMProvider,
        model: str,
        prompt: str,
        response_format: str = "text",
        schema: dict[str, Any] | None = None,
        task_id: int | None = None,
        db: Session | None = None,
    ) -> str:
        """Call the appropriate LLM provider based on configuration.

        This delegates to provider-specific implementations that are
        currently in field_mapper.py. In the future, this will be the
        only place where provider-specific code lives.
        """

        # For now, we reuse the existing implementation from field_mapper
        # This avoids duplicating provider-specific logic
        from app.services.field_mapper import _request_llm_mapping

        if response_format == "json" and schema:
            # Use field_mapper's LLM mapping which already handles JSON schema
            return _request_llm_mapping(
                prompt,
                provider=provider,
                task_id=task_id,
                db=db,
            )
        else:
            # For text format, use a simpler approach
            return _request_llm_mapping(
                prompt,
                provider=provider,
                task_id=task_id,
                db=db,
            )

    def _parse_and_validate_json(
        self,
        raw_response: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Parse and validate JSON response against schema."""

        try:
            # First try to parse as JSON
            parsed = json.loads(raw_response)

            # Validate against schema (basic validation for now)
            self._validate_schema_basic(parsed, schema)

            return parsed

        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON response: {exc}") from exc

    def _validate_schema_basic(
        self,
        data: dict[str, Any],
        schema: dict[str, Any],
    ) -> None:
        """Basic schema validation - ensure required fields exist."""

        required = schema.get("required", [])
        for field in required:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        # Validate nested mappings if present
        properties = schema.get("properties", {})
        for prop_name, prop_schema in properties.items():
            if prop_name in data:
                prop_data = data[prop_name]
                prop_type = prop_schema.get("type")
                if prop_type == "array" and not isinstance(prop_data, list):
                    raise ValueError(f"Field '{prop_name}' must be an array")
                elif prop_type == "object" and not isinstance(prop_data, dict):
                    raise ValueError(f"Field '{prop_name}' must be an object")

    def _extract_usage(
        self,
        provider: LLMProvider,
        model: str,
        response: str,
        latency_ms: int,
    ) -> LLMUsage:
        """Extract usage metrics from provider response.

        Note: This is a simplified version. In production, you would
        extract actual token counts from the provider's response object.
        """

        # For now, estimate tokens
        prompt_tokens = 0  # Would be extracted from actual API response
        completion_tokens = len(response.split()) * 2  # Rough estimate
        total_tokens = prompt_tokens + completion_tokens

        estimated_cost = estimate_llm_cost(
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        return LLMUsage(
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            estimated_cost=estimated_cost,
        )

    def _record_usage(
        self,
        task_id: int | None,
        db: Session | None,
        usage: LLMUsage,
    ) -> None:
        """Record LLM usage to database."""

        if task_id is None:
            return

        usage_dict = {
            "provider": usage.provider,
            "model": usage.model,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "cache_hit_tokens": usage.cache_hit_tokens,
            "cache_miss_tokens": usage.cache_miss_tokens,
            "cache_hit": usage.cache_hit_tokens > 0,
            "cache_hit_rate": (
                usage.cache_hit_tokens / max(usage.prompt_tokens, 1)
            ),
            "latency_ms": usage.latency_ms,
            "estimated_cost": usage.estimated_cost,
        }

        try:
            record_llm_api_usage(task_id=task_id, usage=usage_dict, db=db)
        except Exception as exc:
            logger.warning("Failed to record LLM usage: %s", exc)

    def _record_failure_usage(
        self,
        task_id: int | None,
        db: Session | None,
        usage: LLMUsage,
        error_type: str,
    ) -> None:
        """Record failed LLM usage with error details."""

        if task_id is None:
            return

        usage_dict = {
            "provider": usage.provider,
            "model": usage.model,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "cache_hit_tokens": usage.cache_hit_tokens,
            "cache_miss_tokens": usage.cache_miss_tokens,
            "cache_hit": False,
            "cache_hit_rate": 0.0,
            "latency_ms": usage.latency_ms,
            "error_type": error_type,
            "fallback_used": True,
            "cache_source": "no_cache",
            "estimated_cost": 0.0,
        }

        try:
            record_llm_api_usage(task_id=task_id, usage=usage_dict, db=db)
        except Exception as exc:
            logger.warning("Failed to record LLM failure usage: %s", exc)


# Global singleton for convenience
_llm_client: LLMClient | None = None


def get_llm_client(provider: LLMProvider | None = None) -> LLMClient:
    """Get or create the global LLM client instance."""

    global _llm_client
    if _llm_client is None or provider is not None:
        _llm_client = LLMClient(provider=provider)
    return _llm_client


def llm_is_available(provider: LLMProvider | None = None) -> bool:
    """Check if an LLM provider is available and configured."""
    return get_llm_client(provider=provider)._is_available()
