"""Compatibility helpers for proposal-based review items."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AgentEvidenceItem,
    AgentProposal,
    AgentReviewDecision,
    AgentRun,
    ApprovalRequest,
    FormField,
    Task,
    TaskCheckpoint,
)
from app.services.agent_runtime.schemas import EvidenceItem, Proposal, ReviewDecision
from app.services.workflow_memory import (
    is_one_time_field,
    is_sensitive_field,
    should_save_answer_memory,
    should_save_mapping_memory,
)
from app.workflow_constants import WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE

ACTION_FIELD_TYPES = {"button", "file", "submit", "reset", "image"}


@dataclass(frozen=True)
class ReviewItemTarget:
    """Resolved compatibility target for a task review item decision."""

    proposal: AgentProposal | None
    field: FormField | None
    requires_form_field_sync: bool


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


def load_or_create_task_review_proposals(
    db: Session,
    *,
    task: Task,
    fields: list[FormField],
    checkpoints: list[TaskCheckpoint],
) -> list[Proposal]:
    """Return persisted review proposals, backfilling only missing legacy rows."""

    persisted = load_persisted_task_review_proposals(db, task=task)
    persisted_ids = {proposal.id for proposal in persisted}
    persisted_field_refs = {
        proposal.target_ref
        for proposal in persisted
        if proposal.target_type == "form_field"
    }
    derived = build_task_review_proposals(
        task=task,
        fields=fields,
        checkpoints=checkpoints,
    )
    missing = [
        proposal
        for proposal in derived
        if proposal.id not in persisted_ids
        and not (
            proposal.target_type == "form_field"
            and proposal.target_ref in persisted_field_refs
        )
    ]
    if missing:
        persist_task_review_proposals(db, task=task, proposals=missing)
    return persisted + missing


def load_persisted_task_review_proposal(
    db: Session,
    *,
    task: Task,
    proposal_id: str,
) -> Proposal | None:
    """Restore one persisted review proposal for the task runtime run."""

    row = db.scalar(
        select(AgentProposal)
        .join(AgentRun)
        .where(
            AgentProposal.id == proposal_id,
            AgentRun.legacy_task_id == task.id,
        )
    )
    return _proposal_from_row(row) if row is not None else None


def resolve_task_review_item_target(
    db: Session,
    *,
    task: Task,
    proposal_id: str,
) -> ReviewItemTarget | None:
    """Resolve persisted and legacy task review item ids to their sync target."""

    proposal = db.scalar(
        select(AgentProposal)
        .join(AgentRun)
        .where(
            AgentProposal.id == proposal_id,
            AgentRun.legacy_task_id == task.id,
        )
    )
    if proposal is not None:
        if proposal.target_type != "form_field":
            return ReviewItemTarget(proposal, None, False)
        if not proposal.target_ref.isdigit():
            return ReviewItemTarget(proposal, None, False)
        field = _task_field(db, task.id, int(proposal.target_ref))
        return ReviewItemTarget(proposal, field, field is not None)

    field_id = _field_id_from_review_proposal_id(task.id, proposal_id)
    if field_id is None:
        return None
    field = _task_field(db, task.id, field_id)
    return ReviewItemTarget(None, field, True) if field else None


def apply_review_decision_to_field_target(
    target: ReviewItemTarget,
    *,
    decision: str,
    edited_value: Any = None,
) -> None:
    """Sync a proposal review decision back to the legacy FormField row."""

    field = target.field
    if field is None:
        return
    if decision == "edited":
        field.mapped_value = str(edited_value)
        field.confidence = 1.0
    elif decision == "approved":
        if target.proposal is not None:
            value = target.proposal.proposed_value
            field.mapped_value = str(value) if value is not None else None
        field.confidence = 1.0 if field.mapped_value is not None else field.confidence
    elif decision == "rejected":
        field.mapped_profile_key = None
        field.mapped_value = None
        field.confidence = None


def split_fields_by_browser_write_review(
    db: Session,
    *,
    task: Task,
    fields: list[FormField],
) -> tuple[list[FormField], list[FormField]]:
    """Separate fields allowed for browser write from proposal-blocked fields."""

    fields_by_id = {field.id: field for field in fields}
    blocked_field_ids = {
        int(proposal.target_ref)
        for proposal in db.scalars(
            select(AgentProposal)
            .join(AgentRun)
            .where(
                AgentRun.legacy_task_id == task.id,
                AgentProposal.target_type == "form_field",
                AgentProposal.target_ref.in_(
                    [str(field_id) for field_id in fields_by_id]
                ),
                AgentProposal.status.notin_(["APPROVED", "EDITED"]),
            )
        )
        if proposal.target_ref.isdigit()
    }
    blocked_fields = [
        field
        for field in fields
        if field.id in blocked_field_ids and _is_reviewable_field(field)
    ]
    allowed_fields = [
        field
        for field in fields
        if field.id not in blocked_field_ids
    ]
    return allowed_fields, blocked_fields


def persist_submit_review_proposal(
    db: Session,
    *,
    task: Task,
    approval_request: ApprovalRequest,
) -> None:
    """Persist a high-risk proposal for an explicit submit approval gate."""

    proposed_action = approval_request.proposed_action
    fields = proposed_action.get("fields")
    persist_task_review_proposals(
        db,
        task=task,
        proposals=[
            Proposal(
                id=f"task-{task.id}-submit-{approval_request.id}",
                run_id=_run_id(task.id),
                proposal_type="form_submit",
                target_type="approval_request",
                target_ref=str(approval_request.id),
                proposed_value={
                    "action": "submit_form",
                    "approval_id": approval_request.id,
                    "field_count": len(fields) if isinstance(fields, list) else 0,
                },
                rationale=(
                    "Final form submission requires explicit approval "
                    "before browser execution."
                ),
                risk_level="high",
            )
        ],
    )


def sync_submit_review_proposal_decision(
    db: Session,
    *,
    approval_request: ApprovalRequest,
) -> None:
    """Mirror final submit approval status into its runtime proposal."""

    decision = {
        "APPROVED": "approved",
        "REJECTED": "rejected",
    }.get(approval_request.status)
    if approval_request.step_name != "submit_form" or decision is None:
        return

    proposal_id = f"task-{approval_request.task_id}-submit-{approval_request.id}"
    if db.get(AgentProposal, proposal_id) is None:
        return
    persist_review_decision(
        db,
        decision=ReviewDecision(
            id=f"decision-{proposal_id}",
            proposal_id=proposal_id,
            decision=decision,
        ),
    )


def persist_task_review_proposals(
    db: Session,
    *,
    task: Task,
    proposals: list[Proposal],
) -> None:
    """Double-write Review Mapping proposals into runtime persistence tables."""

    run = _ensure_agent_run(db, task)
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
        if row.status == "PENDING" or proposal.status != "PENDING":
            row.proposed_value = proposal.proposed_value
        row.rationale = proposal.rationale
        row.confidence = proposal.confidence
        row.risk_level = proposal.risk_level
        if row.status == "PENDING" or proposal.status != "PENDING":
            row.status = proposal.status

        evidence_ids = {evidence.id for evidence in proposal.evidence}
        for evidence_row in list(row.evidence_items):
            if evidence_row.id not in evidence_ids:
                db.delete(evidence_row)
        for evidence in proposal.evidence:
            _upsert_evidence_item(db, evidence)
    refresh_pending_review_count(db, run_id=run.id)


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
        refresh_pending_review_count(db, run_id=proposal.run_id)


def refresh_pending_review_count(db: Session, *, run_id: str) -> None:
    """Sync AgentRun.pending_review_count from persisted proposal statuses."""

    run = db.get(AgentRun, run_id)
    if run is None:
        return
    run.pending_review_count = len(
        list(
            db.scalars(
                select(AgentProposal.id).where(
                    AgentProposal.run_id == run_id,
                    AgentProposal.status == "PENDING",
                )
            )
        )
    )


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
    risk_level = _risk_level(field)
    if risk_level == "blocked":
        rationale = "Blocked: sensitive or one-time value cannot be auto-filled."
    elif proposal_type == "answer" and field.mapped_value in (None, "") and not evidence:
        rationale = "Unsupported: no profile match, reviewed memory, or policy evidence found."
    else:
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
        risk_level=risk_level,
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


def _task_field(db: Session, task_id: int, field_id: int) -> FormField | None:
    return db.scalar(
        select(FormField).where(
            FormField.id == field_id,
            FormField.task_id == task_id,
        )
    )


def _field_id_from_review_proposal_id(task_id: int, proposal_id: str) -> int | None:
    match = re.fullmatch(rf"task-{task_id}-field-(\d+)", proposal_id)
    return int(match.group(1)) if match else None


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
    if is_sensitive_field(field) or is_one_time_field(field):
        return "blocked"
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
    "apply_review_decision_to_field_target",
    "build_task_review_proposals",
    "load_or_create_task_review_proposals",
    "load_persisted_task_review_proposal",
    "load_persisted_task_review_proposals",
    "persist_review_decision",
    "persist_submit_review_proposal",
    "persist_task_review_proposals",
    "refresh_pending_review_count",
    "resolve_task_review_item_target",
    "split_fields_by_browser_write_review",
    "sync_submit_review_proposal_decision",
]
