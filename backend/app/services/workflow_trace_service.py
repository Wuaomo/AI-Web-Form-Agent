"""Persistence helpers for workflow run trace spans."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import WorkflowSpan
from app.workflow_constants import SPAN_STATUS_STARTED

logger = logging.getLogger("app.workflow_trace")


def create_span(
    db: Session,
    *,
    task_id: int,
    phase: str,
    name: str,
    status: str = SPAN_STATUS_STARTED,
    parent_span_id: int | None = None,
    input: dict[str, object] | None = None,
    output: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
    provider: str | None = None,
    model: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    estimated_cost: float = 0.0,
    latency_ms: int = 0,
    screenshot_id: int | None = None,
    error_message: str | None = None,
) -> WorkflowSpan:
    """Persist one workflow span."""

    span = WorkflowSpan(
        task_id=task_id,
        parent_span_id=parent_span_id,
        phase=phase,
        name=name,
        status=status,
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
        latency_ms=latency_ms,
        screenshot_id=screenshot_id,
        error_message=error_message,
    )
    span.input = input
    span.output = output
    span.span_metadata = metadata
    db.add(span)
    db.flush()
    return span


def finish_span(
    db: Session,
    span: WorkflowSpan,
    *,
    status: str,
    output: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
    provider: str | None = None,
    model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost: float | None = None,
    latency_ms: int | None = None,
    screenshot_id: int | None = None,
    error_message: str | None = None,
) -> WorkflowSpan:
    """Update a span when the workflow operation ends."""

    span.status = status
    if output is not None:
        span.output = output
    if metadata is not None:
        span.span_metadata = metadata
    if provider is not None:
        span.provider = provider
    if model is not None:
        span.model = model
    if prompt_tokens is not None:
        span.prompt_tokens = prompt_tokens
    if completion_tokens is not None:
        span.completion_tokens = completion_tokens
    if total_tokens is not None:
        span.total_tokens = total_tokens
    if estimated_cost is not None:
        span.estimated_cost = estimated_cost
    if latency_ms is not None:
        span.latency_ms = latency_ms
    if screenshot_id is not None:
        span.screenshot_id = screenshot_id
    if error_message is not None:
        span.error_message = error_message
    db.add(span)
    db.flush()
    return span


def list_spans_for_task(db: Session, task_id: int) -> list[WorkflowSpan]:
    """Return workflow spans ordered chronologically."""

    statement = (
        select(WorkflowSpan)
        .where(WorkflowSpan.task_id == task_id)
        .order_by(WorkflowSpan.created_at, WorkflowSpan.id)
    )
    return list(db.scalars(statement))


def safe_create_span(**kwargs) -> int | None:
    """Persist a span without allowing trace failures to break the workflow."""

    task_id = kwargs.get("task_id")
    phase = kwargs.get("phase")
    name = kwargs.get("name")
    try:
        with SessionLocal() as trace_db:
            span = create_span(trace_db, **kwargs)
            trace_db.commit()
            return span.id
    except Exception:
        logger.exception(
            "Failed to create workflow span for task_id=%s phase=%s name=%s",
            task_id,
            phase,
            name,
        )
        return None


def safe_finish_span(span_id: int | None, **kwargs) -> None:
    """Update a span without allowing trace failures to break the workflow."""

    if span_id is None:
        return

    try:
        with SessionLocal() as trace_db:
            span = trace_db.get(WorkflowSpan, span_id)
            if span is None:
                return
            finish_span(trace_db, span, **kwargs)
            trace_db.commit()
    except Exception:
        logger.exception("Failed to finish workflow span id=%s", span_id)
