"""Database-backed job queue service for async workflow scheduling."""

from datetime import timedelta
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Job, JobAttempt, WorkerHeartbeat
from app.job_constants import (
    JOB_TYPE_ANALYZE_FORM,
    JOB_TYPE_MAP_FIELDS,
    JOB_TYPE_FILL_FORM,
    JOB_TYPE_RUN_BENCHMARK,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SUCCEEDED,
    JOB_STATUS_FAILED,
    JOB_STATUS_RETRY_SCHEDULED,
)
from app.models import utc_now

VALID_JOB_TYPES = {
    JOB_TYPE_ANALYZE_FORM,
    JOB_TYPE_MAP_FIELDS,
    JOB_TYPE_FILL_FORM,
    JOB_TYPE_RUN_BENCHMARK,
}


def enqueue_job(
    db: Session,
    job_type: str,
    task_id: int | None,
    payload: dict | None = None,
    priority: int = 100,
    max_attempts: int = 3,
) -> Job:
    """Create a pending job.

    Args:
        db: Database session
        job_type: Type of job (ANALYZE_FORM, MAP_FIELDS, FILL_FORM, RUN_BENCHMARK)
        task_id: Optional task ID this job belongs to
        payload: Optional structured payload data
        priority: Job priority (lower numbers = higher priority)
        max_attempts: Maximum retry attempts before failure

    Returns:
        The created job record

    Raises:
        ValueError: If job_type is not one of the valid job types
    """

    if job_type not in VALID_JOB_TYPES:
        raise ValueError(f"Invalid job_type: {job_type}. Must be one of {VALID_JOB_TYPES}")

    job = Job(
        task_id=task_id,
        job_type=job_type,
        status=JOB_STATUS_PENDING,
        priority=priority,
        payload=payload or {},
        attempts=0,
        max_attempts=max_attempts,
    )
    db.add(job)
    db.flush()
    return job


def claim_next_job(
    db: Session,
    worker_id: str,
    allowed_job_types: set[str] | None = None,
) -> Job | None:
    """Lock and return the next runnable job.

    Uses an atomic UPDATE-with-WHERE pattern for SQLite-compatible locking.
    Claims both PENDING and RETRY_SCHEDULED jobs when their next_run_at has passed.

    Args:
        db: Database session
        worker_id: Unique identifier for the worker claiming this job
        allowed_job_types: Optional set of job types to filter by

    Returns:
        The claimed job, or None if no runnable job was found
    """

    now = utc_now()

    statement = select(Job).where(
        Job.status.in_([JOB_STATUS_PENDING, JOB_STATUS_RETRY_SCHEDULED]),
        (Job.next_run_at == None) | (Job.next_run_at <= now),
    )

    if allowed_job_types:
        statement = statement.where(Job.job_type.in_(allowed_job_types))

    statement = statement.order_by(Job.priority.asc(), Job.created_at.asc())

    pending_jobs = list(db.scalars(statement))

    for job in pending_jobs:
        update_statement = (
            update(Job)
            .where(
                Job.id == job.id,
                Job.status.in_([JOB_STATUS_PENDING, JOB_STATUS_RETRY_SCHEDULED]),
                (Job.next_run_at == None) | (Job.next_run_at <= now),
            )
            .values(
                status=JOB_STATUS_RUNNING,
                locked_by=worker_id,
                locked_at=now,
                attempts=Job.attempts + 1,
            )
            .execution_options(synchronize_session=False)
        )

        result = db.execute(update_statement)
        db.flush()

        if result.rowcount > 0:
            db.refresh(job)
            create_job_attempt(db=db, job_id=job.id, attempt_no=job.attempts, status=JOB_STATUS_RUNNING)
            return job

    return None


def create_job_attempt(
    db: Session,
    job_id: int,
    attempt_no: int,
    status: str,
) -> JobAttempt:
    """Create a job attempt record.

    Args:
        db: Database session
        job_id: The job this attempt belongs to
        attempt_no: The attempt number
        status: The initial status of the attempt

    Returns:
        The created job attempt record
    """

    attempt = JobAttempt(
        job_id=job_id,
        attempt_no=attempt_no,
        status=status,
    )
    db.add(attempt)
    db.flush()
    return attempt


def update_job_attempt(
    db: Session,
    job_id: int,
    attempt_no: int,
    status: str,
    error_reason: str | None = None,
    error_message: str | None = None,
) -> JobAttempt | None:
    """Update a job attempt record with final status.

    Args:
        db: Database session
        job_id: The job this attempt belongs to
        attempt_no: The attempt number to update
        status: The final status of the attempt
        error_reason: Optional error reason code
        error_message: Optional detailed error message

    Returns:
        The updated job attempt record, or None if not found
    """

    statement = select(JobAttempt).where(
        JobAttempt.job_id == job_id,
        JobAttempt.attempt_no == attempt_no,
    )
    attempt = db.scalar(statement)

    if attempt is None:
        return None

    attempt.status = status
    attempt.finished_at = utc_now()
    attempt.error_reason = error_reason
    attempt.error_message = error_message
    db.flush()
    return attempt


def mark_job_succeeded(db: Session, job: Job) -> None:
    """Mark a job as succeeded.

    Args:
        db: Database session
        job: The job to mark as succeeded
    """

    job.status = JOB_STATUS_SUCCEEDED
    job.locked_by = None
    job.locked_at = None
    update_job_attempt(db=db, job_id=job.id, attempt_no=job.attempts, status=JOB_STATUS_SUCCEEDED)
    db.flush()


def mark_job_failed(
    db: Session,
    job: Job,
    error_reason: str,
    error_message: str,
    retry: bool,
) -> None:
    """Mark a job as failed or schedule a retry.

    Args:
        db: Database session
        job: The job to mark as failed
        error_reason: Short reason code for the failure
        error_message: Detailed error message
        retry: Whether to schedule a retry if attempts remain
    """

    job.error_reason = error_reason
    job.error_message = error_message
    job.locked_by = None
    job.locked_at = None

    if retry and job.attempts < job.max_attempts:
        job.status = JOB_STATUS_RETRY_SCHEDULED
        job.next_run_at = utc_now() + timedelta(seconds=60 * (2 ** (job.attempts - 1)))
        update_job_attempt(db=db, job_id=job.id, attempt_no=job.attempts, status=JOB_STATUS_FAILED, error_reason=error_reason, error_message=error_message)
    else:
        job.status = JOB_STATUS_FAILED
        job.next_run_at = None
        update_job_attempt(db=db, job_id=job.id, attempt_no=job.attempts, status=JOB_STATUS_FAILED, error_reason=error_reason, error_message=error_message)

    db.flush()


def record_worker_heartbeat(
    db: Session,
    worker_id: str,
    current_job_id: int | None,
    status: str,
) -> WorkerHeartbeat:
    """Upsert worker heartbeat.

    Args:
        db: Database session
        worker_id: Unique identifier for the worker
        current_job_id: Optional ID of the job the worker is currently processing
        status: Worker status (e.g., running, busy, idle)

    Returns:
        The created or updated heartbeat record
    """

    statement = select(WorkerHeartbeat).where(WorkerHeartbeat.worker_id == worker_id)
    existing = db.scalar(statement)

    if existing is not None:
        existing.current_job_id = current_job_id
        existing.status = status
        existing.last_seen_at = utc_now()
        db.flush()
        return existing

    heartbeat = WorkerHeartbeat(
        worker_id=worker_id,
        current_job_id=current_job_id,
        status=status,
        last_seen_at=utc_now(),
    )
    db.add(heartbeat)
    db.flush()
    return heartbeat
