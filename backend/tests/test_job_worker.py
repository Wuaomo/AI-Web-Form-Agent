"""Tests for job worker service to ensure proper job execution and retry behavior."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    AgentToolCall,
    AgentToolResult,
    FormField,
    Job,
    Profile,
    Task,
    utc_now,
)
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
from app.services.form_extractor import ExtractedFormField


@pytest.fixture
def db_session(tmp_path):
    """Create a temporary database session for tests."""

    db_path = tmp_path / "job_worker_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    yield session, task.id

    session.close()


def test_execute_job_unknown_type_fails(db_session):
    """Verify execute_job fails with structured error for unknown job type."""

    from app.services.job_worker import execute_job
    from app.models import Job

    db, task_id = db_session

    job = Job(
        task_id=task_id,
        job_type="UNKNOWN_TYPE",
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
    )
    db.add(job)
    db.commit()

    execute_job(db=db, job=job)

    db.refresh(job)
    assert job.status == JOB_STATUS_FAILED
    assert job.error_reason == "UNKNOWN_JOB_TYPE"


def test_execute_job_analyze_calls_workflow_stage(db_session):
    """Verify execute_job calls analyze stage for ANALYZE_FORM jobs."""

    from app.services.job_worker import execute_job
    from app.models import Job

    db, task_id = db_session

    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
    )
    db.add(job)
    db.commit()

    with patch("app.services.job_worker._execute_analyze_stage") as mock_analyze:
        mock_analyze.return_value = True
        execute_job(db=db, job=job)

        mock_analyze.assert_called_once_with(db, job)

    db.refresh(job)
    assert job.status == JOB_STATUS_SUCCEEDED


def test_execute_job_map_calls_workflow_stage(db_session):
    """Verify execute_job calls mapping stage for MAP_FIELDS jobs."""

    from app.services.job_worker import execute_job
    from app.models import Job

    db, task_id = db_session

    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_MAP_FIELDS,
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
    )
    db.add(job)
    db.commit()

    with patch("app.services.job_worker._execute_map_stage") as mock_map:
        mock_map.return_value = True
        execute_job(db=db, job=job)

        mock_map.assert_called_once_with(db, job)

    db.refresh(job)
    assert job.status == JOB_STATUS_SUCCEEDED


def test_execute_job_fill_calls_workflow_stage(db_session):
    """Verify execute_job calls fill stage for FILL_FORM jobs."""

    from app.services.job_worker import execute_job
    from app.models import Job

    db, task_id = db_session

    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_FILL_FORM,
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
    )
    db.add(job)
    db.commit()

    with patch("app.services.job_worker._execute_fill_stage") as mock_fill:
        mock_fill.return_value = True
        execute_job(db=db, job=job)

        mock_fill.assert_called_once_with(db, job)

    db.refresh(job)
    assert job.status == JOB_STATUS_SUCCEEDED


def test_execute_job_retryable_exception_schedules_retry(db_session):
    """Verify execute_job schedules retry for retryable exceptions."""

    from app.services.job_worker import execute_job, RetryableError
    from app.models import Job

    db, task_id = db_session

    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
    )
    db.add(job)
    db.commit()

    with patch("app.services.job_worker._execute_analyze_stage") as mock_analyze:
        mock_analyze.side_effect = RetryableError("temporary failure")
        execute_job(db=db, job=job)

    db.refresh(job)
    assert job.status == JOB_STATUS_RETRY_SCHEDULED
    assert job.next_run_at is not None


def test_execute_job_non_retryable_exception_fails(db_session):
    """Verify execute_job fails permanently for non-retryable exceptions."""

    from app.services.job_worker import execute_job
    from app.models import Job

    db, task_id = db_session

    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
    )
    db.add(job)
    db.commit()

    with patch("app.services.job_worker._execute_analyze_stage") as mock_analyze:
        mock_analyze.side_effect = ValueError("permanent failure")
        execute_job(db=db, job=job)

    db.refresh(job)
    assert job.status == JOB_STATUS_FAILED
    assert job.next_run_at is None


def test_run_worker_once_claims_and_executes_job(db_session):
    """Verify run_worker_once claims and executes a pending job."""

    from app.services.job_worker import run_worker_once
    from app.services.job_queue import enqueue_job

    db, task_id = db_session

    enqueue_job(db=db, job_type=JOB_TYPE_ANALYZE_FORM, task_id=task_id)
    db.commit()

    with patch("app.services.job_worker._execute_analyze_stage") as mock_analyze:
        mock_analyze.return_value = True
        result = run_worker_once(db=db, worker_id="worker-1")

    assert result is True


def test_run_worker_once_no_job_returns_false(db_session):
    """Verify run_worker_once returns False when no job is available."""

    from app.services.job_worker import run_worker_once

    db, _ = db_session

    result = run_worker_once(db=db, worker_id="worker-1")

    assert result is False


def test_execute_analyze_stage_persists_runtime_tool_call(db_session):
    """Verify worker analysis records the browser read as a runtime tool call."""

    from app.services.job_worker import _execute_analyze_stage

    db, task_id = db_session
    field = ExtractedFormField(
        element_ref="field_1",
        form_title="Contact information",
        section_title=None,
        label="Email",
        selector="#email",
        field_type="email",
        placeholder=None,
        name="email",
        html_id="email",
        current_value=None,
        required=True,
    )
    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
    )
    db.add(job)
    db.commit()

    with patch(
        "app.services.form_extractor.extract_form_analysis",
        new=AsyncMock(return_value=MagicMock(fields=[field], login_required=False)),
    ):
        _execute_analyze_stage(db, job)

    call = db.get(AgentToolCall, f"task-{task_id}:extract_form")
    assert call is not None
    assert call.tool_name == "extract_form"
    assert call.status == "SUCCEEDED"
    assert call.governance_decision["decision"] == "ALLOW"
    result = db.get(AgentToolResult, f"task-{task_id}:extract_form")
    assert result is not None
    assert result.output_json["field_count"] == 1
    assert result.output_json["login_required"] is False


def test_execute_fill_stage_blocks_required_policy_review(db_session):
    """Verify worker fill path refuses required fields that still need approval."""

    from app.services.job_worker import _execute_fill_stage

    db, task_id = db_session
    task = db.get(Task, task_id)
    task.status = "READY_TO_FILL"
    task.workflow_status = "READY_TO_FILL"
    field = FormField(
        task_id=task_id,
        label="Agree to terms",
        selector="#terms",
        field_type="checkbox",
        required=True,
        mapped_profile_key="custom:terms",
        mapped_value="true",
        confidence=1.0,
    )
    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_FILL_FORM,
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
    )
    db.add_all([field, job])
    db.commit()

    with pytest.raises(ValueError, match="Required fields require approval before filling"):
        _execute_fill_stage(db, job)


def test_execute_fill_stage_persists_runtime_tool_call(db_session):
    """Verify worker fill records the browser write as a runtime tool call."""

    from app.services.job_worker import _execute_fill_stage

    db, task_id = db_session
    task = db.get(Task, task_id)
    task.status = "READY_TO_FILL"
    task.workflow_status = "READY_TO_FILL"
    field = FormField(
        task_id=task_id,
        label="Email",
        selector="#email",
        field_type="email",
        required=True,
        mapped_profile_key="email",
        mapped_value="ada@example.com",
        confidence=0.99,
    )
    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_FILL_FORM,
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
    )
    db.add_all([field, job])
    db.commit()

    with patch(
        "app.services.browser_executor.fill_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as fill_form:
        fill_form.return_value = (MagicMock(id=9), [])
        _execute_fill_stage(db, job)

    call = db.get(AgentToolCall, f"task-{task_id}:fill_form")
    assert call is not None
    assert call.tool_name == "fill_form"
    assert call.status == "SUCCEEDED"
    assert call.governance_decision["decision"] == "VERIFY_REQUIRED"
    result = db.get(AgentToolResult, f"task-{task_id}:fill_form")
    assert result is not None
    assert result.output_json == {
        "filled_count": 1,
        "screenshot_id": 9,
        "verification_count": 0,
    }


def test_execute_benchmark_stage_passes_runtime_mode_and_db(db_session):
    """Verify queued runtime benchmarks persist through the shared runner."""

    from app.services.benchmark_runner import BenchmarkRunSummary
    from app.services.job_worker import _execute_benchmark_stage

    db, task_id = db_session
    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_RUN_BENCHMARK,
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
    )
    job.payload = {"mode": "runtime"}
    db.add(job)
    db.commit()

    def fake_run_benchmarks(
        *,
        mode: str,
        provider: str | None,
        db,
        stress_mode: str = "standard",
        memory_mode: str = "off",
        baseline_run_id: int | None = None,
    ) -> BenchmarkRunSummary:
        assert mode == "runtime"
        assert provider is None
        assert db is db_session[0]
        assert stress_mode == "standard"
        assert memory_mode == "off"
        assert baseline_run_id is None
        return BenchmarkRunSummary(
            mode="runtime",
            provider=None,
            total_cases=0,
            average_score=1.0,
            summary_metrics={"governed_runtime_path_rate": 1.0},
            case_results=[],
        )

    with patch("app.services.benchmark_runner.run_benchmarks", side_effect=fake_run_benchmarks) as mocked_runner:
        _execute_benchmark_stage(db, job)

    mocked_runner.assert_called_once()


def test_execute_benchmark_stage_passes_queued_options(db_session):
    """Verify queued benchmark options reach the shared runner."""

    from app.services.benchmark_runner import BenchmarkRunSummary
    from app.services.job_worker import _execute_benchmark_stage

    db, task_id = db_session
    job = Job(
        task_id=task_id,
        job_type=JOB_TYPE_RUN_BENCHMARK,
        status=JOB_STATUS_RUNNING,
        attempts=1,
        max_attempts=3,
    )
    job.payload = {
        "mode": "runtime",
        "stress_mode": "cache_warm",
        "memory_mode": "off",
        "baseline_run_id": 42,
    }
    db.add(job)
    db.commit()

    def fake_run_benchmarks(
        *,
        mode: str,
        provider: str | None,
        db,
        stress_mode: str = "standard",
        memory_mode: str = "off",
        baseline_run_id: int | None = None,
    ) -> BenchmarkRunSummary:
        assert mode == "runtime"
        assert provider is None
        assert stress_mode == "cache_warm"
        assert memory_mode == "off"
        assert baseline_run_id == 42
        return BenchmarkRunSummary(
            mode="runtime",
            provider=None,
            total_cases=0,
            average_score=1.0,
            summary_metrics={"governed_runtime_path_rate": 1.0},
            case_results=[],
        )

    with patch(
        "app.services.benchmark_runner.run_benchmarks",
        side_effect=fake_run_benchmarks,
    ):
        _execute_benchmark_stage(db, job)
