"""Job-related API endpoints for monitoring and managing async jobs."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Job, WorkerHeartbeat
from app.schemas import JobResponse, WorkerHeartbeatResponse
from app.job_constants import (
    JOB_STATUS_PENDING,
    JOB_STATUS_RETRY_SCHEDULED,
    JOB_STATUS_CANCELLED,
)

router = APIRouter(tags=["jobs"])


@router.get("/jobs", response_model=list[JobResponse])
def list_jobs(db: Session = Depends(get_db)) -> list[Job]:
    """List all jobs ordered by creation time (newest first)."""

    jobs = db.scalars(
        select(Job)
        .order_by(Job.created_at.desc())
        .options(selectinload(Job.attempts_list))
    ).all()
    return jobs


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)) -> Job:
    """Get detailed information about a specific job including its attempts."""

    job = db.scalar(
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.attempts_list))
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/tasks/{task_id}/jobs", response_model=list[JobResponse])
def list_task_jobs(task_id: int, db: Session = Depends(get_db)) -> list[Job]:
    """List all jobs for a specific task ordered by creation time (newest first)."""

    jobs = db.scalars(
        select(Job)
        .where(Job.task_id == task_id)
        .order_by(Job.created_at.desc())
        .options(selectinload(Job.attempts_list))
    ).all()
    return jobs


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: int, db: Session = Depends(get_db)) -> Job:
    """Cancel a pending or retry-scheduled job.

    Only jobs with status PENDING or RETRY_SCHEDULED can be cancelled.
    Running, succeeded, failed, or already cancelled jobs cannot be cancelled.

    Args:
        job_id: The ID of the job to cancel

    Returns:
        The cancelled job with updated status

    Raises:
        HTTPException: 404 if job not found, 409 if job cannot be cancelled
    """

    job = db.scalar(
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.attempts_list))
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in [JOB_STATUS_PENDING, JOB_STATUS_RETRY_SCHEDULED]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel job with status: {job.status}",
        )

    job.status = JOB_STATUS_CANCELLED
    job.locked_by = None
    job.locked_at = None
    job.next_run_at = None
    db.commit()
    db.refresh(job)
    return job


@router.get("/workers/heartbeats", response_model=list[WorkerHeartbeatResponse])
def list_worker_heartbeats(db: Session = Depends(get_db)) -> list[WorkerHeartbeat]:
    """List all worker heartbeats to monitor worker availability."""

    heartbeats = db.scalars(
        select(WorkerHeartbeat)
        .order_by(WorkerHeartbeat.last_seen_at.desc())
    ).all()
    return heartbeats
