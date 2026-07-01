"""Rule-based and LLM-assisted form field mapping."""

import json
import logging
import re
from collections.abc import Iterable
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.database import SessionLocal
from app.models import FormField, Profile, Task
from app.schemas import LLMProvider, ProfileKey
from app.services.llm_provider_config import resolve_llm_provider
from app.services.llm_usage_service import record_llm_api_usage
from app.services.mapping_cache import (
    build_mapping_cache_context,
    model_for_provider,
    read_cached_mapping_response,
    read_user_override_response,
    write_mapping_cache_response,
)

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

NON_FILLABLE_FIELD_TYPES = {
    "button",
    "file",
    "submit",
    "reset",
    "image",
}

CUSTOM_PROFILE_KEY_PREFIX = "custom:"

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "full_name": (
        "full name",
        "fullname",
        "your name",
        "applicant name",
        "candidate name",
        "contact name",
        "name",
    ),
    "email": ("email address", "e mail", "email"),
    "university": (
        "university",
        "college",
        "school",
        "institution",
        "alma mater",
    ),
    "major": (
        "field of study",
        "area of study",
        "degree major",
        "major",
        "specialization",
        "specialisation",
    ),
    "phone": (
        "phone number",
        "mobile number",
        "telephone number",
        "cell number",
        "phone",
        "mobile",
        "telephone",
        "tel",
    ),
    "linkedin": ("linkedin profile", "linkedin url", "linkedin"),
    "github": ("github profile", "github url", "github"),
    "self_intro": (
        "self introduction",
        "self intro",
        "personal introduction",
        "personal statement",
        "about yourself",
        "about you",
        "biography",
        "introduction",
        "bio",
    ),
}

TYPE_MATCHES = {
    "email": "email",
    "tel": "phone",
    "telephone": "phone",
}

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


class LLMFieldMapping(BaseModel):
    """One strictly validated field-to-profile mapping returned by an LLM."""

    model_config = ConfigDict(extra="forbid")

    field_id: int
    mapped_profile_key: ProfileKey
    confidence: float = Field(ge=0, le=1)


class LLMMappingResponse(BaseModel):
    """The only JSON shape accepted from an LLM provider."""

    model_config = ConfigDict(extra="forbid")

    mappings: list[LLMFieldMapping]


def _normalize(value: str | None) -> str:
    """Turn labels and selectors into comparable lowercase words."""

    if not value:
        return ""
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    return " ".join(re.sub(r"[^a-zA-Z0-9]+", " ", value).lower().split())


def _is_fillable_field(field: FormField) -> bool:
    """Exclude buttons and submit-like controls from every mapping mode."""

    return _normalize(field.field_type) not in NON_FILLABLE_FIELD_TYPES


def _source_scores(field: FormField) -> Iterable[tuple[str, float]]:
    """Yield normalized field metadata with a reliability score."""

    sources = (
        (field.label, 0.98),
        (field.placeholder, 0.94),
        (field.section_title, 0.86),
        (field.form_title, 0.82),
        (field.selector, 0.90),
    )
    for value, score in sources:
        normalized = _normalize(value)
        if normalized:
            yield normalized, score


def _alias_score(text: str, alias: str, base_score: float) -> float | None:
    """Score one alias while treating the generic word 'name' cautiously."""

    if text == alias:
        return base_score
    if alias == "name":
        return None
    if f" {alias} " in f" {text} ":
        return max(base_score - 0.06, 0.0)
    return None


def _match_profile_key(field: FormField) -> tuple[str, float] | None:
    """Return the best profile key and confidence for one form field."""

    normalized_type = _normalize(field.field_type)
    if normalized_type in TYPE_MATCHES:
        return TYPE_MATCHES[normalized_type], 0.99

    best_match: tuple[str, float] | None = None
    for text, base_score in _source_scores(field):
        for profile_key, aliases in FIELD_ALIASES.items():
            for alias in aliases:
                score = _alias_score(text, alias, base_score)
                if score is None:
                    continue
                if best_match is None or score > best_match[1]:
                    best_match = (profile_key, score)

    return best_match


