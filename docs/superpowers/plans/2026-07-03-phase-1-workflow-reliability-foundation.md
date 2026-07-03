# Phase 1 Workflow Reliability Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing form automation workflow recoverable, diagnosable, and safe to retry across analysis, mapping, review, fill, and approval stages.

**Architecture:** Keep the existing `Task.status` flow and add a checkpoint/evidence layer beside it. Each expensive or failure-prone stage writes structured success/failure evidence. Retried operations must check for reusable successful checkpoints before doing browser or LLM work again.

**Tech Stack:** Python, FastAPI, SQLAlchemy, SQLite, pytest, React, Vite, Node test runner, Playwright.

## Global Constraints

- All user-facing page text must be English.
- All new code comments and docstrings must be English.
- Do not auto-submit forms.
- Do not remove existing task APIs.
- Do not bypass user review or approval.
- Do not store passwords, OTPs, payment values, or one-time consent values as reusable profile memory.
- Every backend behavior change must have pytest coverage.
- Every frontend presentation helper change must have Node test coverage.

---

## File Structure

- Create: `backend/app/workflow_constants.py` for stage, checkpoint status, and failure reason constants.
- Modify: `backend/app/models.py` to add `TaskCheckpoint`.
- Modify: `backend/app/schemas.py` to expose checkpoint data when needed.
- Create: `backend/app/services/checkpoint_service.py` for deterministic checkpoint read/write behavior.
- Modify: `backend/app/routers/tasks.py` to write checkpoints from analyze, map, and fill stages.
- Modify: `frontend/src/debugReport.js` to include checkpoint and failure evidence.
- Modify: `frontend/src/taskRunState.js` to show recovery-aware labels.
- Add tests under `backend/tests/` and `frontend/src/*.test.js`.

---

### Task 1: Define Workflow Constants

**Files:**
- Create: `backend/app/workflow_constants.py`
- Create: `backend/tests/test_workflow_constants.py`

**Interfaces:**

```python
WORKFLOW_STAGE_ANALYSIS = "ANALYSIS"
WORKFLOW_STAGE_MAPPING = "MAPPING"
WORKFLOW_STAGE_REVIEW = "REVIEW"
WORKFLOW_STAGE_FILL = "FILL"
WORKFLOW_STAGE_APPROVAL = "APPROVAL"
WORKFLOW_STAGE_SUBMISSION = "SUBMISSION"

CHECKPOINT_SUCCESS = "SUCCESS"
CHECKPOINT_FAILED = "FAILED"
CHECKPOINT_SKIPPED = "SKIPPED"

FAILURE_ANALYSIS_FAILED = "ANALYSIS_FAILED"
FAILURE_LLM_MAPPING_FAILED = "LLM_MAPPING_FAILED"
FAILURE_REQUIRED_FIELD_MISSING = "REQUIRED_FIELD_MISSING"
FAILURE_BROWSER_FILL_FAILED = "BROWSER_FILL_FAILED"
FAILURE_SELECTOR_NOT_FOUND = "SELECTOR_NOT_FOUND"
FAILURE_VALUE_VERIFICATION_FAILED = "VALUE_VERIFICATION_FAILED"
FAILURE_LOGIN_REQUIRED = "LOGIN_REQUIRED"
FAILURE_SUBMISSION_REQUIRES_APPROVAL = "SUBMISSION_REQUIRES_APPROVAL"
```

**Steps:**
- [ ] Write a failing test that imports all constants above.
- [ ] Assert every stage, checkpoint status, and failure reason is uppercase.
- [ ] Assert constants are unique within their category.
- [ ] Run: `cd backend; pytest tests/test_workflow_constants.py -v`
- [ ] Implement `backend/app/workflow_constants.py` with an English module docstring.
- [ ] Re-run the test and confirm it passes.

**Acceptance Criteria:**
- No new workflow stage or failure reason is hard-coded in routes.
- Constants are stable strings that can be used in database rows and API responses.

---

### Task 2: Add TaskCheckpoint Model

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/tests/test_database_migrations.py`

**Model Contract:**

```python
class TaskCheckpoint(Base):
    """A recoverable stage result for one task workflow."""

    __tablename__ = "task_checkpoints"

    id: Mapped[int]
    task_id: Mapped[int]
    stage: Mapped[str]
    status: Mapped[str]
    input_hash: Mapped[str | None]
    output_json: Mapped[str | None]
    failure_reason: Mapped[str | None]
    error_message: Mapped[str | None]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

**Rules:**
- [ ] `stage` must use values from `workflow_constants.py`.
- [ ] `status` must be `SUCCESS`, `FAILED`, or `SKIPPED`.
- [ ] `output_json` must be JSON text or `None`.
- [ ] Do not store secret values in `output_json`.
- [ ] Add `Task.checkpoints` relationship.

**Steps:**
- [ ] Write a failing database test that creates a profile, task, and `TaskCheckpoint`.
- [ ] Assert `task.checkpoints` loads the checkpoint.
- [ ] Assert invalid JSON in `output_json` is handled safely by any property helper if one is added.
- [ ] Run: `cd backend; pytest tests/test_database_migrations.py -v`
- [ ] Add SQLAlchemy model and optional response schema `TaskCheckpointResponse`.
- [ ] Re-run database tests.

