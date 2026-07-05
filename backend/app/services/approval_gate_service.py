"""Approval request persistence helpers for risky workflow actions."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApprovalRequest
from app.services.policy_engine import PolicyDecision
from app.services.workflow_trace_service import safe_create_span, safe_finish_span
from app.workflow_constants import (
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_PENDING,
    APPROVAL_STATUS_REJECTED,
    POLICY_DECISION_REVIEW_REQUIRED,
    SPAN_PHASE_APPROVAL,
    SPAN_STATUS_FAILED,
    SPAN_STATUS_SUCCESS,
)


def create_approval_request(
    db: Session,
    *,
    task_id: int,
    step_name: str,
    policy_decision: PolicyDecision,
    proposed_action: dict[str, object],
) -> ApprovalRequest:
    """Persist a pending approval request for a review-required action."""

    if policy_decision.decision != POLICY_DECISION_REVIEW_REQUIRED:
        raise ValueError("Approval requests can only be created for REVIEW_REQUIRED decisions")

    span_id = safe_create_span(
        task_id=task_id,
        phase=SPAN_PHASE_APPROVAL,
        name=f"approval_request:{step_name}",
        input={"step_name": step_name, "proposed_action": proposed_action},
    )

    request = ApprovalRequest(
        task_id=task_id,
        step_name=step_name,
        risk_type=policy_decision.risk_type,
        risk_level=policy_decision.risk_level,
        decision=policy_decision.decision,
        reason=policy_decision.reason,
        status=APPROVAL_STATUS_PENDING,
    )
    request.proposed_action = proposed_action
    db.add(request)
    db.flush()

    safe_finish_span(
        span_id,
        status=SPAN_STATUS_SUCCESS,
        output={"approval_id": request.id, "status": request.status},
    )
    return request


def list_pending_approvals(
    db: Session,
    task_id: int | None = None,
    status: str | None = None,
) -> list[ApprovalRequest]:
    """Return approval requests ordered newest first."""

    statement = select(ApprovalRequest)
    if task_id is not None:
        statement = statement.where(ApprovalRequest.task_id == task_id)
    if status is not None:
        statement = statement.where(ApprovalRequest.status == status)
    statement = statement.order_by(ApprovalRequest.created_at.desc(), ApprovalRequest.id.desc())
    return list(db.scalars(statement))


def approve_request(
    db: Session,
    approval_id: int,
    *,
    resolved_by: str = "local_user",
) -> ApprovalRequest:
    """Mark a pending approval request as approved."""

    request = db.get(ApprovalRequest, approval_id)
    if request is None:
        raise LookupError("Approval request not found")
    if request.status != APPROVAL_STATUS_PENDING:
        raise ValueError("Approval request has already been resolved")

    request.status = APPROVAL_STATUS_APPROVED
    request.resolved_by = resolved_by
    request.resolved_at = datetime.now(timezone.utc)
    db.add(request)
    db.flush()
    safe_create_span(
        task_id=request.task_id,
        phase=SPAN_PHASE_APPROVAL,
        name=f"approval_approved:{request.step_name}",
        status=SPAN_STATUS_SUCCESS,
        input={"approval_id": request.id},
        output={"status": request.status, "resolved_by": resolved_by},
    )
    return request


def reject_request(
    db: Session,
    approval_id: int,
    *,
    resolved_by: str = "local_user",
) -> ApprovalRequest:
    """Mark a pending approval request as rejected."""

    request = db.get(ApprovalRequest, approval_id)
    if request is None:
        raise LookupError("Approval request not found")
    if request.status != APPROVAL_STATUS_PENDING:
        raise ValueError("Approval request has already been resolved")

    request.status = APPROVAL_STATUS_REJECTED
    request.resolved_by = resolved_by
    request.resolved_at = datetime.now(timezone.utc)
    db.add(request)
    db.flush()
    safe_create_span(
        task_id=request.task_id,
        phase=SPAN_PHASE_APPROVAL,
        name=f"approval_rejected:{request.step_name}",
        status=SPAN_STATUS_FAILED,
        input={"approval_id": request.id},
        output={"status": request.status, "resolved_by": resolved_by},
    )
    return request


def has_pending_approval(db: Session, *, task_id: int, step_name: str) -> bool:
    """Return whether a pending approval exists for the given step."""

    statement = select(ApprovalRequest).where(
        ApprovalRequest.task_id == task_id,
        ApprovalRequest.step_name == step_name,
        ApprovalRequest.status == APPROVAL_STATUS_PENDING,
    )
    return db.scalar(statement) is not None


def latest_approved_request(
    db: Session,
    *,
    task_id: int,
    step_name: str,
) -> ApprovalRequest | None:
    """Return the newest approved request for one task step."""

    statement = (
        select(ApprovalRequest)
        .where(
            ApprovalRequest.task_id == task_id,
            ApprovalRequest.step_name == step_name,
            ApprovalRequest.status == APPROVAL_STATUS_APPROVED,
        )
        .order_by(ApprovalRequest.resolved_at.desc(), ApprovalRequest.id.desc())
    )
    return db.scalar(statement)