def _split_full_name(full_name: str | None) -> tuple[str | None, str | None]:
    """Split a stored full name into simple first and last name values."""

    if not full_name:
        return None, None

    parts = full_name.split()
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


def get_profile_value(profile: Profile, profile_key: ProfileKey) -> str | None:
    """Return stored or derived profile values used by field mapping."""

    if profile_key.startswith(CUSTOM_PROFILE_KEY_PREFIX):
        custom_key = profile_key.removeprefix(CUSTOM_PROFILE_KEY_PREFIX)
        return profile.custom_values.get(custom_key)
    if profile_key == "first_name":
        return _split_full_name(profile.full_name)[0]
    if profile_key == "last_name":
        return _split_full_name(profile.full_name)[1]
    if profile_key not in PROFILE_KEYS:
        return None
    return getattr(profile, profile_key)


def _map_fields(task_id: int, db: Session) -> list[FormField]:
    """Apply mapping rules using an existing database session."""

    task = db.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found")

    fields = list(
        db.scalars(
            select(FormField)
            .where(FormField.task_id == task_id)
            .order_by(FormField.id)
        )
    )

    for field in fields:
        if not _is_fillable_field(field):
            field.mapped_profile_key = None
            field.mapped_value = None
            field.confidence = None
            continue

        match = _match_profile_key(field)
        if match is None:
            field.mapped_profile_key = None
            field.mapped_value = None
            field.confidence = None
            continue

        profile_key, confidence = match
        profile_value = get_profile_value(task.profile, profile_key)
        if profile_value is None or profile_value == "":
            field.mapped_profile_key = None
            field.mapped_value = None
            field.confidence = None
            continue

        field.mapped_profile_key = profile_key
        field.mapped_value = profile_value
        field.confidence = confidence

    db.commit()
    return fields


def _profile_payload(task: Task) -> dict[str, str]:
    """Return only supported, non-empty profile values for the LLM."""

    profile = {
        key: value
        for key in PROFILE_KEYS
        if (value := get_profile_value(task.profile, key)) not in (None, "")
    }
    profile.update(
        {
            f"{CUSTOM_PROFILE_KEY_PREFIX}{key}": value
            for key, value in task.profile.custom_values.items()
            if value not in (None, "")
        }
    )
    return profile


def _stable_ref(field: FormField, index: int) -> str:
    """Return a task-independent field reference for prompt structure."""

    return field.element_ref or f"field_{index + 1}"


def _stable_fields_payload(fields: list[FormField]) -> list[dict[str, object]]:
    """Serialize cache-friendly field metadata without task-specific IDs."""

    return [
        {
            "stable_ref": _stable_ref(field, index),
            "form_title": field.form_title,
            "section_title": field.section_title,
            "field_label": field.label,
            "selector": field.selector,
            "type": field.field_type,
            "hint": field.placeholder,
            "name": field.name,
            "html_id": field.html_id,
            "current_value": field.current_value,
            "options": field.options,
            "required": field.required,
            "fillable": _is_fillable_field(field),
        }
        for index, field in enumerate(fields)
    ]


def _field_id_map(fields: list[FormField]) -> list[dict[str, object]]:
    """Map stable prompt references to current database IDs."""

    return [
        {
            "stable_ref": _stable_ref(field, index),
            "field_id": field.id,
        }
        for index, field in enumerate(fields)
    ]