**Acceptance Criteria:**
- Checkpoints persist successfully.
- Existing profile, task, form field, benchmark, and trace models still work.

---

### Task 3: Create Checkpoint Service

**Files:**
- Create: `backend/app/services/checkpoint_service.py`
- Create: `backend/tests/test_checkpoint_service.py`

**Interfaces:**

```python
def build_input_hash(payload: object) -> str:
    """Return a deterministic hash for checkpoint inputs."""

def get_latest_checkpoint(db: Session, task_id: int, stage: str) -> TaskCheckpoint | None:
    """Return the newest checkpoint for a task stage."""

def has_success_checkpoint(db: Session, task_id: int, stage: str) -> bool:
    """Return whether a stage has a successful checkpoint."""

def write_success_checkpoint(
    db: Session,
    task_id: int,
    stage: str,
    input_payload: object | None,
    output_payload: object | None,
) -> TaskCheckpoint:
    """Persist a successful checkpoint for a completed stage."""

def write_failed_checkpoint(
    db: Session,
    task_id: int,
    stage: str,
    failure_reason: str,
    error_message: str,
    input_payload: object | None = None,
) -> TaskCheckpoint:
    """Persist a failed checkpoint for a failed stage."""
```

**Steps:**
- [ ] Write tests proving `build_input_hash({"b": 2, "a": 1}) == build_input_hash({"a": 1, "b": 2})`.
- [ ] Write tests proving `write_success_checkpoint()` stores `SUCCESS`, input hash, and serialized output.
- [ ] Write tests proving `write_failed_checkpoint()` stores `FAILED`, failure reason, and error message.
- [ ] Write tests proving `get_latest_checkpoint()` returns the newest checkpoint when multiple rows exist.
- [ ] Run: `cd backend; pytest tests/test_checkpoint_service.py -v`
- [ ] Implement the service.
- [ ] Re-run tests.

**Acceptance Criteria:**
- Checkpoint logic is not duplicated in API routes.
- Failed checkpoints are available for debug reports and recovery decisions.

---

### Task 4: Make Analyze Stage Checkpoint-Aware

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Create or Modify: `backend/tests/test_task_checkpoint_flow.py`

**Behavior:**
- [ ] `POST /tasks/{task_id}/analyze` checks for `ANALYSIS` success checkpoint first.
- [ ] If a success checkpoint exists, return the current persisted task and fields without calling Playwright extraction.
- [ ] If no success checkpoint exists, run the existing extraction path.
- [ ] On successful extraction, write `ANALYSIS` success checkpoint.
- [ ] If login is required, write a failed or skipped checkpoint with `LOGIN_REQUIRED` and keep current login flow.
- [ ] On extraction exception, write `ANALYSIS` failed checkpoint with `ANALYSIS_FAILED`.

**Tests:**
- [ ] Existing analysis checkpoint prevents repeated extraction.
- [ ] Successful analysis writes a success checkpoint.
- [ ] Failed extraction writes a failed checkpoint and sets task status to `FAILED`.
- [ ] Login-required analysis records structured evidence and preserves the login-required status.
- [ ] Run: `cd backend; pytest tests/test_task_checkpoint_flow.py -v`

**Acceptance Criteria:**
- Analyze is safe to retry.
- Completed analysis is reused.
- Failed analysis leaves structured recovery evidence.

---

### Task 5: Make Mapping Stage Checkpoint-Aware

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/tests/test_task_mapping_endpoint.py`
- Create or Modify: `backend/tests/test_task_checkpoint_flow.py`

**Behavior:**
- [ ] `POST /tasks/{task_id}/map-fields` checks for `MAPPING` success checkpoint first.
- [ ] If a success checkpoint exists, return persisted `FormField` mappings without invoking LLM or rule mapping.
- [ ] If no success checkpoint exists, run the requested mapping mode.
- [ ] On success, write `MAPPING` success checkpoint containing field ids, mapped profile keys, confidence values, and mapping mode.
- [ ] On LLM failure, write `MAPPING` failed checkpoint with `LLM_MAPPING_FAILED`.

**Tests:**
- [ ] Existing mapping checkpoint prevents repeated LLM call.
- [ ] Successful LLM mapping writes checkpoint.
- [ ] Rules mode also writes checkpoint.
- [ ] LLM exception writes failed checkpoint and does not mark task as ready to fill.
- [ ] Run: `cd backend; pytest tests/test_task_mapping_endpoint.py tests/test_task_checkpoint_flow.py -v`

**Acceptance Criteria:**
- Repeated mapping requests avoid unnecessary LLM calls.
- Mapping failures are structured and recoverable.

---

### Task 6: Make Fill Stage Checkpoint-Aware

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/tests/test_browser_executor.py`
- Modify: `backend/tests/test_confirm_submit.py`
- Create or Modify: `backend/tests/test_task_checkpoint_flow.py`

