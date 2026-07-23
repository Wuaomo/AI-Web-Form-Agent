"""Stable schemas for answer suggestions, memory hits, and policy source hits.

These Pydantic models define the contract that a future LangChain/LangGraph
adapter will consume. No LLM calls happen here — these are pure data structures
with validation rules.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class MemoryHit(BaseModel):
    """One reviewed-memory match used as evidence for a suggestion."""

    memory_id: str
    profile_key: str
    matched_value: str | None = None
    source_label: str | None = None
    match_score: float = Field(ge=0.0, le=1.0, default=0.0)
    stale: bool = False


class PolicySourceHit(BaseModel):
    """One policy-document match used as evidence for a suggestion."""

    source_id: str
    document_name: str
    matched_section: str | None = None
    match_score: float = Field(ge=0.0, le=1.0, default=0.0)
    excerpt: str | None = None
    needs_review: bool = False


class AnswerSuggestion(BaseModel):
    """One answer suggestion for a questionnaire field or question.

    Validation rules:
    - ``confidence`` must be in [0.0, 1.0].
    - ``unsupported`` and ``sensitive_blocked`` statuses cannot carry a
      ``suggested_value`` — those statuses mean no value is proposed.
    """

    question_id: str
    field_id: str | None = None
    suggested_value: str | None = None
    mapped_profile_key: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    answer_status: Literal[
        "suggested", "unsupported", "sensitive_blocked", "requires_user_input"
    ]
    reason: str
    source_ids: list[str] = Field(default_factory=list)
    memory_ids: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def empty_value_for_non_suggestions(self) -> "AnswerSuggestion":
        """Reject suggested_value for statuses that must not propose a value."""

        if (
            self.answer_status in {"unsupported", "sensitive_blocked"}
            and self.suggested_value
        ):
            raise ValueError(
                "unsupported or sensitive suggestions cannot include a value"
            )
        return self


def validate_answer_suggestion_payload(
    payload: dict[str, object],
) -> AnswerSuggestion:
    """Validate a raw dict and return an AnswerSuggestion.

    Raises ``ValidationError`` (a ``ValueError`` subclass) if the payload
    violates the schema or business rules.
    """

    return AnswerSuggestion.model_validate(payload)
