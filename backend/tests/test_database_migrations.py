"""Tests for database migration helpers."""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text


def test_init_db_adds_profile_memory_policy_to_existing_form_fields_table(tmp_path):
    """Verify that _add_missing_form_field_columns adds profile_memory_policy to legacy tables."""

    from app.database import _add_missing_form_field_columns

    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}")

    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE form_fields (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                label VARCHAR(500),
                selector VARCHAR(1000) NOT NULL,
                field_type VARCHAR(100),
                placeholder VARCHAR(500),
                required BOOLEAN NOT NULL DEFAULT 0,
                mapped_profile_key VARCHAR(100),
                mapped_value TEXT,
                confidence FLOAT
            )
        """))

    _add_missing_form_field_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("form_fields")}
    assert "profile_memory_policy" in columns

    with engine.begin() as connection:
        result = connection.execute(text("SELECT profile_memory_policy FROM form_fields LIMIT 1"))
        row = result.fetchone()
        assert row is None or row[0] == "auto"


def test_init_db_adds_all_missing_columns_to_existing_form_fields_table(tmp_path):
    """Verify that all missing columns are added to legacy tables."""

    from app.database import _add_missing_form_field_columns

    db_path = tmp_path / "minimal.db"
    engine = create_engine(f"sqlite:///{db_path}")

    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE form_fields (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                selector VARCHAR(1000) NOT NULL
            )
        """))

    _add_missing_form_field_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("form_fields")}
    assert "element_ref" in columns
    assert "form_title" in columns
    assert "section_title" in columns
    assert "name" in columns
    assert "html_id" in columns
    assert "current_value" in columns
    assert "options" in columns
    assert "profile_memory_policy" in columns


def test_init_db_adds_workflow_columns_to_existing_tasks_table(tmp_path):
    """Verify that legacy tasks tables receive workflow_type and workflow_status."""

    from app.database import _add_missing_task_workflow_columns

    db_path = tmp_path / "legacy_tasks.db"
    engine = create_engine(f"sqlite:///{db_path}")

    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY,
                url VARCHAR(2048) NOT NULL,
                profile_id INTEGER NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'CREATED'
            )
        """))

    _add_missing_task_workflow_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("tasks")}
    assert "workflow_type" in columns
    assert "workflow_status" in columns


def test_init_db_adds_missing_workflow_span_columns(tmp_path):
    """Verify legacy workflow_spans tables receive newly added columns."""

    from app.database import _add_missing_workflow_span_columns

    db_path = tmp_path / "legacy_workflow_spans.db"
    engine = create_engine(f"sqlite:///{db_path}")

    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE workflow_spans (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL
            )
        """))

    _add_missing_workflow_span_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("workflow_spans")}
    assert "phase" in columns
    assert "name" in columns
    assert "status" in columns
    assert "input_json" in columns
    assert "output_json" in columns
    assert "metadata_json" in columns