def _build_llm_prompt(
    fields: list[FormField],
    profile: dict[str, str],
) -> str:
    """Build a prompt with a stable prefix for provider-side context caching."""

    output_data = {
        "mappings": [
            {
                "field_id": "integer field_id from input",
                "mapped_profile_key": f"one of: {', '.join(PROFILE_KEYS)}",
                "confidence": "number from 0 to 1",
            }
        ]
    }
    return (
        "Map each fillable form field to the best matching profile key. "
        "Use first_name or last_name when a form splits a person's name into "
        "separate given/family name fields, and use full_name when the form "
        "asks for one combined name. "
        "Omit uncertain or non-fillable fields. Never return browser actions, "
        "clicks, submits, selectors to execute, or invented values. "
        "Return only JSON matching this shape:\n"
        f"{json.dumps(output_data, ensure_ascii=False)}\n\n"
        "Use the stable_ref values to reason about the form. Use the current "
        "run field id map at the end to return real field_id integers. "
        "Do not return stable_ref in the final JSON.\n\n"
        "Stable form fields:\n"
        f"{json.dumps(_stable_fields_payload(fields), ensure_ascii=False)}"
        "\n\nCurrent run field id map:\n"
        f"{json.dumps(_field_id_map(fields), ensure_ascii=False)}"
        "\n\nCurrent profile values:\n"
        f"{json.dumps(profile, ensure_ascii=False)}"
    )


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
    """Extract structured text from a raw Responses API response."""

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


def _extract_deepseek_usage(response: dict[str, object]) -> dict[str, object]:
    """Build internal token and cache metrics from DeepSeek's usage payload."""

    usage = response.get("usage")
    if not isinstance(usage, dict):
        return {
            "provider": "deepseek",
            "model": config.DEEPSEEK_MODEL,
            "usage_available": False,
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

    return {
        "provider": "deepseek",
        "model": config.DEEPSEEK_MODEL,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cache_hit_tokens": cache_hit_tokens,
        "cache_miss_tokens": cache_miss_tokens,
        "cache_hit": cache_hit_tokens > 0,
        "cache_hit_rate": (
            cache_hit_tokens / prompt_tokens if prompt_tokens else 0
        ),
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
) -> None:
    """Log usage and persist it when this request belongs to a task."""

    usage = _extract_deepseek_usage(response)
    _log_deepseek_usage(usage)
    if task_id is not None:
        record_llm_api_usage(task_id=task_id, usage=usage, db=db)


def _request_openai_mapping(prompt: str) -> str:
    """Request schema-constrained JSON from the OpenAI Responses API."""

    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    response = _post_json(
        "https://api.openai.com/v1/responses",
        {
            "model": config.OPENAI_MODEL,
            "instructions": (
                "You map form fields to profile keys. Output mapping data only."
            ),
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "form_field_mappings",
                    "schema": LLM_MAPPING_SCHEMA,
                    "strict": True,
                }
            },
        },
        {"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
    )
    return _extract_openai_output_text(response)


def _request_gemini_mapping(prompt: str) -> str:
    """Request schema-constrained JSON from Gemini generateContent."""

    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    response = _post_json(
        (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{config.GEMINI_MODEL}:generateContent"
        ),
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": LLM_MAPPING_SCHEMA,
            },
        },
        {"x-goog-api-key": config.GEMINI_API_KEY},
    )

    try:
        return response["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Gemini response did not contain output text") from exc


def _request_deepseek_mapping(
    prompt: str,
    task_id: int | None = None,
    db: Session | None = None,
) -> str:
    """Request JSON field mappings from DeepSeek's OpenAI-compatible API."""

    if not config.DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    logger.warning(
        "Calling DeepSeek mapping API with model %s",
        config.DEEPSEEK_MODEL,
    )
    response = _post_json(
        "https://api.deepseek.com/chat/completions",
        {
            "model": config.DEEPSEEK_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You map form fields to profile keys. Output valid JSON "
                        "only, using this shape: "
                        '{"mappings":[{"field_id":1,'
                        '"mapped_profile_key":"email","confidence":0.9}]}.'
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "max_tokens": 2000,
            "stream": False,
        },
        {"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}"},
    )
    _record_deepseek_usage(response, task_id=task_id, db=db)
    output_text = _extract_chat_completion_output_text(response, "DeepSeek")
    logger.warning("DeepSeek mapping API returned output text")
    return output_text


