"""Deterministic checkpoint read/write service for task workflow stages."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import TaskCheckpoint
from app.workflow_constants import (
    CHECKPOINT_FAILED,
    CHECKPOINT_SKIPPED,
    CHECKPOINT_SUCCESS,
)


def write_checkpoint(
    task_id: int,
    stage: str,
    status: str,
    input_hash: str | None = None,
    output: dict[str, object] | None = None,
    failure_reason: str | None = None,
    error_message: str | None = None,
    db: Session | None = None,
) -> TaskCheckpoint:
    """Write or update a checkpoint for a task stage.

    Callers that already have a database session can pass it in so the checkpoint
    is committed with the surrounding task operation. Other callers can use the
    helper directly and let it manage a short-lived session.

    Args:
        task_id: The task this checkpoint belongs to
        stage: Workflow stage constant (e.g., ANALYSIS, MAPPING, FILL)
        status: Checkpoint status constant (SUCCESS, FAILED, SKIPPED)
        input_hash: Optional hash of inputs for idempotency
        output: Structured output data to persist as JSON
        failure_reason: Optional failure reason constant
        error_message: Optional detailed error message
        db: Optional database session to use

    Returns:
        The persisted checkpoint record
    """

    if status not in (CHECKPOINT_SUCCESS, CHECKPOINT_FAILED, CHECKPOINT_SKIPPED):
        raise ValueError(f"Invalid checkpoint status: {status}")

    if db is not None:
        _write_checkpoint(db, task_id, stage, status, input_hash, output, failure_reason, error_message)
        db.flush()
        statement = select(TaskCheckpoint).where(
            TaskCheckpoint.task_id == task_id,
            TaskCheckpoint.stage == stage,
        ).order_by(TaskCheckpoint.created_at.desc())
        checkpoint = db.scalar(statement)
        if checkpoint:
            db.refresh(checkpoint)
        return checkpoint

    with SessionLocal() as session:
        _write_checkpoint(session, task_id, stage, status, input_hash, output, failure_reason, error_message)
        session.commit()
        statement = select(TaskCheckpoint).where(
            TaskCheckpoint.task_id == task_id,
            TaskCheckpoint.stage == stage,
        ).order_by(TaskCheckpoint.created_at.desc())
        checkpoint = session.scalar(statement)
        if checkpoint:
            session.refresh(checkpoint)
            session.expunge(checkpoint)
        return checkpoint


def _write_checkpoint(
    db: Session,
    task_id: int,
    stage: str,
    status: str,
    input_hash: str | None,
    output: dict[str, object] | None,
    failure_reason: str | None,
    error_message: str | None,
) -> None:
    """Internal helper to write checkpoint with an existing session."""

    statement = select(TaskCheckpoint).where(
        TaskCheckpoint.task_id == task_id,
        TaskCheckpoint.stage == stage,
    ).order_by(TaskCheckpoint.created_at.desc())
    existing = db.scalar(statement)

    if existing is not None:
        existing.status = status
        existing.input_hash = input_hash
        existing.output = output
        existing.failure_reason = failure_reason
        existing.error_message = error_message
    else:
        checkpoint = TaskCheckpoint(
            task_id=task_id,
            stage=stage,
            status=status,
            input_hash=input_hash,
            output=output,
            failure_reason=failure_reason,
            error_message=error_message,
        )
        db.add(checkpoint)


def read_checkpoint(
    task_id: int,
    stage: str,
    db: Session | None = None,
) -> TaskCheckpoint | None:
    """Read the latest checkpoint for a specific task stage.

    Args:
        task_id: The task to query
        stage: Workflow stage constant to filter by
        db: Optional database session to use

    Returns:
        The most recent checkpoint for the stage, or None if none exists
    """

    if db is not None:
        return _read_checkpoint(db, task_id, stage)

    with SessionLocal() as session:
        checkpoint = _read_checkpoint(session, task_id, stage)
        if checkpoint:
            session.expunge(checkpoint)
        return checkpoint


def _read_checkpoint(
    db: Session,
    task_id: int,
    stage: str,
) -> TaskCheckpoint | None:
    """Internal helper to read checkpoint with an existing session."""

    statement = select(TaskCheckpoint).where(
        TaskCheckpoint.task_id == task_id,
        TaskCheckpoint.stage == stage,
    ).order_by(TaskCheckpoint.created_at.desc())
    return db.scalar(statement)


def list_checkpoints(
    task_id: int,
    db: Session | None = None,
) -> list[TaskCheckpoint]:
    """List all checkpoints for a task, ordered by creation time.

    Args:
        task_id: The task to query
        db: Optional database session to use

    Returns:
        List of checkpoints ordered by creation time (newest first)
    """

    if db is not None:
        return _list_checkpoints(db, task_id)

    with SessionLocal() as session:
        checkpoints = _list_checkpoints(session, task_id)
        for checkpoint in checkpoints:
            session.expunge(checkpoint)
        return checkpoints


def _list_checkpoints(
    db: Session,
    task_id: int,
) -> list[TaskCheckpoint]:
    """Internal helper to list checkpoints with an existing session."""

    statement = select(TaskCheckpoint).where(
        TaskCheckpoint.task_id == task_id,
    ).order_by(TaskCheckpoint.created_at.desc(), TaskCheckpoint.id.desc())
    return list(db.scalars(statement))