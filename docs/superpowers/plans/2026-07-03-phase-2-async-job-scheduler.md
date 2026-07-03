# Phase 2 Async Job Scheduler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move long-running LLM and Playwright workflows out of synchronous API requests and into a recoverable, resource-aware job scheduler.

**Architecture:** Add database-backed job records and a Python worker loop. API routes enqueue jobs and return quickly. Workers lock jobs, execute workflow stages, write checkpoints, update task status, and record attempts. This phase uses SQLite-compatible locking patterns and keeps Redis/Celery out of scope.

**Tech Stack:** Python, FastAPI, SQLAlchemy, SQLite, pytest, React, Vite, Node test runner.

## Global Constraints

- Do not introduce Redis, Celery, or external queue infrastructure in this phase.
- Do not run final submission as an automatic background job.
- Do not allow more browser jobs than the configured local limit.
- Every job execution must write either success or failure evidence.
- All UI text and code comments must be English.

---

## File Structure

- Create: `backend/app/job_constants.py`
- Modify: `backend/app/models.py` to add `Job`, `JobAttempt`, and `WorkerHeartbeat`.
- Create: `backend/app/services/job_queue.py`
- Create: `backend/app/services/job_worker.py`
- Modify: `backend/app/routers/tasks.py` to enqueue jobs for analyze, map, and fill.
- Create: `backend/app/routers/jobs.py`
- Modify: `backend/app/main.py` to include jobs router.
- Modify: `frontend/src/api.js` and Task Detail helpers to show queued/running job state.

---

### Task 1: Define Job Constants

**Files:**
- Create: `backend/app/job_constants.py`
- Create: `backend/tests/test_job_constants.py`

**Interfaces:**

```python
JOB_TYPE_ANALYZE_FORM = "ANALYZE_FORM"
JOB_TYPE_MAP_FIELDS = "MAP_FIELDS"
JOB_TYPE_FILL_FORM = "FILL_FORM"
JOB_TYPE_RUN_BENCHMARK = "RUN_BENCHMARK"

JOB_STATUS_PENDING = "PENDING"
JOB_STATUS_RUNNING = "RUNNING"
JOB_STATUS_SUCCEEDED = "SUCCEEDED"
JOB_STATUS_FAILED = "FAILED"
JOB_STATUS_CANCELLED = "CANCELLED"
JOB_STATUS_RETRY_SCHEDULED = "RETRY_SCHEDULED"
```

**Steps:**
- [ ] Write tests importing constants and verifying uniqueness.
- [ ] Run: `cd backend; pytest tests/test_job_constants.py -v`
- [ ] Implement constants with English docstring.
- [ ] Re-run test.

**Acceptance Criteria:**
- Routes and services do not invent job status strings.

---

### Task 2: Add Job, JobAttempt, And WorkerHeartbeat Models

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/tests/test_database_migrations.py`

**Model Contracts:**

```python
class Job(Base):
    id: int
    task_id: int | None
    job_type: str
    status: str
    priority: int
    payload_json: str | None
    attempts: int
    max_attempts: int
    locked_by: str | None
    locked_at: datetime | None
    next_run_at: datetime | None
    error_reason: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

class JobAttempt(Base):
    id: int
    job_id: int
    attempt_no: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    error_reason: str | None
    error_message: str | None

class WorkerHeartbeat(Base):
    id: int
    worker_id: str
    hostname: str | None
    current_job_id: int | None
    status: str
    last_seen_at: datetime
```

**Steps:**
- [ ] Write database test creating a job with one attempt.
- [ ] Write database test creating/updating worker heartbeat.
- [ ] Run: `cd backend; pytest tests/test_database_migrations.py -v`
- [ ] Add models and relationships.
- [ ] Add response schemas: `JobResponse`, `JobAttemptResponse`, `WorkerHeartbeatResponse`.
- [ ] Re-run database tests.

**Acceptance Criteria:**
- Jobs, attempts, and worker heartbeats persist.
- Existing task tests still pass.

---

### Task 3: Create Job Queue Service

**Files:**
- Create: `backend/app/services/job_queue.py`
- Create: `backend/tests/test_job_queue.py`

**Interfaces:**

```python
def enqueue_job(db: Session, job_type: str, task_id: int | None, payload: dict | None = None, priority: int = 100, max_attempts: int = 3) -> Job:
    """Create a pending job."""

def claim_next_job(db: Session, worker_id: str, allowed_job_types: set[str] | None = None) -> Job | None:
    """Lock and return the next runnable job."""

def mark_job_succeeded(db: Session, job: Job) -> None:
    """Mark a job as succeeded."""

def mark_job_failed(db: Session, job: Job, error_reason: str, error_message: str, retry: bool) -> None:
    """Mark a job as failed or schedule a retry."""

def record_worker_heartbeat(db: Session, worker_id: str, current_job_id: int | None, status: str) -> WorkerHeartbeat:
    """Upsert worker heartbeat."""