def test_init_db_adds_missing_approval_request_columns(tmp_path):
    """Verify legacy approval_requests tables receive newly added columns."""

    from app.database import _add_missing_approval_request_columns

    db_path = tmp_path / "legacy_approval_requests.db"
    engine = create_engine(f"sqlite:///{db_path}")

    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE approval_requests (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL
            )
        """))

    _add_missing_approval_request_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("approval_requests")}
    assert "step_name" in columns
    assert "risk_type" in columns
    assert "risk_level" in columns
    assert "decision" in columns
    assert "proposed_action_json" in columns
    assert "status" in columns


def test_task_checkpoint_model_creates_profile_task_and_checkpoint(tmp_path):
    """Verify TaskCheckpoint model creates and loads checkpoints with relationship."""

    from app.database import Base
    from app.models import Profile, Task, TaskCheckpoint, utc_now
    from app.workflow_constants import WORKFLOW_STAGE_ANALYSIS, CHECKPOINT_SUCCESS

    db_path = tmp_path / "checkpoint_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    checkpoint = TaskCheckpoint(
        task_id=task.id,
        stage=WORKFLOW_STAGE_ANALYSIS,
        status=CHECKPOINT_SUCCESS,
        input_hash="abc123",
        output_json=json.dumps({"fields": ["email", "name"]}),
    )
    session.add(checkpoint)
    session.commit()

    session.refresh(task)

    assert len(task.checkpoints) == 1
    assert task.checkpoints[0].stage == WORKFLOW_STAGE_ANALYSIS
    assert task.checkpoints[0].status == CHECKPOINT_SUCCESS
    assert task.checkpoints[0].input_hash == "abc123"

    session.close()


def test_task_checkpoint_output_json_safe_parse(tmp_path):
    """Verify invalid JSON in output_json is handled safely."""

    from app.database import Base
    from app.models import Profile, Task, TaskCheckpoint
    from app.workflow_constants import WORKFLOW_STAGE_MAPPING, CHECKPOINT_SUCCESS

    db_path = tmp_path / "checkpoint_json_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    checkpoint = TaskCheckpoint(
        task_id=task.id,
        stage=WORKFLOW_STAGE_MAPPING,
        status=CHECKPOINT_SUCCESS,
        output_json="{invalid json}",
    )
    session.add(checkpoint)
    session.commit()

    session.refresh(checkpoint)

    assert checkpoint.output is not None
    assert isinstance(checkpoint.output, dict)
    assert checkpoint.output == {}

    session.close()


def test_job_and_job_attempt_models_create_and_persist(tmp_path):
    """Verify Job and JobAttempt models create and load with relationship."""

    from app.database import Base
    from app.models import Profile, Task, Job, JobAttempt
    from app.job_constants import JOB_TYPE_ANALYZE_FORM, JOB_STATUS_PENDING, JOB_STATUS_RUNNING, JOB_STATUS_SUCCEEDED

    db_path = tmp_path / "job_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    job = Job(
        task_id=task.id,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_PENDING,
        priority=1,
        payload_json=json.dumps({"url": "https://example.com/form"}),
        attempts=0,
        max_attempts=3,
    )
    session.add(job)
    session.commit()

    attempt = JobAttempt(
        job_id=job.id,
        attempt_no=1,
        status=JOB_STATUS_RUNNING,
    )
    session.add(attempt)
    session.commit()

    attempt.status = JOB_STATUS_SUCCEEDED
    session.commit()

    session.refresh(job)

    assert job.task_id == task.id
    assert job.job_type == JOB_TYPE_ANALYZE_FORM
    assert job.status == JOB_STATUS_PENDING
    assert job.priority == 1
    assert job.attempts == 0
    assert job.max_attempts == 3
    assert job.locked_by is None
    assert job.locked_at is None
    assert job.next_run_at is None

    session.refresh(attempt)
    assert attempt.job_id == job.id
    assert attempt.attempt_no == 1
    assert attempt.status == JOB_STATUS_SUCCEEDED
    assert attempt.started_at is not None
    assert attempt.finished_at is None

    session.close()


def test_worker_heartbeat_model_creates_and_updates(tmp_path):
    """Verify WorkerHeartbeat model creates and updates correctly."""

    from app.database import Base
    from app.models import WorkerHeartbeat

    db_path = tmp_path / "heartbeat_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    heartbeat = WorkerHeartbeat(
        worker_id="worker-123",
        hostname="worker-host-01",
        current_job_id=None,
        status="running",
    )
    session.add(heartbeat)
    session.commit()

    session.refresh(heartbeat)
    assert heartbeat.worker_id == "worker-123"
    assert heartbeat.hostname == "worker-host-01"
    assert heartbeat.current_job_id is None
    assert heartbeat.status == "running"
    assert heartbeat.last_seen_at is not None

    heartbeat.current_job_id = 12345
    heartbeat.status = "busy"
    session.commit()

    session.refresh(heartbeat)
    assert heartbeat.current_job_id == 12345
    assert heartbeat.status == "busy"

    session.close()


def test_job_payload_json_safe_parse(tmp_path):
    """Verify invalid JSON in payload_json is handled safely."""

    from app.database import Base
    from app.models import Profile, Task, Job
    from app.job_constants import JOB_TYPE_ANALYZE_FORM, JOB_STATUS_PENDING

    db_path = tmp_path / "job_payload_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    job = Job(
        task_id=task.id,
        job_type=JOB_TYPE_ANALYZE_FORM,
        status=JOB_STATUS_PENDING,
        priority=1,
        payload_json="{invalid json}",
    )
    session.add(job)
    session.commit()

    session.refresh(job)

    assert job.payload is not None
    assert isinstance(job.payload, dict)
    assert job.payload == {}

    job.payload = {"url": "https://example.com/form", "profile_id": profile.id}
    session.commit()

    session.refresh(job)
    assert job.payload["url"] == "https://example.com/form"
    assert job.payload["profile_id"] == profile.id

    session.close()


def test_llm_api_usage_log_new_fields_with_defaults(tmp_path):
    """Verify LlmApiUsageLog model creates with new observability fields and safe defaults."""

    from app.database import Base
    from app.models import Profile, Task, LlmApiUsageLog

    db_path = tmp_path / "llm_usage_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    usage_log = LlmApiUsageLog(
        task_id=task.id,
        provider="deepseek",
        model="deepseek-v4-flash",
        prompt_tokens=100,
        completion_tokens=25,
        total_tokens=125,
        cache_hit_tokens=50,
        cache_miss_tokens=50,
        cache_hit=True,
        cache_hit_rate=0.5,
        latency_ms=234,
        error_type=None,
        fallback_used=False,
        cache_source="provider_prompt_cache",
        estimated_cost=0.00125,
    )
    session.add(usage_log)
    session.commit()

    session.refresh(usage_log)

    assert usage_log.latency_ms == 234
    assert usage_log.error_type is None
    assert usage_log.fallback_used is False
    assert usage_log.cache_source == "provider_prompt_cache"
    assert usage_log.estimated_cost == 0.00125

    session.close()


def test_llm_api_usage_log_fallback_and_error_records(tmp_path):
    """Verify LlmApiUsageLog records fallback_used and error_type correctly."""

    from app.database import Base
    from app.models import Profile, Task, LlmApiUsageLog

    db_path = tmp_path / "llm_usage_fallback_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    usage_log = LlmApiUsageLog(
        task_id=task.id,
        provider="openai",
        model="gpt-4o-mini",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        cache_hit_tokens=0,
        cache_miss_tokens=0,
        cache_hit=False,
        cache_hit_rate=0.0,
        latency_ms=5000,
        error_type="TimeoutError",
        fallback_used=True,
        cache_source="no_cache",
        estimated_cost=0.0,
    )
    session.add(usage_log)
    session.commit()

    session.refresh(usage_log)

    assert usage_log.error_type == "TimeoutError"
    assert usage_log.fallback_used is True
    assert usage_log.latency_ms == 5000
    assert usage_log.cache_source == "no_cache"

    session.close()


def test_llm_api_usage_log_default_values_for_existing_rows(tmp_path):
    """Verify LlmApiUsageLog new fields have safe defaults for existing rows."""

    from app.database import Base
    from app.models import Profile, Task, LlmApiUsageLog

    db_path = tmp_path / "llm_usage_defaults_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    usage_log = LlmApiUsageLog(
        task_id=task.id,
        provider="deepseek",
        model="deepseek-v4-flash",
        prompt_tokens=100,
        completion_tokens=25,
        total_tokens=125,
        cache_hit_tokens=0,
        cache_miss_tokens=100,
        cache_hit=False,
        cache_hit_rate=0.0,
    )
    session.add(usage_log)
    session.commit()

    session.refresh(usage_log)

    assert usage_log.latency_ms == 0
    assert usage_log.error_type is None
    assert usage_log.fallback_used is False
    assert usage_log.cache_source == "no_cache"
    assert usage_log.estimated_cost == 0.0

    session.close()


def test_benchmark_run_with_baseline_and_duration(tmp_path):
    """Verify BenchmarkRun model creates with baseline_run_id, duration_ms, and comparison fields."""

    import json
    from app.database import Base
    from app.models import BenchmarkRun, BenchmarkCaseResult

    db_path = tmp_path / "benchmark_run_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    baseline_run = BenchmarkRun(
        mode="rules",
        provider=None,
        total_cases=5,
        average_score=0.95,
        summary_metrics_json=json.dumps({
            "field_extraction_recall": 0.9,
            "mapping_accuracy": 0.95,
            "required_field_coverage": 1.0,
        }),
        duration_ms=1234,
    )
    session.add(baseline_run)
    session.commit()

    current_run = BenchmarkRun(
        mode="rules",
        provider=None,
        total_cases=5,
        average_score=0.92,
        summary_metrics_json=json.dumps({
            "field_extraction_recall": 0.85,
            "mapping_accuracy": 0.92,
            "required_field_coverage": 1.0,
        }),
        baseline_run_id=baseline_run.id,
        duration_ms=1567,
        regression_count=2,
        improvement_count=0,
        mode_detail="stress_test",
    )
    session.add(current_run)
    session.commit()

    session.refresh(baseline_run)
    assert baseline_run.id is not None
    assert baseline_run.baseline_run_id is None
    assert baseline_run.duration_ms == 1234
    assert baseline_run.regression_count == 0
    assert baseline_run.improvement_count == 0
    assert baseline_run.mode_detail is None

    session.refresh(current_run)
    assert current_run.baseline_run_id == baseline_run.id
    assert current_run.duration_ms == 1567
    assert current_run.regression_count == 2
    assert current_run.improvement_count == 0
    assert current_run.mode_detail == "stress_test"

    session.close()


def test_benchmark_run_default_values(tmp_path):
    """Verify BenchmarkRun new fields have safe defaults for existing rows."""

    import json
    from app.database import Base
    from app.models import BenchmarkRun

    db_path = tmp_path / "benchmark_run_defaults_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    run = BenchmarkRun(
        mode="llm",
        provider="openai",
        total_cases=3,
        average_score=0.88,
        summary_metrics_json=json.dumps({
            "field_extraction_recall": 0.85,
            "mapping_accuracy": 0.90,
        }),
    )
    session.add(run)
    session.commit()

    session.refresh(run)

    assert run.baseline_run_id is None
    assert run.duration_ms == 0
    assert run.regression_count == 0
    assert run.improvement_count == 0
    assert run.mode_detail is None

    session.close()


def test_add_missing_benchmark_run_columns(tmp_path):
    """Verify _add_missing_benchmark_run_columns adds new columns to legacy benchmark_runs table."""

    from app.database import _add_missing_benchmark_run_columns

    db_path = tmp_path / "legacy_benchmark.db"
    engine = create_engine(f"sqlite:///{db_path}")

    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE benchmark_runs (
                id INTEGER PRIMARY KEY,
                mode VARCHAR(50) NOT NULL,
                provider VARCHAR(50),
                total_cases INTEGER NOT NULL,
                average_score FLOAT NOT NULL,
                summary_metrics TEXT NOT NULL,
                created_at DATETIME NOT NULL
            )
        """))

    _add_missing_benchmark_run_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("benchmark_runs")}
    assert "baseline_run_id" in columns
    assert "duration_ms" in columns
    assert "regression_count" in columns
    assert "improvement_count" in columns
    assert "mode_detail" in columns


