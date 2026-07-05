"""Approval request endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ApprovalRequestResponse
from app.services.approval_gate_service import (
    approve_request,
    list_pending_approvals,
    reject_request,
)

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalRequestResponse])
def list_approvals(
    task_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[object]:
    """Return approval requests filtered by task or status."""

    return list_pending_approvals(db, task_id=task_id, status=status_filter)


@router.post("/{approval_id}/approve", response_model=ApprovalRequestResponse)
def approve_approval_request(
    approval_id: int,
    db: Session = Depends(get_db),
) -> object:
    """Approve a pending approval request."""

    try:
        request = approve_request(db, approval_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(request)
    return request


@router.post("/{approval_id}/reject", response_model=ApprovalRequestResponse)
def reject_approval_request(
    approval_id: int,
    db: Session = Depends(get_db),
) -> object:
    """Reject a pending approval request."""

    try:
        request = reject_request(db, approval_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(request)
    return request
