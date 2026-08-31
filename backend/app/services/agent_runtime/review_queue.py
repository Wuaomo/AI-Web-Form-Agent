"""Compatibility helpers for proposal-based review items."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AgentEvidenceItem,
    AgentProposal,
    AgentReviewDecision,
    AgentRun,
    FormField,
    Task,
    TaskCheckpoint,
)
from app.services.agent_runtime.schemas import EvidenceItem, Proposal, ReviewDecision
from app.services.workflow_memory import (
    should_save_answer_memory,
    should_save_mapping_memory,
)
from app.workflow_constants import WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE

ACTION_FIELD_TYPES = {"button", "file", "submit", "reset", "image"}


def build_task_review_proposals(
    *,
    task: Task,
    fields: list[FormField],
    checkpoints: list[TaskCheckpoint],
) -> list[Proposal]:
    """Project existing mapping review rows into generic runtime proposals."""

    evidence_by_field_id = _evidence_by_field_id(task.id, checkpoints)
    field_proposals = [
        _field_proposal(task, field, evidence_by_field_id.get(field.id, []))
        for field in fields
        if _is_reviewable_field(field)
    ]
    memory_proposals = [
        proposal
        for field in fields
        for proposal in _memory_write_proposals(task, field)
    ]
    return field_proposals + memory_proposals


def load_persisted_task_review_proposals(
    db: Session,
    *,
    task: Task,
) -> list[Proposal]:
    """Restore review proposals already persisted for the task runtime run."""

    run = db.execute(
        select(AgentRun)
        .where(AgentRun.legacy_task_id == task.id)
        .order_by(AgentRun.updated_at.desc(), AgentRun.created_at.desc())
    ).scalars().first()
    if run is None:
        return []

    rows = list(
        db.scalars(
            select(AgentProposal)
            .where(AgentProposal.run_id == run.id)
            .order_by(AgentProposal.created_at, AgentProposal.id)
        )
    )
    return [_proposal_from_row(row) for row in rows]


def persist_task_review_proposals(
    db: Session,
    *,
    task: Task,
    proposals: list[Proposal],
) -> None:
    """Double-write Review Mapping proposals into runtime persistence tables."""

    _ensure_agent_run(db, task)
    for proposal in proposals:
        row = db.get(AgentProposal, proposal.id)
        if row is None:
            row = AgentProposal(
                id=proposal.id,
                run_id=proposal.run_id,
                proposal_type=proposal.proposal_type,
                target_type=proposal.target_type,
                target_ref=proposal.target_ref,
                proposed_value_json="null",
                rationale=proposal.rationale,
                risk_level=proposal.risk_level,
                status=proposal.status,
            )
            db.add(row)

        row.run_id = proposal.run_id
        row.proposal_type = proposal.proposal_type
        row.target_type = proposal.target_type
        row.target_ref = proposal.target_ref
        row.proposed_value = proposal.proposed_value
        row.rationale = proposal.rationale
        row.confidence = proposal.confidence
        row.risk_level = proposal.risk_level
        if row.status == "PENDING" or proposal.status != "PENDING":
            row.status = proposal.status

        for evidence in proposal.evidence:
            _upsert_evidence_item(db, evidence)


def persist_review_decision(
    db: Session,
    *,
    decision: ReviewDecision,
) -> None:
    """Double-write a proposal review decision and update proposal status."""

    row = db.get(AgentReviewDecision, decision.id)
    if row is None:
        row = AgentReviewDecision(
            id=decision.id,
            proposal_id=decision.proposal_id,
            decision=decision.decision,
        )
        db.add(row)

    row.proposal_id = decision.proposal_id
    row.decision = decision.decision
    row.edited_value = decision.edited_value
    row.reviewer_note = decision.reviewer_note

    proposal = db.get(AgentProposal, decision.proposal_id)
    if proposal is not None:
        proposal.status = _proposal_status_for_decision(decision.decision)
        if decision.decision == "edited":
            proposal.proposed_value = decision.edited_value


def _proposal_from_row(row: AgentProposal) -> Proposal:
    latest_decision = _latest_decision(row.review_decisions)
    proposed_value = row.proposed_value
    if latest_decision is not None and latest_decision.decision == "edited":
        proposed_value = latest_decision.edited_value

    return Proposal(
        id=row.id,
        run_id=row.run_id,
        proposal_type=row.proposal_type,
        target_type=row.target_type,
        target_ref=row.target_ref,
        proposed_value=proposed_value,
        rationale=row.rationale,
        confidence=row.confidence,
        risk_level=row.risk_level,
        status=(
            _proposal_status_for_decision(latest_decision.decision)
            if latest_decision is not None
            else row.status
        ),
        evidence=[
            EvidenceItem(
                id=evidence.id,
                run_id=evidence.run_id,
                proposal_id=evidence.proposal_id,
                source_type=evidence.source_type,
                source_id=evidence.source_id,
                source_title=evidence.source_title,
                section_title=evidence.section_title,
                quote_or_summary=evidence.quote_or_summary,
                score=evidence.score,
                created_at=evidence.created_at,
            )
            for evidence in sorted(
                row.evidence_items,
                key=lambda item: (item.created_at, item.id),
            )
        ],
    )


def _latest_decision(
    decisions: list[AgentReviewDecision],
) -> AgentReviewDecision | None:
    if not decisions:
        return None
    return max(decisions, key=lambda item: (item.created_at, item.id))


def _field_proposal(
    task: Task,
    field: FormField,
    evidence: list[EvidenceItem],
) -> Proposal:
    proposal_type = (
        "answer"
        if task.workflow_type == WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE
        else "field_value"
    )
    rationale = (
        "Review the proposed answer before browser execution."
        if proposal_type == "answer"
        else "Review the proposed field value before browser execution."
    )
    return Proposal(
        id=_proposal_id(task.id, field.id),
        run_id=_run_id(task.id),
        proposal_type=proposal_type,
        target_type="form_field",
        target_ref=str(field.id),
        proposed_value=field.mapped_value,
        rationale=rationale,
        confidence=field.confidence,
        risk_level=_risk_level(field),
        evidence=evidence,
    )


def _ensure_agent_run(db: Session, task: Task) -> AgentRun:
    run_id = _run_id(task.id)
    run = db.get(AgentRun, run_id)
    if run is None:
        run = AgentRun(
            id=run_id,
            legacy_task_id=task.id,
            goal=task.description or "Review proposed browser workflow items.",
            target_url=task.url,
            profile_id=task.profile_id,
            workflow_hint=task.workflow_type,
            status=task.workflow_status or task.status,
            mode="deterministic",
        )
        run.final_result = {}
        db.add(run)
    return run


def _upsert_evidence_item(db: Session, evidence: EvidenceItem) -> AgentEvidenceItem:
    row = db.get(AgentEvidenceItem, evidence.id)
    if row is None:
        row = AgentEvidenceItem(
            id=evidence.id,
            run_id=evidence.run_id,
            source_type=evidence.source_type,
            quote_or_summary=evidence.quote_or_summary,
        )
        db.add(row)

    row.run_id = evidence.run_id
    row.proposal_id = evidence.proposal_id
    row.source_type = evidence.source_type
    row.source_id = evidence.source_id
    row.source_title = evidence.source_title
    row.section_title = evidence.section_title
    row.quote_or_summary = evidence.quote_or_summary
    row.score = evidence.score
    return row


def _proposal_status_for_decision(decision: str) -> str:
    return {
        "approved": "APPROVED",
        "edited": "EDITED",
        "rejected": "REJECTED",
        "needs_more_evidence": "NEEDS_MORE_EVIDENCE",
    }[decision]


def _memory_write_proposals(task: Task, field: FormField) -> list[Proposal]:
    proposals: list[Proposal] = []
    if should_save_mapping_memory(field):
        proposals.append(
            _memory_write_proposal(
                task=task,
                field=field,
                kind="mapping",
                proposed_value=field.mapped_profile_key,
                rationale="Save this reviewed mapping for future retrieval.",
            )
        )
    if should_save_answer_memory(task, field):
        proposals.append(
            _memory_write_proposal(
                task=task,
                field=field,
                kind="answer",
                proposed_value="reviewed_answer",
                rationale="Save this reviewed answer for future retrieval.",
            )
        )
    return proposals


def _memory_write_proposal(
    *,
    task: Task,
    field: FormField,
    kind: str,
    proposed_value: str | None,
    rationale: str,
) -> Proposal:
    return Proposal(
        id=f"{_proposal_id(task.id, field.id)}-memory-{kind}",
        run_id=_run_id(task.id),
        proposal_type="memory_write",
        target_type="workflow_memory",
        target_ref=str(field.id),
        proposed_value=proposed_value,
        rationale=rationale,
        confidence=field.confidence,
        risk_level="medium",
    )


def _evidence_by_field_id(
    task_id: int,
    checkpoints: list[TaskCheckpoint],
) -> dict[int, list[EvidenceItem]]:
    evidence_by_field: dict[int, list[EvidenceItem]] = {}
    for checkpoint in checkpoints:
        if checkpoint.stage != "MAPPING":
            continue
        output = checkpoint.output
        for suggestion in _dict_items(output.get("retrieval_suggestions")):
            _append_evidence(
                evidence_by_field,
                _retrieval_evidence(task_id, suggestion),
            )
        for suggestion in _dict_items(output.get("source_suggestions")):
            for item in _source_evidence(task_id, suggestion):
                _append_evidence(evidence_by_field, item)
    return evidence_by_field


def _retrieval_evidence(
    task_id: int,
    suggestion: dict[str, Any],
) -> tuple[int, EvidenceItem] | None:
    field_id = _field_id(suggestion)
    if field_id is None:
        return None
    source_id = suggestion.get("source_id")
    profile_key = suggestion.get("mapped_profile_key")
    status = "stale" if suggestion.get("stale") else "reviewed"
    return (
        field_id,
        EvidenceItem(
            id=_evidence_id(task_id, field_id, "memory", len(str(source_id or ""))),
            run_id=_run_id(task_id),
            proposal_id=_proposal_id(task_id, field_id),
            source_type="memory",
            source_id=str(source_id) if source_id is not None else None,
            source_title="Reviewed memory",
            section_title=str(profile_key) if profile_key else None,
            quote_or_summary=f"Reviewed memory suggests profile.{profile_key} ({status}).",
            score=_score(suggestion),
        ),
    )


def _source_evidence(
    task_id: int,
    suggestion: dict[str, Any],
) -> list[tuple[int, EvidenceItem]]:
    field_id = _field_id(suggestion)
    if field_id is None:
        return []
    raw_items = _dict_items(suggestion.get("source_evidence"))
    if not raw_items:
        raw_items = [suggestion]
    return [
        (
            field_id,
            EvidenceItem(
                id=_evidence_id(task_id, field_id, "source", index),
                run_id=_run_id(task_id),
                proposal_id=_proposal_id(task_id, field_id),
                source_type=_source_type(item.get("source_type")),
                source_id=_optional_str(item.get("source_id") or suggestion.get("source_id")),
                source_title=_optional_str(
                    item.get("source_title") or suggestion.get("source")
                ),
                section_title=_optional_str(
                    item.get("section_title") or suggestion.get("matched_section")
                ),
                quote_or_summary=str(
                    item.get("quote_or_summary")
                    or item.get("content")
                    or "Source-backed suggestion requires review."
                ),
                score=_score(item) or _score(suggestion),
            ),
        )
        for index, item in enumerate(raw_items, start=1)
    ]


def _append_evidence(
    evidence_by_field: dict[int, list[EvidenceItem]],
    item: tuple[int, EvidenceItem] | None,
) -> None:
    if item is None:
        return
    field_id, evidence = item
    evidence_by_field.setdefault(field_id, []).append(evidence)


def _dict_items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _field_id(item: dict[str, Any]) -> int | None:
    value = item.get("field_id")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _score(item: dict[str, Any]) -> float | None:
    value = item.get("score")
    if isinstance(value, int | float) and 0 <= value <= 1:
        return float(value)
    return None


def _source_type(value: object) -> str:
    known_source_types = {
        "profile",
        "memory",
        "knowledge_source",
        "page",
        "policy_doc",
        "tool_result",
        "user_input",
        "verification",
    }
    if value in known_source_types:
        return str(value)
    return "knowledge_source"


def _optional_str(value: object) -> str | None:
    return str(value) if value not in (None, "") else None


def _is_reviewable_field(field: FormField) -> bool:
    return (field.field_type or "").lower() not in ACTION_FIELD_TYPES


def _risk_level(field: FormField) -> str:
    if field.required and not field.mapped_value:
        return "medium"
    if field.confidence is not None and field.confidence < 0.7:
        return "medium"
    return "low"


def _run_id(task_id: int) -> str:
    return f"task-{task_id}"


def _proposal_id(task_id: int, field_id: int) -> str:
    return f"task-{task_id}-field-{field_id}"


def _evidence_id(task_id: int, field_id: int, kind: str, index: int) -> str:
    return f"task-{task_id}-field-{field_id}-{kind}-{index}"


__all__ = [
    "build_task_review_proposals",
    "load_persisted_task_review_proposals",
    "persist_review_decision",
    "persist_task_review_proposals",
]
