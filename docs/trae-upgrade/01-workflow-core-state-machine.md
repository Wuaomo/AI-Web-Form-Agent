# Phase 01 - Workflow Core State Machine

## Goal

Introduce a workflow-oriented state model while preserving the current task-based form-filling flow.

This phase should make the backend able to describe a run as a workflow, not only as a form task.

## Why This Matters

A professional AI workflow project needs explicit lifecycle management. The system should show that every run moves through controlled states, rejects invalid transitions, and records why transitions happened.

## Current Code To Read

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/routers/tasks.py`
- `backend/app/workflow_constants.py`
- `backend/app/services/checkpoint_service.py`
- `backend/tests/test_workflow_constants.py`
- `backend/tests/test_task_mapping_endpoint.py`
- `frontend/src/taskRunState.js`
- `frontend/src/taskRunState.test.js`
- `frontend/src/pages/TaskDetail.jsx`

## Scope

Add workflow identity and state-transition helpers around the existing `Task` model.

## Out Of Scope

- Do not replace `Task` with a new `WorkflowRun` table yet.
- Do not rewrite frontend navigation.
- Do not add planner, policy engine, approval gates, RAG, or evals in this phase.
- Do not remove existing task statuses.

## Data Model

Modify `Task` in `backend/app/models.py`:

```python
workflow_type: Mapped[str] = mapped_column(String(50), default="form_fill", nullable=False)
workflow_status: Mapped[str] = mapped_column(String(50), default="CREATED", nullable=False)
```

The existing `status` field remains for backward compatibility during this phase. Keep it synchronized with `workflow_status` where practical.

## Workflow Types

Create constants in `backend/app/workflow_constants.py`:

```python
WORKFLOW_TYPE_FORM_FILL = "form_fill"
WORKFLOW_TYPE_WEB_DATA_EXTRACT = "web_data_extract"
WORKFLOW_TYPE_DATA_ENTRY = "data_entry"
WORKFLOW_TYPE_JOB_APPLICATION = "job_application"

WORKFLOW_TYPES = {
    WORKFLOW_TYPE_FORM_FILL,
    WORKFLOW_TYPE_WEB_DATA_EXTRACT,
    WORKFLOW_TYPE_DATA_ENTRY,
    WORKFLOW_TYPE_JOB_APPLICATION,
}
```

Only `form_fill` needs to execute in this phase. Other types can be accepted by constants but should not be executable until later phases.

## Workflow Statuses

Add constants:

```python
WORKFLOW_STATUS_CREATED = "CREATED"
WORKFLOW_STATUS_PLANNED = "PLANNED"
WORKFLOW_STATUS_ANALYZING = "ANALYZING"
WORKFLOW_STATUS_MAPPING_READY = "MAPPING_READY"
WORKFLOW_STATUS_REVIEWING = "REVIEWING"
WORKFLOW_STATUS_READY_TO_FILL = "READY_TO_FILL"
WORKFLOW_STATUS_FILLING = "FILLING"
WORKFLOW_STATUS_VERIFYING = "VERIFYING"
WORKFLOW_STATUS_WAITING_APPROVAL = "WAITING_APPROVAL"
WORKFLOW_STATUS_COMPLETED = "COMPLETED"
WORKFLOW_STATUS_FAILED = "FAILED"
WORKFLOW_STATUS_BLOCKED = "BLOCKED"
WORKFLOW_STATUS_LOGIN_REQUIRED = "LOGIN_REQUIRED"
WORKFLOW_STATUS_LOGIN_IN_PROGRESS = "LOGIN_IN_PROGRESS"
```

## Transition Rules

Create `backend/app/services/workflow_state_service.py`.

Required interface:

```python
from app.models import Task

class InvalidWorkflowTransition(ValueError):
    pass

def set_workflow_status(task: Task, next_status: str, *, reason: str | None = None) -> None:
    ...

def can_transition(current_status: str, next_status: str) -> bool:
    ...

def sync_legacy_status(task: Task) -> None:
    ...