def test_field_verification_result_model_creates_and_persists(tmp_path):
    """Verify FieldVerificationResult model creates and loads correctly."""

    from app.database import Base
    from app.models import Profile, Task, FieldVerificationResult, utc_now
    from app.models import (
        VERIFICATION_STATUS_VERIFIED,
        VERIFICATION_STATUS_FAILED,
        VERIFICATION_STATUS_SKIPPED,
        VERIFICATION_REASON_VALUE_MISMATCH,
        VERIFICATION_REASON_SENSITIVE_FIELD_SKIPPED,
    )

    db_path = tmp_path / "verification_result_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    verification = FieldVerificationResult(
        task_id=task.id,
        field_id=1,
        selector="input[name='email']",
        expected_value_hash="abc123",
        actual_value_hash="abc123",
        status=VERIFICATION_STATUS_VERIFIED,
        reason=None,
        message=None,
    )
    session.add(verification)
    session.commit()

    session.refresh(task)
    assert len(task.verification_results) == 1
    assert task.verification_results[0].status == VERIFICATION_STATUS_VERIFIED

    session.refresh(verification)
    assert verification.task_id == task.id
    assert verification.field_id == 1
    assert verification.selector == "input[name='email']"
    assert verification.expected_value_hash == "abc123"
    assert verification.actual_value_hash == "abc123"
    assert verification.status == VERIFICATION_STATUS_VERIFIED
    assert verification.reason is None
    assert verification.message is None
    assert verification.created_at is not None

    skipped_verification = FieldVerificationResult(
        task_id=task.id,
        field_id=2,
        selector="input[name='password']",
        expected_value_hash=None,
        actual_value_hash=None,
        status=VERIFICATION_STATUS_SKIPPED,
        reason=VERIFICATION_REASON_SENSITIVE_FIELD_SKIPPED,
        message="Password field skipped for security",
    )
    session.add(skipped_verification)
    session.commit()

    session.refresh(task)
    assert len(task.verification_results) == 2

    session.refresh(skipped_verification)
    assert skipped_verification.status == VERIFICATION_STATUS_SKIPPED
    assert skipped_verification.reason == VERIFICATION_REASON_SENSITIVE_FIELD_SKIPPED
    assert skipped_verification.message == "Password field skipped for security"
    assert skipped_verification.expected_value_hash is None
    assert skipped_verification.actual_value_hash is None

    session.close()