def _request_llm_mapping(
    prompt: str,
    provider: LLMProvider | None = None,
    task_id: int | None = None,
    db: Session | None = None,
) -> str:
    """Route the mapping request to the configured provider."""

    selected_provider = resolve_llm_provider(provider)
    if selected_provider == "openai":
        return _request_openai_mapping(prompt)
    if selected_provider == "gemini":
        return _request_gemini_mapping(prompt)
    if selected_provider == "deepseek":
        return _request_deepseek_mapping(prompt, task_id=task_id, db=db)
    raise ValueError("LLM_PROVIDER must be 'openai', 'gemini', or 'deepseek'")


def _validate_llm_response(
    raw_response: str,
    fields: list[FormField],
    profile: dict[str, str],
) -> LLMMappingResponse:
    """Validate JSON shape, IDs, fillability, uniqueness, and profile keys."""

    parsed = LLMMappingResponse.model_validate_json(raw_response)
    fillable_field_ids = {
        field.id for field in fields if _is_fillable_field(field)
    }
    seen_field_ids: set[int] = set()

    for mapping in parsed.mappings:
        if mapping.field_id not in fillable_field_ids:
            raise ValueError("LLM mapped an unknown or non-fillable field")
        if mapping.field_id in seen_field_ids:
            raise ValueError("LLM returned duplicate field mappings")
        seen_field_ids.add(mapping.field_id)

    valid_mappings = [
        mapping
        for mapping in parsed.mappings
        if mapping.mapped_profile_key in profile
    ]
    skipped_count = len(parsed.mappings) - len(valid_mappings)
    if skipped_count:
        logger.warning(
            "Ignoring %s LLM mappings whose profile key has no value",
            skipped_count,
        )

    return LLMMappingResponse(mappings=valid_mappings)


def _apply_llm_mappings(
    fields: list[FormField],
    profile: dict[str, str],
    result: LLMMappingResponse,
    db: Session,
) -> list[FormField]:
    """Persist validated mappings; values always come from the database profile."""

    mappings_by_field_id = {
        mapping.field_id: mapping for mapping in result.mappings
    }
    for field in fields:
        mapping = mappings_by_field_id.get(field.id)
        if mapping is None:
            field.mapped_profile_key = None
            field.mapped_value = None
            field.confidence = None
            continue

        field.mapped_profile_key = mapping.mapped_profile_key
        field.mapped_value = profile[mapping.mapped_profile_key]
        field.confidence = mapping.confidence

    db.commit()
    return fields


def _mapping_response_by_field_id(raw_response: str) -> dict[int, dict[str, object]]:
    """Parse a mapping JSON response into mutable mapping dictionaries."""

    parsed = json.loads(raw_response)
    mappings = parsed.get("mappings")
    if not isinstance(mappings, list):
        raise ValueError("Mapping response has no mappings list")

    mappings_by_field_id: dict[int, dict[str, object]] = {}
    for mapping in mappings:
        if not isinstance(mapping, dict):
            raise ValueError("Mapping entry is not an object")
        field_id = mapping.get("field_id")
        if not isinstance(field_id, int):
            raise ValueError("Mapping entry has no integer field_id")
        mappings_by_field_id[field_id] = dict(mapping)
    return mappings_by_field_id


def _merge_mapping_responses(
    base_response: str | None,
    override_response: str | None,
) -> str | None:
    """Return a mapping response with user overrides replacing base mappings."""

    if base_response is None and override_response is None:
        return None

    merged: dict[int, dict[str, object]] = {}
    if base_response is not None:
        merged.update(_mapping_response_by_field_id(base_response))
    if override_response is not None:
        merged.update(_mapping_response_by_field_id(override_response))

    return json.dumps({"mappings": list(merged.values())}, ensure_ascii=False)