```

Allowed transitions:

```python
ALLOWED_TRANSITIONS = {
    "CREATED": {"PLANNED", "ANALYZING", "FAILED"},
    "PLANNED": {"ANALYZING", "BLOCKED", "FAILED"},
    "ANALYZING": {"MAPPING_READY", "LOGIN_REQUIRED", "FAILED"},
    "LOGIN_REQUIRED": {"LOGIN_IN_PROGRESS", "FAILED"},
    "LOGIN_IN_PROGRESS": {"ANALYZING", "LOGIN_REQUIRED", "FAILED"},
    "MAPPING_READY": {"REVIEWING", "READY_TO_FILL", "FAILED"},
    "REVIEWING": {"READY_TO_FILL", "MAPPING_READY", "FAILED", "BLOCKED"},
    "READY_TO_FILL": {"FILLING", "FAILED", "BLOCKED"},
    "FILLING": {"VERIFYING", "WAITING_APPROVAL", "FAILED"},
    "VERIFYING": {"WAITING_APPROVAL", "FAILED", "BLOCKED"},
    "WAITING_APPROVAL": {"COMPLETED", "FAILED", "BLOCKED"},
    "COMPLETED": set(),
    "FAILED": {"ANALYZING", "MAPPING_READY"},
    "BLOCKED": {"REVIEWING", "FAILED"},
}
```

The service should also update `task.status = task.workflow_status` so existing UI continues to work.

## Database Initialization

Modify `backend/app/database.py` to add missing columns for old SQLite databases:

```python
"workflow_type": "VARCHAR(50) NOT NULL DEFAULT 'form_fill'",
"workflow_status": "VARCHAR(50) NOT NULL DEFAULT 'CREATED'",
```

Use the existing migration-like helper style.

## Schema Changes

Modify `TaskCreate` in `backend/app/schemas.py`:

```python
workflow_type: str = "form_fill"
```

Validate that unsupported workflow types are rejected by the router.

Modify `TaskResponse`:

```python
workflow_type: str = "form_fill"
workflow_status: str
```

## API Changes

### POST `/tasks`

Request:

```json
{
  "url": "https://example.com/form",
  "profile_id": 1,
  "description": "Internship application",
  "workflow_type": "form_fill"
}
```

Response includes:

```json
{
  "workflow_type": "form_fill",
  "workflow_status": "CREATED"
}
```

If `workflow_type` is not supported:

```json
{
  "detail": "Unsupported workflow_type: unknown_type"
}
```

HTTP status: `400`.

## Backend Changes

- Use `set_workflow_status()` in task route actions where status is changed.
- If replacing every direct assignment is too large, update the main transitions first:
  - create task
  - analyze start/success/failure
  - login required
  - map success/failure
  - confirm mapping
  - fill start/success/failure
  - confirm submit success/failure
- Keep direct assignments only if they are covered by tests and synchronized before commit.

## Frontend Changes

Minimal frontend changes:

- `frontend/src/taskRunState.js` should prefer `task.workflow_status || task.status`.
- Existing UI labels should continue to render the same way.
- Create Task page may expose workflow type only if it can be done with a simple select. If not, default to `form_fill` and leave template UI for Phase 04.

## Tests Required

### Backend

Create `backend/tests/test_workflow_state_service.py`.

Test cases:

- `can_transition("CREATED", "ANALYZING")` is true.
- `can_transition("CREATED", "COMPLETED")` is false.
- `set_workflow_status()` updates both `workflow_status` and legacy `status`.
- invalid transition raises `InvalidWorkflowTransition`.
- old SQLite migration helper adds `workflow_type` and `workflow_status`.

Update existing task tests to assert response includes workflow fields.

### Frontend

Update `frontend/src/taskRunState.test.js`:

- task with `workflow_status` uses that value.
- task without `workflow_status` still uses legacy `status`.

## Acceptance Criteria

- Existing form-fill flow still works.
- Existing tests still pass.
- New workflow status fields exist in API responses.
- Invalid transitions are rejected by unit tests.
- No new runtime dependency is added.

## Implementation Order

1. Add constants to `backend/app/workflow_constants.py`.
2. Add columns to `Task`.
3. Add migration helper in `database.py`.
4. Add `workflow_state_service.py`.
5. Update schemas.
6. Update task creation and main route status transitions.
7. Update frontend task run state helper.
8. Add tests.
9. Run backend and frontend tests.

## Trae Prompt

Implement Phase 01. Add workflow_type and workflow_status to the existing Task model, introduce a workflow_state_service with explicit transition validation, synchronize legacy task.status, update schemas and task routes minimally, and add backend/frontend tests. Preserve the existing form-fill UX and do not introduce planner, policy, approval, memory, or eval features in this phase.