def test_agent_review_model_creates_and_persists(tmp_path):
    """Verify AgentReview model creates and loads correctly with relationship."""

    import json
    from app.database import Base
    from app.models import Profile, Task, AgentReview
    from app.agent_constants import (
        AGENT_ROLE_MAPPING_CRITIC,
        AGENT_ROLE_SAFETY_REVIEW,
        AGENT_DECISION_PASS,
        AGENT_DECISION_REVIEW_REQUIRED,
        AGENT_DECISION_BLOCK,
    )

    db_path = tmp_path / "agent_review_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    mapping_review = AgentReview(
        task_id=task.id,
        role=AGENT_ROLE_MAPPING_CRITIC,
        decision=AGENT_DECISION_PASS,
        input_hash="abc123def456",
        output_json=json.dumps({"issues": [], "confidence": 0.95}),
        model="gpt-4o-mini",
        provider="openai",
    )
    session.add(mapping_review)
    session.commit()

    safety_review = AgentReview(
        task_id=task.id,
        role=AGENT_ROLE_SAFETY_REVIEW,
        decision=AGENT_DECISION_REVIEW_REQUIRED,
        input_hash="ghi789jkl012",
        output_json=json.dumps({"issues": ["Potential sensitive field detected"], "confidence": 0.85}),
        model="deepseek-v4-flash",
        provider="deepseek",
    )
    session.add(safety_review)
    session.commit()

    session.refresh(task)
    assert len(task.agent_reviews) == 2

    session.refresh(mapping_review)
    assert mapping_review.task_id == task.id
    assert mapping_review.role == AGENT_ROLE_MAPPING_CRITIC
    assert mapping_review.decision == AGENT_DECISION_PASS
    assert mapping_review.input_hash == "abc123def456"
    assert mapping_review.model == "gpt-4o-mini"
    assert mapping_review.provider == "openai"
    assert mapping_review.created_at is not None

    assert mapping_review.output is not None
    assert isinstance(mapping_review.output, dict)
    assert mapping_review.output["issues"] == []
    assert mapping_review.output["confidence"] == 0.95

    session.refresh(safety_review)
    assert safety_review.role == AGENT_ROLE_SAFETY_REVIEW
    assert safety_review.decision == AGENT_DECISION_REVIEW_REQUIRED
    assert safety_review.output["issues"] == ["Potential sensitive field detected"]

    session.close()


def test_agent_review_output_json_safe_parse(tmp_path):
    """Verify invalid JSON in output_json is handled safely."""

    from app.database import Base
    from app.models import Profile, Task, AgentReview
    from app.agent_constants import (
        AGENT_ROLE_MAPPING_CRITIC,
        AGENT_DECISION_BLOCK,
    )

    db_path = tmp_path / "agent_review_json_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    review = AgentReview(
        task_id=task.id,
        role=AGENT_ROLE_MAPPING_CRITIC,
        decision=AGENT_DECISION_BLOCK,
        input_hash="invalid123",
        output_json="{invalid json}",
    )
    session.add(review)
    session.commit()

    session.refresh(review)

    assert review.output is not None
    assert isinstance(review.output, dict)
    assert review.output == {}

    session.close()