def _fillable_field_ids(fields: list[FormField]) -> set[int]:
    """Return field IDs that an automated mapping may fill."""

    return {
        field.id
        for field in fields
        if field.id is not None and _is_fillable_field(field)
    }


def _response_covers_fillable_fields(
    raw_response: str,
    fields: list[FormField],
) -> bool:
    """Return whether a cached response can stand in for an LLM call."""

    mapped_field_ids = set(_mapping_response_by_field_id(raw_response))
    return _fillable_field_ids(fields).issubset(mapped_field_ids)


def _map_fields_with_llm(
    task_id: int,
    db: Session,
    provider: LLMProvider | None = None,
) -> list[FormField]:
    """Apply LLM mappings in an existing database session."""

    task = db.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found")

    fields = list(
        db.scalars(
            select(FormField)
            .where(FormField.task_id == task_id)
            .order_by(FormField.id)
        )
    )
    profile = _profile_payload(task)

    try:
        try:
            selected_provider = resolve_llm_provider(provider)
            cache_context = build_mapping_cache_context(
                provider=selected_provider,
                model=model_for_provider(selected_provider),
                fields=fields,
                profile=profile,
            )
        except ValueError:
            selected_provider = provider
            cache_context = None

        override_response = read_user_override_response(db, fields, profile)
        if override_response is not None and _response_covers_fillable_fields(
            override_response,
            fields,
        ):
            result = _validate_llm_response(override_response, fields, profile)
            if cache_context is not None:
                write_mapping_cache_response(
                    db,
                    cache_context,
                    fields,
                    override_response,
                )
            return _apply_llm_mappings(fields, profile, result, db)

        cached_response = (
            read_cached_mapping_response(db, cache_context, fields)
            if cache_context is not None
            else None
        )
        merged_cached_response = _merge_mapping_responses(
            cached_response,
            override_response,
        )
        if merged_cached_response is not None:
            result = _validate_llm_response(
                merged_cached_response,
                fields,
                profile,
            )
            if cache_context is not None:
                write_mapping_cache_response(
                    db,
                    cache_context,
                    fields,
                    merged_cached_response,
                )
            return _apply_llm_mappings(fields, profile, result, db)

        prompt = _build_llm_prompt(fields, profile)
        raw_response = _request_llm_mapping(
            prompt,
            selected_provider,
            task_id=task_id,
            db=db,
        )
        merged_response = _merge_mapping_responses(raw_response, override_response)
        if merged_response is None:
            merged_response = raw_response
        result = _validate_llm_response(merged_response, fields, profile)
        if cache_context is not None:
            write_mapping_cache_response(db, cache_context, fields, merged_response)
        mapped_fields = _apply_llm_mappings(fields, profile, result, db)
        logger.warning(
            "LLM mapping succeeded for task %s with %s mappings",
            task_id,
            len(result.mappings),
        )
        return mapped_fields
    except Exception as exc:
        db.rollback()
        logger.warning(
            "LLM mapping failed for task %s; using rules: %s",
            task_id,
            exc,
        )
        return _map_fields(task_id, db)


def map_fields_with_llm(
    task_id: int,
    db: Session | None = None,
    provider: LLMProvider | None = None,
) -> list[FormField]:
    """Map fields with an LLM and safely fall back to local rules."""

    if db is not None:
        return _map_fields_with_llm(task_id, db, provider)

    with SessionLocal() as session:
        fields = _map_fields_with_llm(task_id, session, provider)
        for field in fields:
            session.expunge(field)
        return fields


def map_fields_by_rules(
    task_id: int,
    db: Session | None = None,
) -> list[FormField]:
    """Map and save all extracted fields for a task without using an LLM."""

    if db is not None:
        return _map_fields(task_id, db)

    with SessionLocal() as session:
        fields = _map_fields(task_id, session)
        for field in fields:
            session.expunge(field)
        return fields
