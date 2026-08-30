"""LLM Client Boundary - The only provider-specific HTTP/API boundary.

Provides a minimal, stable interface for LLM interactions while hiding
provider-specific SDK details. Supports graceful fallback when LLM is unavailable
or returns invalid output.

This file contains ALL provider-specific request logic. Business services
should only call methods from this module, not directly access provider APIs.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app import config
from app.schemas import LLMProvider, ProfileKey
from app.services import llm_provider_config
from app.services.llm_usage_service import record_llm_api_usage
from app.services.llm_cost_service import estimate_llm_cost

logger = logging.getLogger(__name__)

PROFILE_KEYS: tuple[ProfileKey, ...] = (
    "first_name",
    "last_name",
    "full_name",
    "email",
    "university",
    "major",
    "phone",
    "linkedin",
    "github",
    "self_intro",
)

LLM_MAPPING_SCHEMA = {
    "type": "object",
    "properties": {
        "mappings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field_id": {"type": "integer"},
                    "mapped_profile_key": {
                        "type": "string",
                        "enum": list(PROFILE_KEYS),
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                },
                "required": [
                    "field_id",
                    "mapped_profile_key",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["mappings"],
    "additionalProperties": False,
}

LLM_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
    },
    "required": ["summary"],
    "additionalProperties": False,
}


def _classification_schema(labels: list[str] | tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "label": {"type": "string", "enum": list(labels)},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
        },
        "required": ["label", "confidence", "reason"],
        "additionalProperties": False,
    }


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


def _post_json(
    url: str,
    payload: dict[str, object],
    headers: dict[str, str],
) -> dict[str, object]:
    """Send one JSON request using the standard library."""

    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urlopen(
        request,
        timeout=config.LLM_REQUEST_TIMEOUT_SECONDS,
    ) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_openai_output_text(response: dict[str, object]) -> str:
    """Extract structured text from a raw OpenAI Responses API response."""

    output = response.get("output")
    if not isinstance(output, list):
        raise ValueError("OpenAI response did not contain output")

    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if (
                isinstance(part, dict)
                and part.get("type") == "output_text"
                and isinstance(part.get("text"), str)
            ):
                return part["text"]

    raise ValueError("OpenAI response did not contain output text")


def _extract_chat_completion_output_text(
    response: dict[str, object],
    provider_name: str,
) -> str:
    """Extract text from an OpenAI-compatible chat completion response."""

    try:
        choices = response["choices"]
        if not isinstance(choices, list):
            raise TypeError
        message = choices[0]["message"]
        content = message["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(
            f"{provider_name} response did not contain output text"
        ) from exc

    if not isinstance(content, str) or not content:
        raise ValueError(f"{provider_name} response did not contain output text")
    return content


def _usage_int(usage: dict[str, object], key: str) -> int | None:
    """Return an integer usage metric when the provider sent one."""

    value = usage.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _extract_deepseek_usage(response: dict[str, object], latency_ms: int = 0) -> dict[str, object]:
    """Build internal token and cache metrics from DeepSeek's usage payload."""

    usage = response.get("usage")
    if not isinstance(usage, dict):
        return {
            "provider": "deepseek",
            "model": config.DEEPSEEK_MODEL,
            "usage_available": False,
            "latency_ms": latency_ms,
        }

    prompt_tokens = _usage_int(usage, "prompt_tokens") or 0
    completion_tokens = _usage_int(usage, "completion_tokens") or 0
    total_tokens = _usage_int(usage, "total_tokens")
    cache_hit_tokens = _usage_int(usage, "prompt_cache_hit_tokens") or 0
    cache_miss_tokens = _usage_int(usage, "prompt_cache_miss_tokens")

    if total_tokens is None:
        total_tokens = prompt_tokens + completion_tokens
    if cache_miss_tokens is None:
        cache_miss_tokens = max(prompt_tokens - cache_hit_tokens, 0)

    cache_hit = cache_hit_tokens > 0
    cache_hit_rate = cache_hit_tokens / prompt_tokens if prompt_tokens else 0

    cache_source = "provider_prompt_cache" if cache_hit else "no_cache"

    return {
        "provider": "deepseek",
        "model": config.DEEPSEEK_MODEL,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cache_hit_tokens": cache_hit_tokens,
        "cache_miss_tokens": cache_miss_tokens,
        "cache_hit": cache_hit,
        "cache_hit_rate": cache_hit_rate,
        "latency_ms": latency_ms,
        "cache_source": cache_source,
    }


def _log_deepseek_usage(usage: dict[str, object]) -> None:
    """Record DeepSeek usage metrics without exposing prompt or response text."""

    logger.info(
        "DeepSeek API usage: %s",
        json.dumps(usage, ensure_ascii=False),
    )


