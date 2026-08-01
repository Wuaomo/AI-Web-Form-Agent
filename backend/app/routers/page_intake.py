"""Page intake API endpoints."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Task
from app.schemas import PageIntakeAnalyzeRequest, PageIntakeResponse
from app.services.checkpoint_service import write_checkpoint
from app.services.page_intake_service import analyze_page_intake
from app.services.workflow_trace_service import safe_create_span, safe_finish_span
from app.workflow_constants import (
    CHECKPOINT_FAILED,
    CHECKPOINT_SUCCESS,
    SPAN_PHASE_EXTRACTION,
    SPAN_STATUS_FAILED,
    SPAN_STATUS_SUCCESS,
)

router = APIRouter(prefix="/page-intake", tags=["page-intake"])


@router.post("/analyze", response_model=PageIntakeResponse)
async def analyze_page_intake_endpoint(
    request: PageIntakeAnalyzeRequest,
    db: Session = Depends(get_db),
) -> PageIntakeResponse:
    """Analyze a page and return intake classification.

    When task_id is None the endpoint runs preview-only: no span, no checkpoint.
    When task_id is provided the endpoint validates task identity against the
    request, then records a trace and checkpoint.
    """

    task = None
    if request.task_id is not None:
        task = db.get(Task, request.task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found",
            )
        if task.url != request.url or task.profile_id != request.profile_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task url or profile_id does not match request",
            )

    span_id = None
    if task is not None:
        span_id = safe_create_span(
            task_id=request.task_id,
            phase=SPAN_PHASE_EXTRACTION,
            name="page_intake",
            input={"url": request.url, "user_goal": request.user_goal},
        )

    try:
        result = await analyze_page_intake(
            url=request.url,
            profile_id=request.profile_id,
            user_goal=request.user_goal,
        )

        if task is not None:
            write_checkpoint(
                db=db,
                task_id=request.task_id,
                stage="PAGE_INTAKE",
                status=CHECKPOINT_SUCCESS,
                input_hash=f"{request.url}:{request.profile_id}:{request.user_goal}",
                output=asdict(result),
            )
            db.commit()

        if span_id is not None:
            safe_finish_span(
                span_id,
                status=SPAN_STATUS_SUCCESS,
                output={
                    "page_type": result.page_type,
                    "recommended_workflow": result.recommended_workflow,
                    "confidence": result.confidence,
                },
            )

        return PageIntakeResponse(
            page_type=result.page_type,
            recommended_workflow=result.recommended_workflow,
            confidence=result.confidence,
            summary=result.summary,
            detected_fields=[
                {
                    "label": f.label,
                    "field_type": f.field_type,
                    "required": f.required,
                    "selector": f.selector,
                }
                for f in result.detected_fields
            ],
            risk_flags=list(result.risk_flags),
            blocked_reasons=list(result.blocked_reasons),
            evidence=[
                {
                    "source": e.source,
                    "text": e.text,
                    "reason": e.reason,
                }
                for e in result.evidence
            ],
        )

    except Exception as exc:
        if task is not None:
            write_checkpoint(
                db=db,
                task_id=request.task_id,
                stage="PAGE_INTAKE",
                status=CHECKPOINT_FAILED,
                input_hash=f"{request.url}:{request.profile_id}:{request.user_goal}",
                error_message=str(exc),
            )
            db.commit()

        if span_id is not None:
            safe_finish_span(
                span_id,
                status=SPAN_STATUS_FAILED,
                error_message=str(exc),
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
