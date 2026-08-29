"""Shared Pydantic schemas for the governed agent runtime.

These models are contracts only. They do not execute tools, persist state, or
change existing task endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RiskLevel = Literal["low", "medium", "high", "blocked"]
RunMode = Literal["deterministic", "template_guided", "llm_structured"]
AgentRunStatus = Literal[
    "CREATED",
    "PLANNING",
    "RUNNING",
    "WAITING_REVIEW",
    "WAITING_APPROVAL",
    "VERIFYING",
    "COMPLETED",
    "FAILED",
    "BLOCKED",
    "CANCELLED",
]
PlanCreator = Literal["deterministic", "template", "llm", "user"]
ToolCallStatus = Literal[
    "PENDING",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "BLOCKED",
    "WAITING_REVIEW",
    "WAITING_APPROVAL",
]
ToolResultStatus = Literal["SUCCEEDED", "FAILED"]
ProposalType = Literal[
    "field_value",
    "open_ended_answer",
    "answer",
    "memory_write",
    "browser_navigation",
    "browser_click",
    "form_submit",
    "external_api_write",
]
ProposalStatus = Literal[
    "PENDING",
    "APPROVED",
    "EDITED",
    "REJECTED",
    "NEEDS_MORE_EVIDENCE",
]
EvidenceSourceType = Literal[
    "profile",
    "memory",
    "knowledge_source",
    "page",
    "policy_doc",
    "tool_result",
    "user_input",
    "verification",
]
ReviewDecisionValue = Literal[
    "approved",
    "edited",
    "rejected",
    "needs_more_evidence",
]
GovernanceDecisionValue = Literal[
    "ALLOW",
    "RECORD_ONLY",
    "REVIEW_REQUIRED",
    "APPROVAL_REQUIRED",
    "BLOCKED",
    "VERIFY_REQUIRED",
]
VerificationType = Literal[
    "field_value",
    "page_state",
    "navigation",
    "download",
    "saved_draft",
    "external_api_result",
    "memory_write",
]
RuntimeValue = str | int | float | bool | dict[str, Any] | list[Any] | None


def _utc_now() -> datetime:
    """Return an aware timestamp for new runtime objects."""

    return datetime.now(timezone.utc)


class RuntimeSchema(BaseModel):
    """Base settings shared by runtime contracts."""

    model_config = ConfigDict(extra="forbid")


class AgentRunState(RuntimeSchema):
    """A serializable user goal and current runtime status."""

    id: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    target_url: str | None = None
    profile_id: int | None = Field(default=None, ge=1)
    status: AgentRunStatus = "CREATED"
    mode: RunMode = "deterministic"
    context: dict[str, Any] = Field(default_factory=dict)
    current_plan_id: str | None = None
    final_result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class PlannedToolCall(RuntimeSchema):
    """One inspectable planned tool call inside an agent plan."""

    step_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    input_json: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = "low"
    expected_evidence: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)


class AgentPlan(RuntimeSchema):
    """A versioned plan made of typed tool calls."""

    id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    goal: str = Field(min_length=1)
    steps: list[PlannedToolCall] = Field(min_length=1)
    created_by: PlanCreator
    created_at: datetime = Field(default_factory=_utc_now)

    @model_validator(mode="after")
    def require_unique_step_ids(self) -> "AgentPlan":
        """Reject duplicate step IDs so plan state can address each step."""

        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("step_id values must be unique")
        return self


class GovernanceDecision(RuntimeSchema):
    """Action-level governance result for a tool call or proposal."""

    decision: GovernanceDecisionValue
    reason: str = Field(min_length=1)
    risk_level: RiskLevel = "low"
    requires_review: bool = False
    requires_approval: bool = False
    requires_verification: bool = False
    blocked_reason: str | None = None

    @model_validator(mode="after")
    def normalize_decision_flags(self) -> "GovernanceDecision":
        """Keep decision-specific flags explicit for downstream callers."""

        if self.decision == "REVIEW_REQUIRED":
            self.requires_review = True
        elif self.decision == "APPROVAL_REQUIRED":
            self.requires_approval = True
        elif self.decision == "VERIFY_REQUIRED":
            self.requires_verification = True
        elif self.decision == "BLOCKED" and not self.blocked_reason:
            raise ValueError("blocked_reason is required for BLOCKED decisions")
        return self


class ToolCall(RuntimeSchema):
    """A concrete tool call request tracked by the runtime."""

    id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    plan_step_id: str | None = None
    tool_name: str = Field(min_length=1)
    input_json: dict[str, Any] = Field(default_factory=dict)
    status: ToolCallStatus = "PENDING"
    risk_level: RiskLevel = "low"
    governance_decision: GovernanceDecision | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None

    @model_validator(mode="after")
    def require_chronological_timestamps(self) -> "ToolCall":
        """Reject impossible completed_at values when both timestamps exist."""

        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("completed_at must be after started_at")
        return self


class EvidenceItem(RuntimeSchema):
    """Source-backed support for a proposal or tool result."""

    id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    proposal_id: str | None = None
    source_type: EvidenceSourceType
    source_id: str | None = None
    source_title: str | None = None
    section_title: str | None = None
    quote_or_summary: str = Field(min_length=1)
    score: float | None = Field(default=None, ge=0, le=1)
    created_at: datetime = Field(default_factory=_utc_now)


class Proposal(RuntimeSchema):
    """A reviewable value, browser action, memory write, or external write."""

    id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    proposal_type: ProposalType
    target_type: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    proposed_value: RuntimeValue = None
    rationale: str = ""
    confidence: float | None = Field(default=None, ge=0, le=1)
    risk_level: RiskLevel = "low"
    status: ProposalStatus = "PENDING"
    evidence: list[EvidenceItem] = Field(default_factory=list)


class ReviewDecision(RuntimeSchema):
    """A human review decision for one proposal."""

    id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    decision: ReviewDecisionValue
    edited_value: RuntimeValue = None
    reviewer_note: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)

    @model_validator(mode="after")
    def require_value_for_edits(self) -> "ReviewDecision":
        """Edited decisions must include the replacement value."""

        if self.decision == "edited" and self.edited_value is None:
            raise ValueError("edited_value is required for edited decisions")
        return self


class VerificationCandidate(RuntimeSchema):
    """A requested verification that a future execution result can satisfy."""

    id: str | None = None
    run_id: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    verification_type: VerificationType
    expected: RuntimeValue = None
    evidence_required: list[str] = Field(default_factory=list)
    screenshot_id: int | None = None


class ToolResult(RuntimeSchema):
    """Normalized output from an executed runtime tool."""

    tool_call_id: str = Field(min_length=1)
    status: ToolResultStatus
    governance_decision: GovernanceDecision | None = None
    output_json: dict[str, Any] = Field(default_factory=dict)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    created_proposals: list[Proposal] = Field(default_factory=list)
    verification_candidates: list[VerificationCandidate] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def require_error_for_failures(self) -> "ToolResult":
        """Failed tool results must say what failed."""

        if self.status == "FAILED" and not self.error:
            raise ValueError("error is required for FAILED tool results")
        return self


__all__ = [
    "AgentPlan",
    "AgentRunState",
    "AgentRunStatus",
    "EvidenceItem",
    "EvidenceSourceType",
    "GovernanceDecision",
    "GovernanceDecisionValue",
    "PlanCreator",
    "PlannedToolCall",
    "Proposal",
    "ProposalStatus",
    "ProposalType",
    "ReviewDecision",
    "ReviewDecisionValue",
    "RiskLevel",
    "RunMode",
    "RuntimeValue",
    "ToolCall",
    "ToolCallStatus",
    "ToolResult",
    "ToolResultStatus",
    "VerificationCandidate",
    "VerificationType",
]
