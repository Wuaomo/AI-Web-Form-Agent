"""Tests for shared agent runtime schemas."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.services.agent_runtime.schemas import (
    AgentPlan,
    AgentRunState,
    EvidenceItem,
    GovernanceDecision,
    PlannedToolCall,
    Proposal,
    ReviewDecision,
    ToolResult,
    VerificationCandidate,
)


def test_agent_plan_accepts_planned_tool_calls() -> None:
    """Verify deterministic plans can be represented as typed tool calls."""

    plan = AgentPlan(
        id="plan-1",
        run_id="run-1",
        version=1,
        goal="Complete this reviewed browser workflow",
        steps=[
            PlannedToolCall(
                step_id="inspect_page",
                tool_name="extract_form",
                reason="Find fillable fields before proposing changes.",
            )
        ],
        created_by="deterministic",
    )

    assert plan.steps[0].input_json == {}
    assert plan.steps[0].risk_level == "low"


def test_agent_plan_rejects_duplicate_step_ids() -> None:
    """Verify plan steps are addressable by stable unique IDs."""

    with pytest.raises(ValidationError, match="step_id values must be unique"):
        AgentPlan(
            id="plan-1",
            run_id="run-1",
            version=1,
            goal="Complete this reviewed browser workflow",
            steps=[
                PlannedToolCall(
                    step_id="inspect_page",
                    tool_name="extract_form",
                    reason="Inspect once.",
                ),
                PlannedToolCall(
                    step_id="inspect_page",
                    tool_name="map_fields",
                    reason="Duplicate IDs would make review state ambiguous.",
                ),
            ],
            created_by="deterministic",
        )


def test_proposal_requires_valid_confidence() -> None:
    """Verify proposal confidence is a normalized score."""

    with pytest.raises(ValidationError):
        Proposal(
            id="proposal-1",
            run_id="run-1",
            proposal_type="field_value",
            target_type="form_field",
            target_ref="field-1",
            proposed_value="Ada Lovelace",
            confidence=1.2,
        )


def test_review_decision_requires_value_for_edits() -> None:
    """Verify edited review decisions include the reviewer-provided value."""

    with pytest.raises(ValidationError, match="edited_value is required"):
        ReviewDecision(
            id="review-1",
            proposal_id="proposal-1",
            decision="edited",
        )


def test_tool_result_failure_requires_error() -> None:
    """Verify failed tool results carry a structured error message."""

    with pytest.raises(ValidationError, match="error is required"):
        ToolResult(
            tool_call_id="call-1",
            status="FAILED",
        )


def test_governance_block_requires_blocked_reason() -> None:
    """Verify blocked governance decisions explain why execution cannot proceed."""

    with pytest.raises(ValidationError, match="blocked_reason is required"):
        GovernanceDecision(
            decision="BLOCKED",
            reason="Sensitive field detected.",
            risk_level="high",
        )


def test_runtime_schema_serializes_nested_review_contract() -> None:
    """Verify proposals, evidence, governance, and verification share one contract."""

    created_at = datetime(2026, 8, 29, tzinfo=timezone.utc)
    evidence = EvidenceItem(
        id="evidence-1",
        run_id="run-1",
        proposal_id="proposal-1",
        source_type="knowledge_source",
        source_id="policy-doc-1",
        source_title="Security Policy",
        quote_or_summary="MFA is required for administrative access.",
        score=0.92,
        created_at=created_at,
    )
    proposal = Proposal(
        id="proposal-1",
        run_id="run-1",
        proposal_type="open_ended_answer",
        target_type="form_field",
        target_ref="question-1",
        proposed_value="Yes. MFA is required for administrative access.",
        rationale="Answer is supported by the selected security policy.",
        confidence=0.92,
        risk_level="medium",
        evidence=[evidence],
    )
    candidate = VerificationCandidate(
        id="verify-1",
        run_id="run-1",
        target_ref="question-1",
        verification_type="field_value",
        expected="Yes. MFA is required for administrative access.",
        evidence_required=["dom_value"],
    )
    result = ToolResult(
        tool_call_id="call-1",
        status="SUCCEEDED",
        output_json={"field_count": 1},
        evidence_items=[evidence],
        created_proposals=[proposal],
        verification_candidates=[candidate],
    )
    state = AgentRunState(
        id="run-1",
        goal="Complete the questionnaire after review",
        target_url="https://example.com/security",
        status="WAITING_REVIEW",
        current_plan_id="plan-1",
    )

    assert result.model_dump()["created_proposals"][0]["evidence"][0]["score"] == 0.92
    assert state.mode == "deterministic"