```

**Steps:**
- [ ] Test `enqueue_job()` creates `PENDING` job.
- [ ] Test `claim_next_job()` locks the oldest pending job and increments attempts.
- [ ] Test locked jobs are not claimed by another worker.
- [ ] Test `mark_job_failed(..., retry=True)` schedules retry until `max_attempts`.
- [ ] Test final failure after max attempts.
- [ ] Run: `cd backend; pytest tests/test_job_queue.py -v`
- [ ] Implement service.
- [ ] Re-run tests.

**Acceptance Criteria:**
- Job locking is deterministic enough for local SQLite.
- Retry behavior is explicit and test-covered.

---

### Task 4: Create Worker Execution Service

**Files:**
- Create: `backend/app/services/job_worker.py`
- Create: `backend/tests/test_job_worker.py`

**Interfaces:**

```python
def execute_job(db: Session, job: Job) -> None:
    """Execute one claimed job and update job/task/checkpoint state."""

def run_worker_once(db: Session, worker_id: str, allowed_job_types: set[str] | None = None) -> bool:
    """Claim and execute one job. Return True when a job was processed."""
```

**Behavior:**
- [ ] `ANALYZE_FORM` calls checkpoint-aware analyze stage service.
- [ ] `MAP_FIELDS` calls checkpoint-aware mapping stage service.
- [ ] `FILL_FORM` calls checkpoint-aware fill stage service.
- [ ] Worker writes job attempts.
- [ ] Worker records heartbeat before and after execution.
- [ ] Worker marks retryable failures as retry scheduled.

**Tests:**
- [ ] Unknown job type fails with structured error.
- [ ] Analyze job calls analyze stage.
- [ ] Mapping job calls mapping stage.
- [ ] Fill job calls fill stage.
- [ ] Retryable exception schedules retry.
- [ ] Non-retryable exception fails permanently.
- [ ] Run: `cd backend; pytest tests/test_job_worker.py -v`

**Acceptance Criteria:**
- One job can be processed from queue to terminal status.
- Worker does not submit forms automatically.

---

### Task 5: Add Job API Endpoints

**Files:**
- Create: `backend/app/routers/jobs.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_jobs_endpoint.py`

**Endpoints:**

```text
GET /jobs
GET /jobs/{job_id}
GET /tasks/{task_id}/jobs
POST /jobs/{job_id}/cancel
GET /workers/heartbeats
```

**Steps:**
- [ ] Write endpoint tests for listing jobs newest first.
- [ ] Write endpoint test for task-specific jobs.
- [ ] Write endpoint test for job detail with attempts.
- [ ] Write cancel test: pending jobs become `CANCELLED`; running/succeeded jobs reject cancellation.
- [ ] Run: `cd backend; pytest tests/test_jobs_endpoint.py -v`
- [ ] Implement router and include it in `main.py`.
- [ ] Re-run tests.

**Acceptance Criteria:**
- UI can display job progress.
- Running jobs cannot be incorrectly cancelled.

---

### Task 6: Enqueue Analyze, Map, And Fill From Task Routes

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/tests/test_task_mapping_endpoint.py`
- Create: `backend/tests/test_task_job_enqueue.py`

**Behavior:**
- [ ] `POST /tasks/{id}/analyze` enqueues `ANALYZE_FORM` and returns job information or updated task response with queued status.
- [ ] `POST /tasks/{id}/map-fields` enqueues `MAP_FIELDS`.
- [ ] `POST /tasks/{id}/fill` enqueues `FILL_FORM`.
- [ ] Existing synchronous behavior can be kept behind a local feature flag if needed: `ASYNC_JOBS_ENABLED`.

**Tests:**
- [ ] Analyze endpoint creates job.
- [ ] Map endpoint creates job with mode/provider payload.
- [ ] Fill endpoint creates job only when task is ready.
- [ ] Approval/submit endpoint remains synchronous and manual.
- [ ] Run: `cd backend; pytest tests/test_task_job_enqueue.py tests/test_task_mapping_endpoint.py -v`

**Acceptance Criteria:**
- Long-running work can be queued.
- Final approval is not queued or automated.

---

### Task 7: Add Frontend Job Status Display

**Files:**
- Modify: `frontend/src/api.js`
- Create: `frontend/src/jobPresentation.js`
- Create: `frontend/src/jobPresentation.test.js`
- Modify: `frontend/src/pages/TaskDetail.jsx`

**Behavior:**
- [ ] Load task jobs on Task Detail.
- [ ] Show newest job status: `Queued`, `Running`, `Retry scheduled`, `Succeeded`, `Failed`.
- [ ] Show attempt count and latest error message when failed.
- [ ] Do not expose raw stack traces.

**Tests:**
- [ ] `jobStatusLabel("PENDING")` returns `Queued`.
- [ ] Retry scheduled status has a clear label.
- [ ] Failed job summary includes attempt count.
- [ ] Run: `cd frontend; npm test -- jobPresentation.test.js`

**Acceptance Criteria:**
- User can see background workflow progress.
- User still reviews mapping and final submission manually.

---

### Task 8: End-To-End Verification

**Commands:**
- [ ] Run: `cd backend; pytest -v`
- [ ] Run: `cd frontend; npm run lint`
- [ ] Run: `cd frontend; npm test`
- [ ] Run: `cd frontend; npm run build`

**Manual Verification:**
- [ ] Create a task.
- [ ] Enqueue analyze job.
- [ ] Run worker once and confirm task advances.
- [ ] Enqueue mapping job.
- [ ] Run worker once and confirm mappings appear.
- [ ] Enqueue fill job.
- [ ] Run worker once and confirm task waits for approval.

**Done Criteria:**
- API is not blocked by long-running Playwright/LLM work.
- Jobs have attempts, retries, and terminal states.
- No final submission is performed by worker.

