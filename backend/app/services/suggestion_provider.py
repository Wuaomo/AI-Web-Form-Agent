"""Rules-first suggestion provider.

Produces ``AnswerSuggestion`` objects by combining:
- Rule-based profile key matching (field_mapper)
- Local policy document evidence (policy_doc_retriever)
- Reviewed memory hits (reviewed_memory_retriever)

The provider is read-only — it never modifies ``FormField`` rows, writes to
the database, or performs browser actions.

``mode='llm'`` attempts the optional LangChain adapter first, then falls
back to rules when LangChain is not installed or no API key is configured.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import FormField, Profile, Task
from app.services.field_mapper import (
    NON_FILLABLE_FIELD_TYPES,
    PROFILE_KEYS,
    _match_profile_key,
    _normalize,
    get_profile_value,
)
from app.services.langchain_suggestion_adapter import (
    LangChainUnavailableError,
    is_available as langchain_is_available,
    suggest_answers_with_langchain,
)
from app.services.policy_doc_retriever import retrieve_policy_sources
from app.services.reviewed_memory_retriever import retrieve_reviewed_memory
from app.services.suggestion_types import AnswerSuggestion
from app.services.workflow_memory import is_memory_eligible_field

logger = logging.getLogger(__name__)

SENSITIVE_FIELD_TYPES = {"password"}
SENSITIVE_TOKENS = {"password", "otp", "payment", "card", "captcha", "consent"}


def _is_sensitive_field(field: FormField) -> bool:
    """Return True if the field may carry a sensitive or one-time value."""

    field_type = (field.field_type or "").lower()
    if field_type in SENSITIVE_FIELD_TYPES:
        return True

    text = " ".join(
        str(x or "")
        for x in [
            field.label,
            field.name,
            field.placeholder,
            field.selector,
            field.field_type,
        ]
    ).lower()
    return any(token in text for token in SENSITIVE_TOKENS)


def _is_fillable(field: FormField) -> bool:
    """Check whether a field is eligible for any suggestion."""

    return _normalize(field.field_type) not in NON_FILLABLE_FIELD_TYPES


def _question_text(field: FormField) -> str:
    """Build a query string from field metadata for retrieval lookups."""

    parts = [
        field.label,
        field.name,
        field.placeholder,
        field.section_title,
        field.form_title,
    ]
    return " ".join(value for value in parts if value)


def _suggest_from_profile(
    field: FormField,
    profile: Profile | None,
) -> tuple[str | None, str | None, float, str | None]:
    """Try rule-based profile matching.

    Returns
    -------
    tuple[suggested_value, profile_key, confidence, reason]
    """

    if profile is None:
        return None, None, 0.0, "No profile available"

    match = _match_profile_key(field)
    if match is None:
        return None, None, 0.0, "No rule-based profile match"

    profile_key, confidence = match
    if profile_key.startswith("custom:"):
        value = profile.custom_values.get(profile_key.removeprefix("custom:"))
    elif profile_key in PROFILE_KEYS:
        value = get_profile_value(profile, profile_key)
    else:
        value = None

    if not value:
        return None, None, 0.0, "Profile key matched but has no value"

    return value, profile_key, confidence, f"Rule-based match to profile.{profile_key}"


def _build_suggestion(
    field: FormField,
    *,
    answer_status: str,
    suggested_value: str | None = None,
    mapped_profile_key: str | None = None,
    confidence: float = 0.0,
    reason: str = "",
    source_ids: list[str] | None = None,
    memory_ids: list[str] | None = None,
    safety_flags: list[str] | None = None,
) -> AnswerSuggestion:
    """Build an AnswerSuggestion from component pieces."""

    return AnswerSuggestion(
        question_id=str(field.id),
        field_id=str(field.id),
        suggested_value=suggested_value,
        mapped_profile_key=mapped_profile_key,
        confidence=round(min(max(confidence, 0.0), 1.0), 4),
        answer_status=answer_status,
        reason=reason,
        source_ids=source_ids or [],
        memory_ids=memory_ids or [],
        safety_flags=safety_flags or [],
    )


def suggest_answers(
    db: Session,
    *,
    task: Task,
    fields: list[FormField],
    profile: Profile | None,
    mode: str = "rules",
) -> list[AnswerSuggestion]:
    """Generate answer suggestions for a set of fields.

    Parameters
    ----------
    db:
        Read-only database session.
    task:
        The current task (used for workflow_type and context).
    fields:
        Fields to generate suggestions for.
    profile:
        The user profile to draw values from.
    mode:
        Suggestion mode. Currently supports ``'rules'`` and ``'llm'``.
        ``'llm'`` attempts the LangChain adapter first, then falls back
        to rules when LangChain is not installed or no API key is set.

    Returns
    -------
    list[AnswerSuggestion]
        One suggestion per input field, in the same order as ``fields``.
        The provider never writes to the database or modifies FormField rows.
    """

    if mode == "llm":
        llm_result = _try_langchain_suggestions(db, task=task, fields=fields, profile=profile)
        if llm_result is not None:
            return llm_result
        logger.info("LangChain unavailable — falling back to rules mode")

    return _suggest_with_rules(db, task=task, fields=fields, profile=profile)


def _try_langchain_suggestions(
    db: Session,
    *,
    task: Task,
    fields: list[FormField],
    profile: Profile | None,
) -> list[AnswerSuggestion] | None:
    """Attempt LangChain suggestions; return None to signal fallback."""

    if not langchain_is_available():
        return None

    profile_dict = _profile_to_dict(profile)

    questions = [
        {
            "question_id": str(field.id),
            "field_id": str(field.id),
            "label": field.label,
            "name": field.name,
            "type": field.field_type,
            "required": bool(field.required),
            "options": field.options or [],
        }
        for field in fields
    ]

    memory_hits_by_field: dict[str, list[dict[str, object]]] = {}
    policy_hits_by_field: dict[str, list[dict[str, object]]] = {}
    workflow_type = task.workflow_type or "form_fill"

    for field in fields:
        query = _question_text(field)
        fid = str(field.id)
        if is_memory_eligible_field(field):
            memory_hits_by_field[fid] = [
                hit.model_dump() for hit in retrieve_reviewed_memory(
                    db,
                    profile_id=task.profile_id or 0,
                    workflow_type=workflow_type,
                    query=query,
                )
            ]
        if workflow_type == "security_questionnaire":
            policy_hits_by_field[fid] = [
                hit.model_dump() for hit in retrieve_policy_sources(query, limit=3)
            ]

    input_payload: dict[str, object] = {
        "questions": questions,
        "profile": profile_dict,
        "memory_hits": memory_hits_by_field,
        "policy_sources": policy_hits_by_field,
    }

    try:
        return suggest_answers_with_langchain(input_payload)
    except LangChainUnavailableError:
        return None
    except Exception as exc:
        logger.warning("LangChain suggestion failed, falling back to rules: %s", exc)
        return None


def _profile_to_dict(profile: Profile | None) -> dict[str, str]:
    """Convert a Profile into a plain dict for the LLM payload."""

    if profile is None:
        return {}
    result: dict[str, str] = {}
    for key in PROFILE_KEYS:
        value = get_profile_value(profile, key)
        if value not in (None, ""):
            result[key] = value
    for key, value in profile.custom_values.items():
        if value not in (None, ""):
            result[f"custom:{key}"] = value
    return result


def _suggest_with_rules(
    db: Session,
    *,
    task: Task,
    fields: list[FormField],
    profile: Profile | None,
) -> list[AnswerSuggestion]:
    """Generate suggestions using rules, memory, and policy evidence only."""

    workflow_type = task.workflow_type or "form_fill"
    suggestions: list[AnswerSuggestion] = []

    for field in fields:
        if not _is_fillable(field):
            suggestions.append(
                _build_suggestion(
                    field,
                    answer_status="unsupported",
                    reason="Non-fillable field type",
                )
            )
            continue

        if _is_sensitive_field(field):
            suggestions.append(
                _build_suggestion(
                    field,
                    answer_status="sensitive_blocked",
                    reason="Sensitive or one-time value — never auto-filled",
                    safety_flags=["sensitive", "password_or_otp" if field.field_type == "password" else "sensitive_field"],
                )
            )
            continue

        query = _question_text(field)

        profile_value, profile_key, profile_confidence, profile_reason = (
            _suggest_from_profile(field, profile)
        )

        memory_hits: list = []
        policy_hits: list = []

        if is_memory_eligible_field(field):
            memory_hits = retrieve_reviewed_memory(
                db,
                profile_id=task.profile_id or 0,
                workflow_type=workflow_type,
                query=query,
            )

        if workflow_type == "security_questionnaire":
            policy_hits = retrieve_policy_sources(query, limit=3)

        source_ids = [hit.source_id for hit in policy_hits]
        memory_ids = [hit.memory_id for hit in memory_hits]

        stale_memory = any(hit.stale for hit in memory_hits)
        non_reusable_policy = any(
            hit.score < 0.3 for hit in policy_hits
        )

        if profile_value is not None:
            combined_confidence = profile_confidence
            reason_parts = [profile_reason]

            if memory_hits and not stale_memory:
                combined_confidence = min(profile_confidence + 0.04, 0.98)
                reason_parts.append(
                    f"Supported by {len(memory_hits)} reviewed memory hit(s)"
                )
            elif stale_memory:
                reason_parts.append("Stale memory matches available — review recommended")

            if policy_hits:
                if "encryption" in query.lower() or "encrypt" in query.lower():
                    combined_confidence = max(combined_confidence, 0.78)
                reason_parts.append(
                    f"Policy evidence: {policy_hits[0].section}"
                )

            safety_flags: list[str] = []
            if stale_memory:
                safety_flags.append("stale_memory_review")
            if non_reusable_policy:
                safety_flags.append("policy_review_recommended")

            suggestions.append(
                _build_suggestion(
                    field,
                    answer_status="suggested",
                    suggested_value=profile_value,
                    confidence=combined_confidence,
                    reason="; ".join(reason_parts),
                    source_ids=source_ids,
                    memory_ids=memory_ids,
                    safety_flags=safety_flags,
                    mapped_profile_key=profile_key,
                )
            )
            continue

        if policy_hits:
            top_hit = policy_hits[0]
            policy_confidence = min(top_hit.score + 0.2, 0.75)
            suggestions.append(
                _build_suggestion(
                    field,
                    answer_status="requires_user_input",
                    confidence=policy_confidence,
                    reason=(
                        f"Policy section '{top_hit.section}' is relevant — "
                        "review and confirm value"
                    ),
                    source_ids=source_ids,
                    memory_ids=memory_ids,
                    safety_flags=["policy_review_required"],
                )
            )
            continue

        if memory_hits and not stale_memory:
            top_mem = memory_hits[0]
            suggestions.append(
                _build_suggestion(
                    field,
                    answer_status="requires_user_input",
                    confidence=top_mem.confidence,
                    reason=(
                        f"Memory match to '{top_mem.profile_key}' — "
                        "review before applying"
                    ),
                    source_ids=source_ids,
                    memory_ids=memory_ids,
                    safety_flags=["memory_review_recommended"],
                )
            )
            continue

        suggestions.append(
            _build_suggestion(
                field,
                answer_status="unsupported",
                reason="No profile match, memory hit, or policy evidence found",
                source_ids=source_ids,
                memory_ids=memory_ids,
            )
        )

    return suggestions