def _record_deepseek_usage(
    response: dict[str, object],
    task_id: int | None,
    db: Session | None,
    latency_ms: int = 0,
) -> None:
    """Log usage and persist it when this request belongs to a task."""

    usage = _extract_deepseek_usage(response, latency_ms=latency_ms)
    _log_deepseek_usage(usage)
    if task_id is not None:
        record_llm_api_usage(task_id=task_id, usage=usage, db=db)


def _record_deepseek_error(
    *,
    provider: str,
    model: str,
    task_id: int | None,
    db: Session | None,
    error_type: str,
    latency_ms: int,
) -> None:
    """Record a failed DeepSeek API request with error details."""

    usage = {
        "provider": provider,
        "model": model,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cache_hit_tokens": 0,
        "cache_miss_tokens": 0,
        "cache_hit": False,
        "cache_hit_rate": 0.0,
        "latency_ms": latency_ms,
        "error_type": error_type,
        "fallback_used": True,
        "cache_source": "no_cache",
        "estimated_cost": 0.0,
    }
    logger.warning(
        "DeepSeek API error: %s, latency_ms: %s",
        error_type,
        latency_ms,
    )
    if task_id is not None:
        record_llm_api_usage(task_id=task_id, usage=usage, db=db)


def _extract_openai_usage(response: dict[str, object], latency_ms: int = 0) -> dict[str, object]:
    """Build internal token metrics from OpenAI's usage payload."""

    usage = response.get("usage")
    if not isinstance(usage, dict):
        return {
            "provider": "openai",
            "model": config.OPENAI_MODEL,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cache_hit_tokens": 0,
            "cache_miss_tokens": 0,
            "cache_hit": False,
            "cache_hit_rate": 0.0,
            "latency_ms": latency_ms,
            "cache_source": "no_cache",
        }

    prompt_tokens = _usage_int(usage, "prompt_tokens") or 0
    completion_tokens = _usage_int(usage, "completion_tokens") or 0
    total_tokens = _usage_int(usage, "total_tokens")
    cache_hit_tokens = _usage_int(usage, "prompt_cache_hit_tokens") or 0
    cache_miss_tokens = _usage_int(usage, "prompt_cache_miss_tokens")

    if total_tokens is None:
        total_tokens = prompt_tokens + completion_tokens
    if cache_miss_tokens is None:
        cache_miss_tokens = max(prompt_tokens - cache_hit_tokens, 0)

    cache_hit = cache_hit_tokens > 0
    cache_hit_rate = cache_hit_tokens / prompt_tokens if prompt_tokens else 0

    cache_source = "provider_prompt_cache" if cache_hit else "no_cache"

    return {
        "provider": "openai",
        "model": config.OPENAI_MODEL,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cache_hit_tokens": cache_hit_tokens,
        "cache_miss_tokens": cache_miss_tokens,
        "cache_hit": cache_hit,
        "cache_hit_rate": cache_hit_rate,
        "latency_ms": latency_ms,
        "cache_source": cache_source,
    }


def _extract_gemini_usage(response: dict[str, object], latency_ms: int = 0) -> dict[str, object]:
    """Build internal token metrics from Gemini's usage payload."""

    prompt_tokens = 0
    completion_tokens = 0
    cache_hit_tokens = 0

    try:
        candidates = response.get("candidates")
        if isinstance(candidates, list) and len(candidates) > 0:
            usage_metadata = candidates[0].get("usageMetadata")
            if isinstance(usage_metadata, dict):
                prompt_tokens = _usage_int(usage_metadata, "promptTokenCount") or 0
                completion_tokens = _usage_int(usage_metadata, "candidatesTokenCount") or 0
    except (KeyError, IndexError, TypeError):
        pass

    total_tokens = prompt_tokens + completion_tokens
    cache_miss_tokens = max(prompt_tokens - cache_hit_tokens, 0)
    cache_hit = cache_hit_tokens > 0
    cache_hit_rate = cache_hit_tokens / prompt_tokens if prompt_tokens else 0
    cache_source = "provider_prompt_cache" if cache_hit else "no_cache"

    return {
        "provider": "gemini",
        "model": config.GEMINI_MODEL,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cache_hit_tokens": cache_hit_tokens,
        "cache_miss_tokens": cache_miss_tokens,
        "cache_hit": cache_hit,
        "cache_hit_rate": cache_hit_rate,
        "latency_ms": latency_ms,
        "cache_source": cache_source,
    }


