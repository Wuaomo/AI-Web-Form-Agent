"""Worker execution service for processing async jobs from the queue."""

import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Job, Task
from app.job_constants import (
    JOB_TYPE_ANALYZE_FORM,
    JOB_TYPE_MAP_FIELDS,
    JOB_TYPE_FILL_FORM,
    JOB_TYPE_RUN_BENCHMARK,
    JOB_STATUS_RETRY_SCHEDULED,
)
from app.services.job_queue import (
    claim_next_job,
    mark_job_succeeded,
    mark_job_failed,
    record_worker_heartbeat,
)
from app.services.metrics_sidecar_client import emit_metrics_event
from app.services.workflow_state_service import set_workflow_status
from app.workflow_constants import (
    FAILURE_ANALYSIS_FAILED,
    FAILURE_LLM_MAPPING_FAILED,
    FAILURE_BROWSER_FILL_FAILED,
    WORKFLOW_STATUS_ANALYZING,
    WORKFLOW_STATUS_FAILED,
    WORKFLOW_STATUS_FILLING,
    WORKFLOW_STATUS_MAPPING_READY,
    WORKFLOW_STATUS_WAITING_APPROVAL,
)


class RetryableError(Exception):
    """An error that should trigger a job retry."""

    pass


def execute_job(db: Session, job: Job) -> None:
    """Execute one claimed job and update job/task/checkpoint state.

    Routes the job to the appropriate workflow stage handler based on job_type.
    Handles exceptions and updates job status accordingly.

    Args:
        db: Database session
        job: The job to execute (must already be claimed/running)
    """

    started_at = time.monotonic()
    worker_id = job.locked_by or ""

    emit_metrics_event({
        "event_type": "job_started",
        "task_id": job.task_id or 0,
        "job_id": job.id,
        "job_type": job.job_type,
        "worker_id": worker_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    try:
        if job.job_type == JOB_TYPE_ANALYZE_FORM:
            _execute_analyze_stage(db, job)
        elif job.job_type == JOB_TYPE_MAP_FIELDS:
            _execute_map_stage(db, job)
        elif job.job_type == JOB_TYPE_FILL_FORM:
            _execute_fill_stage(db, job)
        elif job.job_type == JOB_TYPE_RUN_BENCHMARK:
            _execute_benchmark_stage(db, job)
        else:
            raise ValueError(f"Unknown job type: {job.job_type}")

        mark_job_succeeded(db, job)

        duration_ms = int((time.monotonic() - started_at) * 1000)
        emit_metrics_event({
            "event_type": "job_succeeded",
            "task_id": job.task_id or 0,
            "job_id": job.id,
            "job_type": job.job_type,
            "duration_ms": duration_ms,
            "worker_id": worker_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    except RetryableError as exc:
        mark_job_failed(
            db=db,
            job=job,
            error_reason=str(exc)[:100],
            error_message=str(exc),
            retry=True,
        )
        _emit_failure_event(job, started_at, is_retry=True, worker_id=worker_id)
    except Exception as exc:
        error_reason = _get_error_reason(job.job_type, exc)
        mark_job_failed(
            db=db,
            job=job,
            error_reason=error_reason,
            error_message=str(exc),
            retry=False,
        )
        _emit_failure_event(job, started_at, is_retry=False, worker_id=worker_id)


def run_worker_once(db: Session, worker_id: str, allowed_job_types: set[str] | None = None) -> bool:
    """Claim and execute one job. Return True when a job was processed.

    Records worker heartbeat before and after execution.

    Args:
        db: Database session
        worker_id: Unique identifier for this worker
        allowed_job_types: Optional set of job types to filter by

    Returns:
        True if a job was found and processed, False otherwise
    """

    record_worker_heartbeat(db=db, worker_id=worker_id, current_job_id=None, status="idle")

    job = claim_next_job(db=db, worker_id=worker_id, allowed_job_types=allowed_job_types)

    if job is None:
        return False

    record_worker_heartbeat(db=db, worker_id=worker_id, current_job_id=job.id, status="busy")

    try:
        execute_job(db=db, job=job)
        db.commit()
        return True
    finally:
        record_worker_heartbeat(db=db, worker_id=worker_id, current_job_id=None, status="idle")


def _emit_failure_event(job: Job, started_at: float, is_retry: bool, worker_id: str) -> None:
    """Emit a job_failed or job_retry_scheduled metrics event.

    Args:
        job: The job that failed
        started_at: Monotonic timestamp when the job started
        is_retry: Whether the failure will be retried
        worker_id: The worker ID that executed the job
    """

    duration_ms = int((time.monotonic() - started_at) * 1000)
    event_type = "job_retry_scheduled" if is_retry else "job_failed"
    emit_metrics_event({
        "event_type": event_type,
        "task_id": job.task_id or 0,
        "job_id": job.id,
        "job_type": job.job_type,
        "duration_ms": duration_ms,
        "worker_id": worker_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


def _execute_analyze_stage(db: Session, job: Job) -> None:
    """Execute the analyze form workflow stage.

    Args:
        db: Database session
        job: The job being executed
    """

    task = db.get(Task, job.task_id)
    if task is None:
        raise ValueError(f"Task {job.task_id} not found")

    from app.routers.tasks import (
        create_log,
        get_next_log_step,
        mark_login_required,
        save_extracted_fields,
    )
    from app.services.form_extractor import extract_form_analysis
    from app.services.form_analysis_cache import read_form_analysis_cache, write_form_analysis_cache
    from app.services.checkpoint_service import write_checkpoint
    from app.workflow_constants import WORKFLOW_STAGE_ANALYSIS, CHECKPOINT_SUCCESS, CHECKPOINT_FAILED

    import asyncio

    step = get_next_log_step(task.id, db)
    set_workflow_status(task, WORKFLOW_STATUS_ANALYZING, reason="analyze_started")
    create_log(
        task_id=task.id,
        step=step,
        action="analyze_form",
        message=f"Opening {task.url} and analyzing form fields.",
        status="STARTED",
        db=db,
    )
    db.flush()

    try:
        analysis = read_form_analysis_cache(db, task.url)
        if analysis is None:
            analysis = asyncio.run(extract_form_analysis(task.url, task.profile_id))
            write_form_analysis_cache(db, task.url, analysis)
        if analysis.login_required:
            mark_login_required(task, db)
        else:
            save_extracted_fields(task, analysis, db)
        write_checkpoint(
            task_id=task.id,
            stage=WORKFLOW_STAGE_ANALYSIS,
            status=CHECKPOINT_SUCCESS,
            input_hash=f"{task.url}:{task.profile_id}",
            output={"field_count": len(analysis.fields), "login_required": analysis.login_required},
            db=db,
        )
    except Exception as exc:
        write_checkpoint(
            task_id=task.id,
            stage=WORKFLOW_STAGE_ANALYSIS,
            status=CHECKPOINT_FAILED,
            input_hash=f"{task.url}:{task.profile_id}",
            failure_reason=FAILURE_ANALYSIS_FAILED,
            error_message=str(exc),
            db=db,
        )
        set_workflow_status(task, WORKFLOW_STATUS_FAILED, reason="analyze_failed")
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="analyze_form",
            message=f"Form analysis failed: {exc}",
            status="FAILED",
            db=db,
        )
        raise


def _execute_map_stage(db: Session, job: Job) -> None:
    """Execute the map fields workflow stage.

    Args:
        db: Database session
        job: The job being executed
    """

    task = db.get(Task, job.task_id)
    if task is None:
        raise ValueError(f"Task {job.task_id} not found")

    from app.services.field_mapper import map_fields_by_rules, map_fields_with_llm
    from app.services.checkpoint_service import write_checkpoint
    from app.services.llm_provider_config import is_provider_configured, resolve_llm_provider
    from app.workflow_constants import WORKFLOW_STAGE_MAPPING, CHECKPOINT_SUCCESS, CHECKPOINT_FAILED

    mode = job.payload.get("mode", "llm")
    provider = job.payload.get("provider")

    try:
        if mode == "llm":
            selected_provider = resolve_llm_provider(provider)
            if not is_provider_configured(selected_provider):
                raise ValueError(f"LLM provider {selected_provider} is not configured")
            fields = map_fields_with_llm(job.task_id, db, provider=selected_provider)
        else:
            fields = map_fields_by_rules(job.task_id, db)

        set_workflow_status(task, WORKFLOW_STATUS_MAPPING_READY, reason="mapping_completed")
        mapped_count = sum(1 for f in fields if f.mapped_profile_key)
        write_checkpoint(
            task_id=job.task_id,
            stage=WORKFLOW_STAGE_MAPPING,
            status=CHECKPOINT_SUCCESS,
            input_hash=f"{job.task_id}:{mode}:{provider or 'default'}",
            output={"field_count": len(fields), "mapped_count": mapped_count, "mode": mode},
            db=db,
        )
    except Exception as exc:
        write_checkpoint(
            task_id=job.task_id,
            stage=WORKFLOW_STAGE_MAPPING,
            status=CHECKPOINT_FAILED,
            input_hash=f"{job.task_id}:{mode}:{provider or 'default'}",
            failure_reason=FAILURE_LLM_MAPPING_FAILED if mode == "llm" else FAILURE_ANALYSIS_FAILED,
            error_message=str(exc),
            db=db,
        )
        set_workflow_status(task, WORKFLOW_STATUS_FAILED, reason="mapping_failed")
        raise


def _execute_fill_stage(db: Session, job: Job) -> None:
    """Execute the fill form workflow stage.

    Args:
        db: Database session
        job: The job being executed
    """

    task = db.get(Task, job.task_id)
    if task is None:
        raise ValueError(f"Task {job.task_id} not found")

    from sqlalchemy import select
    from app.models import FormField
    from app.routers.tasks import (
        create_log,
        get_next_log_step,
        get_missing_required_fields,
        missing_required_detail,
    )
    from app.services.browser_executor import fill_form_and_capture_screenshot
    from app.services.checkpoint_service import write_checkpoint
    from app.workflow_constants import WORKFLOW_STAGE_FILL, CHECKPOINT_SUCCESS, CHECKPOINT_FAILED

    import asyncio

    fields = list(
        db.scalars(
            select(FormField)
            .where(FormField.task_id == task.id)
            .order_by(FormField.id)
        )
    )
    mapped_fields = [field for field in fields if field.mapped_value]
    missing_required_fields = get_missing_required_fields(fields)

    if missing_required_fields:
        raise ValueError(missing_required_detail(missing_required_fields))

    if not mapped_fields:
        raise ValueError("No mapped fields are ready to fill")

    step = get_next_log_step(task.id, db)
    set_workflow_status(task, WORKFLOW_STATUS_FILLING, reason="fill_started")
    create_log(
        task_id=task.id,
        step=step,
        action="fill_form",
        message=f"Filling {len(mapped_fields)} mapped fields.",
        status="STARTED",
        db=db,
    )
    db.flush()

    try:
        asyncio.run(
            fill_form_and_capture_screenshot(
                task_id=task.id,
                url=task.url,
                profile_id=task.profile_id,
                fields=mapped_fields,
                stage="filled_form",
                db=db,
            )
        )
        set_workflow_status(task, WORKFLOW_STATUS_WAITING_APPROVAL, reason="fill_completed")
        write_checkpoint(
            task_id=task.id,
            stage=WORKFLOW_STAGE_FILL,
            status=CHECKPOINT_SUCCESS,
            input_hash=f"{task.id}:{len(mapped_fields)}",
            output={"filled_count": len(mapped_fields)},
            db=db,
        )
        create_log(
            task_id=task.id,
            step=step + 1,
            action="fill_form",
            message="Filled mapped fields and paused before submission.",
            status="SUCCESS",
            db=db,
        )
    except Exception as exc:
        write_checkpoint(
            task_id=task.id,
            stage=WORKFLOW_STAGE_FILL,
            status=CHECKPOINT_FAILED,
            input_hash=f"{task.id}:{len(mapped_fields)}",
            failure_reason=FAILURE_BROWSER_FILL_FAILED,
            error_message=str(exc),
            db=db,
        )
        set_workflow_status(task, WORKFLOW_STATUS_FAILED, reason="fill_failed")
        create_log(
            task_id=task.id,
            step=get_next_log_step(task.id, db),
            action="fill_form",
            message=f"Form filling failed: {exc}",
            status="FAILED",
            db=db,
        )
        raise


def _execute_benchmark_stage(db: Session, job: Job) -> None:
    """Execute the run benchmark workflow stage.

    Args:
        db: Database session
        job: The job being executed
    """

    from app.services.benchmark_runner import run_benchmarks
    from app.models import BenchmarkRun

    mode = job.payload.get("mode", "rules")
    provider = job.payload.get("provider")

    run = run_benchmarks(mode=mode, provider=provider)
    db.add(run)


def _get_error_reason(job_type: str, exc: Exception) -> str:
    """Determine the appropriate error reason code for a job failure.

    Args:
        job_type: The type of job that failed
        exc: The exception that was raised

    Returns:
        A short error reason code
    """

    if job_type == JOB_TYPE_ANALYZE_FORM:
        return FAILURE_ANALYSIS_FAILED
    elif job_type == JOB_TYPE_MAP_FIELDS:
        return FAILURE_LLM_MAPPING_FAILED
    elif job_type == JOB_TYPE_FILL_FORM:
        return FAILURE_BROWSER_FILL_FAILED
    elif job_type == JOB_TYPE_RUN_BENCHMARK:
        return "BENCHMARK_FAILED"
    else:
        return "UNKNOWN_JOB_TYPE"
