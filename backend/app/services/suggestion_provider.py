"""Rules-first suggestion provider.

Produces ``AnswerSuggestion`` objects by combining:
- Rule-based profile key matching (field_mapper)
- Local policy document evidence (policy_doc_retriever)
- Reviewed memory hits (reviewed_memory_retriever)

The provider is read-only — it never modifies ``FormField`` rows, writes to
the database, or performs browser actions.

``mode='llm'`` falls back to rules-only for now. A future LangChain adapter
can plug in here without changing the public interface.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import FormField, Profile, Task
from app.services.field_mapper import (
    NON_FILLABLE_FIELD_TYPES,
    PROFILE_KEYS,
    _match_profile_key,
    _normalize,
    get_profile_value,
)
from app.services.policy_doc_retriever import retrieve_policy_sources
from app.services.reviewed_memory_retriever import retrieve_reviewed_memory
from app.services.suggestion_types import AnswerSuggestion
from app.services.workflow_memory import is_memory_eligible_field

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
        ``'llm'`` falls back to rules-only (no LangChain yet).

    Returns
    -------
    list[AnswerSuggestion]
        One suggestion per input field, in the same order as ``fields``.
        The provider never writes to the database or modifies FormField rows.
    """

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
        needs_review = any(hit.needs_review for hit in policy_hits)

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
                    f"Policy evidence: {policy_hits[0].matched_section}"
                )

            safety_flags: list[str] = []
            if stale_memory:
                safety_flags.append("stale_memory_review")
            if needs_review:
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
            policy_confidence = min(top_hit.match_score + 0.2, 0.75)
            suggestions.append(
                _build_suggestion(
                    field,
                    answer_status="requires_user_input",
                    confidence=policy_confidence,
                    reason=(
                        f"Policy section '{top_hit.matched_section}' is relevant — "
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
                    confidence=top_mem.match_score,
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