class LLMClient:
    """Thin LLM client boundary that abstracts provider-specific details."""

    def __init__(self, provider: LLMProvider | None = None):
        self.provider = provider

    def _resolve_provider(self) -> LLMProvider:
        """Resolve and return the selected LLM provider."""
        return llm_provider_config.resolve_llm_provider(self.provider)

    def _is_available(self) -> bool:
        """Check if the selected provider is configured and available."""
        try:
            provider = self._resolve_provider()
            return llm_provider_config.is_provider_configured(provider)
        except (ValueError, RuntimeError):
            return False

    def complete_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        task_id: int | None = None,
        db: Session | None = None,
        instructions: str | None = None,
        schema_name: str = "structured_response",
    ) -> LLMResult:
        """Request structured JSON output validated against a schema."""

        if not self._is_available():
            return LLMResult(
                success=False,
                content=None,
                raw_response="",
                usage=None,
                fallback_used=True,
                error_type="LLM_UNAVAILABLE",
                reason="LLM provider not configured or unavailable",
            )

        start_time = time.perf_counter()
        provider = self._resolve_provider()
        model = llm_provider_config.get_provider_model(provider)

        try:
            raw_response = self._call_provider(
                provider=provider,
                model=model,
                prompt=prompt,
                response_format="json",
                schema=schema,
                task_id=task_id,
                db=db,
                instructions=instructions,
                schema_name=schema_name,
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Validate JSON
            parsed = self._parse_and_validate_json(raw_response, schema)

            return LLMResult(
                success=True,
                content=parsed,
                raw_response=raw_response,
                reason="JSON completion successful",
            )

        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            error_type = type(exc).__name__

            logger.warning("LLM complete_json failed: %s", exc)
            return LLMResult(
                success=False,
                content=None,
                raw_response="",
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
        """
        return self.complete_json(
            prompt,
            schema,
            task_id=task_id,
            db=db,
            instructions="You map form fields to profile keys. Output mapping data only.",
            schema_name="form_field_mappings",
        )

    def summarize(
        self,
        prompt: str,
        *,
        max_sentences: int = 3,
        task_id: int | None = None,
        db: Session | None = None,
    ) -> LLMResult:
        """Summarize page or workflow text into a short structured summary."""

        summary_prompt = (
            f"Summarize the following content in at most {max_sentences} sentences. "
            "Return JSON with a single key named summary.\n\n"
            f"{prompt}"
        )
        return self.complete_json(
            summary_prompt,
            LLM_SUMMARY_SCHEMA,
            task_id=task_id,
            db=db,
            instructions="You summarize browser page content for a review-first workflow assistant. Output JSON only.",
            schema_name="page_summary",
        )

    def classify(
        self,
        prompt: str,
        labels: list[str] | tuple[str, ...],
        *,
        task_id: int | None = None,
        db: Session | None = None,
    ) -> LLMResult:
        """Classify text into one of the provided labels."""

        label_list = list(labels)
        schema = _classification_schema(label_list)
        classify_prompt = (
            "Classify the following content into exactly one of these labels: "
            f"{', '.join(label_list)}. Return JSON with label, confidence, and reason.\n\n"
            f"{prompt}"
        )
        result = self.complete_json(
            classify_prompt,
            schema,
            task_id=task_id,
            db=db,
            instructions="You classify browser pages for a review-first workflow assistant. Output JSON only.",
            schema_name="page_classification",
        )

        if not result.success:
            return result

        label = result.content.get("label") if isinstance(result.content, dict) else None
        if label not in label_list:
            return LLMResult(
                success=False,
                content=None,
                raw_response=result.raw_response,
                usage=result.usage,
                fallback_used=True,
                error_type="INVALID_CLASSIFICATION_LABEL",
                reason=f"Classification label is not allowed: {label}",
            )

        return result

    def _parse_and_validate_json(
        self,
        raw_response: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Parse and validate JSON response against schema."""

        try:
            parsed = json.loads(raw_response)

            # Validate against schema (basic validation)
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

        properties = schema.get("properties", {})
        for prop_name, prop_schema in properties.items():
            if prop_name in data:
                prop_data = data[prop_name]
                prop_type = prop_schema.get("type")
                if prop_type == "array" and not isinstance(prop_data, list):
                    raise ValueError(f"Field '{prop_name}' must be an array")
                elif prop_type == "object" and not isinstance(prop_data, dict):
                    raise ValueError(f"Field '{prop_name}' must be an object")

    def _call_provider(
        self,
        provider: LLMProvider,
        model: str,
        prompt: str,
        response_format: str = "text",
        schema: dict[str, Any] | None = None,
        task_id: int | None = None,
        db: Session | None = None,
        instructions: str | None = None,
        schema_name: str = "structured_response",
    ) -> str:
        """Call the appropriate LLM provider based on configuration."""

        if provider == "openai":
            return self._request_openai_mapping(
                prompt,
                schema=schema,
                instructions=instructions,
                schema_name=schema_name,
                task_id=task_id,
                db=db,
            )
        if provider == "gemini":
            return self._request_gemini_mapping(
                prompt,
                schema=schema,
                instructions=instructions,
                schema_name=schema_name,
                task_id=task_id,
                db=db,
            )
        if provider == "deepseek":
            return self._request_deepseek_mapping(
                prompt,
                schema=schema,
                instructions=instructions,
                schema_name=schema_name,
                task_id=task_id,
                db=db,
            )
        raise ValueError("LLM_PROVIDER must be 'openai', 'gemini', or 'deepseek'")

    def _request_openai_mapping(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        instructions: str | None = None,
        schema_name: str = "form_field_mappings",
        task_id: int | None = None,
        db: Session | None = None,
    ) -> str:
        """Request schema-constrained JSON from the OpenAI Responses API."""

        if not config.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        schema = schema or LLM_MAPPING_SCHEMA
        instructions = instructions or (
            "You map form fields to profile keys. Output mapping data only."
        )

        start_time = time.perf_counter()
        response = _post_json(
            "https://api.openai.com/v1/responses",
            {
                "model": config.OPENAI_MODEL,
                "instructions": instructions,
                "input": prompt,
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "schema": schema,
                        "strict": True,
                    }
                },
            },
            {"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        )
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        usage = _extract_openai_usage(response, latency_ms=latency_ms)
        logger.info("OpenAI API usage: %s", json.dumps(usage, ensure_ascii=False))
        if task_id is not None:
            record_llm_api_usage(task_id=task_id, usage=usage, db=db)
        return _extract_openai_output_text(response)

    def _request_gemini_mapping(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        instructions: str | None = None,
        schema_name: str = "form_field_mappings",
        task_id: int | None = None,
        db: Session | None = None,
    ) -> str:
        """Request schema-constrained JSON from Gemini generateContent."""

        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        schema = schema or LLM_MAPPING_SCHEMA
        instructions = instructions or (
            "You map form fields to profile keys. Output mapping data only."
        )

        effective_prompt = f"{instructions}\n\n{prompt}"

        start_time = time.perf_counter()
        response = _post_json(
            (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{config.GEMINI_MODEL}:generateContent"
            ),
            {
                "contents": [{"parts": [{"text": effective_prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": schema,
                },
            },
            {"x-goog-api-key": config.GEMINI_API_KEY},
        )
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        usage = _extract_gemini_usage(response, latency_ms=latency_ms)
        logger.info("Gemini API usage: %s", json.dumps(usage, ensure_ascii=False))
        if task_id is not None:
            record_llm_api_usage(task_id=task_id, usage=usage, db=db)

        try:
            return response["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("Gemini response did not contain output text") from exc

    def _request_deepseek_mapping(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        instructions: str | None = None,
        schema_name: str = "form_field_mappings",
        task_id: int | None = None,
        db: Session | None = None,
    ) -> str:
        """Request JSON output from DeepSeek's OpenAI-compatible API."""

        if not config.DEEPSEEK_API_KEY:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")

        schema = schema or LLM_MAPPING_SCHEMA
        instructions = instructions or (
            "You map form fields to profile keys. Output mapping data only."
        )
        system_content = (
            f"{instructions} "
            f"Output valid JSON matching this schema: "
            f"{json.dumps(schema, ensure_ascii=False)}"
        )

        logger.warning(
            "Calling DeepSeek mapping API with model %s",
            config.DEEPSEEK_MODEL,
        )
        start_time = time.perf_counter()
        response = _post_json(
            "https://api.deepseek.com/chat/completions",
            {
                "model": config.DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "thinking": {"type": "disabled"},
                "max_tokens": 2000,
                "stream": False,
            },
            {"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}"},
        )
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        _record_deepseek_usage(response, task_id=task_id, db=db, latency_ms=latency_ms)
        output_text = _extract_chat_completion_output_text(response, "DeepSeek")
        logger.warning("DeepSeek mapping API returned output text")
        return output_text


def get_llm_client(provider: LLMProvider | None = None) -> LLMClient:
    """Create a new LLM client instance.

    Unlike a singleton, this always returns a new instance to avoid
    state leakage between different provider configurations.
    """
    return LLMClient(provider=provider)


def llm_is_available(provider: LLMProvider | None = None) -> bool:
    """Check if an LLM provider is available and configured."""
    return get_llm_client(provider=provider)._is_available()
