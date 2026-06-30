"""Persistent cache helpers for reusable LLM field mappings."""

import json
from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.models import FormField, LLMMappingCache, utc_now
from app.schemas import LLMProvider

PROMPT_VERSION = "field-mapping-v1"


@dataclass(frozen=True)
class LLMMappingCacheContext:
    """Stable cache identity for one provider/model/form/profile-key shape."""

    cache_key: str
    provider: str
    model: str
    prompt_version: str
    fields_fingerprint: str
    profile_keys_signature: str


def _hash_json(payload: object) -> str:
    """Hash JSON with stable key ordering and compact separators."""

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(encoded.encode("utf-8")).hexdigest()


def model_for_provider(provider: LLMProvider) -> str:
    """Return the configured model name used by one LLM provider."""

    if provider == "openai":
        return config.OPENAI_MODEL
    if provider == "gemini":
        return config.GEMINI_MODEL
    if provider == "deepseek":
        return config.DEEPSEEK_MODEL
    raise ValueError("Unsupported LLM provider")


def field_signature(field: FormField) -> str:
    """Return a stable signature for reusable form-field identity."""

    return _hash_json(
        {
            "form_title": field.form_title,
            "section_title": field.section_title,
            "label": field.label,
            "selector": field.selector,
            "field_type": field.field_type,
            "placeholder": field.placeholder,
            "name": field.name,
            "html_id": field.html_id,
            "required": field.required,
        }
    )


def build_mapping_cache_context(
    *,
    provider: LLMProvider,
    model: str,
    fields: list[FormField],
    profile: dict[str, str],
) -> LLMMappingCacheContext:
    """Build a stable cache context without task IDs or profile values."""

    field_signatures = [field_signature(field) for field in fields]
    fields_fingerprint = _hash_json(field_signatures)
    profile_keys_signature = _hash_json(sorted(profile))
    cache_key = _hash_json(
        {
            "provider": provider,
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "fields_fingerprint": fields_fingerprint,
            "profile_keys_signature": profile_keys_signature,
        }
    )
    return LLMMappingCacheContext(
        cache_key=cache_key,
        provider=provider,
        model=model,
        prompt_version=PROMPT_VERSION,
        fields_fingerprint=fields_fingerprint,
        profile_keys_signature=profile_keys_signature,
    )


def _cached_response_for_fields(
    response_json: str,
    fields: list[FormField],
) -> str | None:
    """Convert cached field signatures back to current database field IDs."""

    parsed = json.loads(response_json)
    mappings = parsed.get("mappings")
    if not isinstance(mappings, list):
        raise ValueError("Cached mapping response has no mappings list")

    fields_by_signature = {field_signature(field): field for field in fields}
    current_mappings: list[dict[str, object]] = []
    for mapping in mappings:
        if not isinstance(mapping, dict):
            raise ValueError("Cached mapping entry is not an object")
        signature = mapping.get("field_signature")
        field = fields_by_signature.get(signature)
        if field is None:
            continue
        current_mappings.append(
            {
                "field_id": field.id,
                "mapped_profile_key": mapping.get("mapped_profile_key"),
                "confidence": mapping.get("confidence"),
            }
        )

    if mappings and not current_mappings:
        return None
    return json.dumps({"mappings": current_mappings}, ensure_ascii=False)


def read_cached_mapping_response(
    db: Session,
    context: LLMMappingCacheContext,
    fields: list[FormField],
) -> str | None:
    """Return a current-field-id response JSON when a cache entry matches."""

    entry = db.scalar(
        select(LLMMappingCache).where(LLMMappingCache.cache_key == context.cache_key)
    )
    if entry is None:
        return None

    response_json = _cached_response_for_fields(entry.response_json, fields)
    if response_json is None:
        return None

    entry.hit_count += 1
    entry.last_used_at = utc_now()
    return response_json


def write_mapping_cache_response(
    db: Session,
    context: LLMMappingCacheContext,
    fields: list[FormField],
    response_json: str,
) -> None:
    """Store validated field mappings using stable field signatures."""

    parsed = json.loads(response_json)
    mappings = parsed.get("mappings")
    if not isinstance(mappings, list):
        raise ValueError("LLM mapping response has no mappings list")

    signatures_by_id = {field.id: field_signature(field) for field in fields}
    cached_mappings: list[dict[str, object]] = []
    for mapping in mappings:
        if not isinstance(mapping, dict):
            raise ValueError("LLM mapping entry is not an object")
        field_id = mapping.get("field_id")
        signature = signatures_by_id.get(field_id)
        if signature is None:
            continue
        cached_mappings.append(
            {
                "field_signature": signature,
                "mapped_profile_key": mapping.get("mapped_profile_key"),
                "confidence": mapping.get("confidence"),
            }
        )

    entry = db.scalar(
        select(LLMMappingCache).where(LLMMappingCache.cache_key == context.cache_key)
    )
    if entry is None:
        entry = LLMMappingCache(
            cache_key=context.cache_key,
            provider=context.provider,
            model=context.model,
            prompt_version=context.prompt_version,
            fields_fingerprint=context.fields_fingerprint,
            profile_keys_signature=context.profile_keys_signature,
            response_json=json.dumps(
                {"mappings": cached_mappings},
                ensure_ascii=False,
            ),
        )
        db.add(entry)
        return

    entry.response_json = json.dumps({"mappings": cached_mappings}, ensure_ascii=False)