**Behavior:**
- [ ] `POST /tasks/{task_id}/fill` still requires `READY_TO_FILL`.
- [ ] Required-field validation still runs before filling.
- [ ] Successful browser fill writes `FILL` success checkpoint and sets task status to `WAITING_APPROVAL`.
- [ ] Browser fill failure writes `FILL` failed checkpoint with `BROWSER_FILL_FAILED` and sets task status to `FAILED`.
- [ ] Existing `FILL` checkpoint must never trigger automatic submission.

**Tests:**
- [ ] Successful fill writes `FILL` success checkpoint.
- [ ] Fill failure writes `FILL` failed checkpoint.
- [ ] Submit remains blocked until explicit approval even when `FILL` checkpoint exists.
- [ ] Run: `cd backend; pytest tests/test_browser_executor.py tests/test_confirm_submit.py tests/test_task_checkpoint_flow.py -v`

**Acceptance Criteria:**
- Fill stage has success/failure evidence.
- Final approval remains manual.

---

### Task 7: Expose Task Checkpoints For Debugging

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/tests/test_task_checkpoints_endpoint.py`
- Modify: `frontend/src/api.js`

**Endpoint:**

```text
GET /tasks/{task_id}/checkpoints
```

**Response:**

```json
[
  {
    "id": 1,
    "task_id": 55,
    "stage": "MAPPING",
    "status": "SUCCESS",
    "failure_reason": null,
    "error_message": null,
    "created_at": "..."
  }
]
```

**Steps:**
- [ ] Write endpoint test for existing task with checkpoints.
- [ ] Write endpoint test for missing task returning `404`.
- [ ] Return checkpoints ordered by newest first.
- [ ] Add `api.listTaskCheckpoints(taskId)`.
- [ ] Run: `cd backend; pytest tests/test_task_checkpoints_endpoint.py -v`

**Acceptance Criteria:**
- Frontend can load checkpoint history.
- Sensitive checkpoint output is not required in the first frontend response.

---

### Task 8: Extend Debug Report With Checkpoints

**Files:**
- Modify: `frontend/src/debugReport.js`
- Modify: `frontend/src/debugReport.test.js`
- Modify: `frontend/src/pages/TaskDetail.jsx`

**Behavior:**
- [ ] Load checkpoints on Task Detail.
- [ ] Include latest success checkpoint stage.
- [ ] Include latest failed checkpoint stage, failure reason, and error message.
- [ ] Include LLM usage summary, screenshots, and recent logs as current behavior does.
- [ ] Do not print full sensitive mapped values.

**Tests:**
- [ ] `generateDebugReport()` includes latest success checkpoint.
- [ ] `generateDebugReport()` includes latest failure reason.
- [ ] `generateDebugReport()` treats `null` and empty mapped values as missing.
- [ ] Run: `cd frontend; npm test -- debugReport.test.js`

**Acceptance Criteria:**
- Debug report explains recovery state.
- Debug report remains safe to share during review.

---

### Task 9: Add Recovery-Aware UI Labels

**Files:**
- Modify: `frontend/src/taskRunState.js`
- Modify: `frontend/src/taskRunState.test.js`
- Modify: `frontend/src/pages/TaskDetail.jsx`

**User-Facing Labels:**
- `Recoverable failure`
- `Retry preparation`
- `Retry mapping`
- `Retry fill`
- `Waiting for approval`

**Rules:**
- [ ] `ANALYSIS_FAILED` suggests retry preparation.
- [ ] `LLM_MAPPING_FAILED` suggests retry mapping.
- [ ] `BROWSER_FILL_FAILED` suggests retry fill only when mapping is complete.
- [ ] `SUBMISSION_REQUIRES_APPROVAL` never suggests automatic submit.

**Tests:**
- [ ] Failed analysis state exposes retry preparation.
- [ ] Failed mapping state exposes retry mapping.
- [ ] Failed fill state exposes retry fill.
- [ ] Waiting approval state exposes approve action only.
- [ ] Run: `cd frontend; npm test -- taskRunState.test.js`

**Acceptance Criteria:**
- Users know whether a failure can be retried.
- UI does not expose unsafe recovery actions.

---

### Task 10: End-To-End Verification

**Commands:**
- [ ] Run: `cd backend; pytest -v`
- [ ] Run: `cd frontend; npm run lint`
- [ ] Run: `cd frontend; npm test`
- [ ] Run: `cd frontend; npm run build`

**Manual Verification:**
- [ ] Create a profile.
- [ ] Create a task.
- [ ] Analyze form and confirm `ANALYSIS` checkpoint exists.
- [ ] Map fields and confirm `MAPPING` checkpoint exists.
- [ ] Fill form and confirm `FILL` checkpoint exists.
- [ ] Force a mapping or fill failure and confirm debug report shows failure reason and last checkpoint.

**Done Criteria:**
- Existing form flow still works.
- Failed tasks produce structured evidence.
- Retried stages do not redo completed expensive work.
- No final submission happens without explicit approval.

