# Phase 3 Multi-Step Application Flows

> For agentic workers: reuse the existing task pipeline for each step. Do not invent a second form-filling engine.

## Background

The current product handles one reviewed form-fill task at a time. Real
application flows often span multiple pages, but they still need the same safety
properties: extraction, mapping, review, confirmation, fill, and pause before
submission.

Phase 3 adds workflow runs and ordered workflow steps. Each step points back to
the existing `Task` flow instead of duplicating task behavior.

## Goals

- Store ordered multi-step workflows.
- Reuse the existing single-task analysis and review pipeline for each step.
- Gate progression so users cannot skip review.
- Add a simple frontend shell to inspect workflow steps and open task review.
- Preserve the current single-page task flow.

## Non-Goals

- Do not add free-form browsing.
- Do not execute multi-step plans automatically.
- Do not support cross-tab orchestration.
- Do not auto-select files for upload.
- Do not add arbitrary natural-language browser commands.

## Ponytail Scope Controls

| Temptation | Do instead | Add later only when |
| --- | --- | --- |
| New workflow engine dependency | Two SQLAlchemy models plus a small service | Branching workflows become necessary |
| Duplicate task analysis code | Create or link normal `Task` records | Task code has been extracted into stable services |
| Background job runner | Keep prepare actions request-driven | Long-running workflow execution becomes real |
| Complex visual timeline | Ordered step list | Users need dense comparison across many steps |
| Cross-tab browser manager | Same-tab, user-approved progression | Real sites require tested cross-tab support |

The minimum useful workflow is an ordered list of reviewed task-backed steps.

## Design

### Architecture

```text
WorkflowRun
  -> WorkflowStep 1 -> Task -> existing review-first task flow
  -> WorkflowStep 2 -> Task -> existing review-first task flow
  -> WorkflowStep N -> Task -> existing review-first task flow
```

`WorkflowRun` owns the user-facing flow. `WorkflowStep` owns ordering and links
to a normal `Task`. The task continues to own field extraction, mapping,
confirmation, fill, logs, screenshots, and approval state.

### Status Model

Workflow statuses:

```text
CREATED
ANALYZING_STEP
STEP_REVIEW_REQUIRED
READY_FOR_NEXT_STEP
WAITING_APPROVAL
COMPLETED
FAILED
```

Do not change existing `Task.status` values.

### Progression Gate

A next step may be appended only when the current linked task is:

```text
WAITING_APPROVAL
COMPLETED
```

Anything earlier returns `409` with a clear English reason.

## Implementation Plan

### Task 1: Workflow Run And Step Models

Files:

- Modify `backend/app/models.py`.
- Modify `backend/app/schemas.py`.
- Test with `backend/tests/test_database_migrations.py`.

Interfaces:

```text
WorkflowRun:
  id, profile_id, start_url, title, status, created_at, updated_at

WorkflowStep:
  id, workflow_run_id, step_index, task_id, url, status,
  review_required, summary
```

Implementation:

- Add SQLAlchemy models with English docstrings.
- Add useful relationships from `Profile` and workflow run.
- Order steps by `step_index`.
- Keep existing task tables and statuses unchanged.

Validation:

```powershell
cd backend
pytest tests/test_database_migrations.py -v
```

### Task 2: Workflow Step Service

Files:

- Create `backend/app/services/workflow_step_service.py`.
- Test with `backend/tests/test_workflow_steps.py`.

Interface:

```python
def create_workflow_run(db, profile_id: int, start_url: str, title: str | None = None):
    """Create a workflow run with an initial step."""

def append_workflow_step(db, workflow_run_id: int, url: str, task_id: int | None = None):
    """Append the next ordered workflow step."""

def summarize_workflow_run(workflow_run) -> dict[str, int]:
    """Return counts for total, completed, blocked, and failed steps."""
```

Implementation:

- Initial workflows create step index `1`.
- Appended steps use max index + 1.
- Prevent duplicate active steps with the same index.
- Keep status counting deterministic.

Validation:

```powershell
cd backend
pytest tests/test_workflow_steps.py -v
```

### Task 3: Workflow API

Files:

- Create `backend/app/routers/workflows.py`.
- Modify `backend/app/main.py`.
- Modify `backend/app/schemas.py`.
- Test with `backend/tests/test_workflow_endpoints.py`.

Endpoints:

```text
POST /workflows
GET /workflows
GET /workflows/{workflow_id}
POST /workflows/{workflow_id}/steps
```

Implementation:

- `POST /workflows` accepts `profile_id`, `start_url`, and optional `title`.
- Validate profile existence.
- Return ordered steps in detail responses.
- Do not execute browser actions from these endpoints.

Validation:

```powershell
cd backend
pytest tests/test_workflow_endpoints.py -v
```

### Task 4: Prepare One Workflow Step

Files:

- Modify `backend/app/routers/workflows.py`.
- Modify `backend/app/services/workflow_step_service.py`.
- Test with `backend/tests/test_workflow_endpoints.py`.

Endpoint:

```text
POST /workflows/{workflow_id}/steps/{step_id}/prepare
```

Implementation:

- Create a normal `Task` for the step if none exists.
- Reuse the existing task analysis behavior through shared service logic where
  available.
- Reuse a linked task if it already exists.
- Set step and workflow status to `STEP_REVIEW_REQUIRED` when mapping is ready.
- Surface login-required state through the linked task.
- Do not auto-fill.

### Task 5: Workflow Frontend Shell

Files:

- Create `frontend/src/workflowPresentation.js`.
- Create `frontend/src/workflowPresentation.test.js`.
- Create `frontend/src/pages/WorkflowDetail.jsx`.
- Modify `frontend/src/api.js`.
- Modify `frontend/src/App.jsx`.

Interface:

```javascript
export function workflowStatusLabel(status) {
  return "Step review required";
}

export function stepStatusLabel(status) {
  return "Ready for review";
}
```

Implementation:

- Add route `/workflows/:workflowId`.
- Show title, start URL, status, and ordered steps.
- Show step number, URL, status, and linked task button when `task_id` exists.
- Use button text:
  - `Prepare step`
  - `Open task review`
  - `Add next step`
- Do not add automatic execution buttons.

Validation:

```powershell
cd frontend
npm test -- workflowPresentation.test.js
```

### Task 6: Next-Step Gate

Files:

- Modify `backend/app/services/workflow_step_service.py`.
- Modify `backend/app/routers/workflows.py`.
- Test with `backend/tests/test_workflow_endpoints.py`.

Interface:

```python
def can_append_next_step(current_step) -> tuple[bool, str | None]:
    """Return whether a next step can be appended after the current step."""
```

Implementation:

- Allow next step only after linked task status `WAITING_APPROVAL` or
  `COMPLETED`.
- Return `409` with an English reason when blocked.
- Keep the rule in one service function.

### Task 7: Verification

Run:

```powershell
cd backend
pytest -v
```

```powershell
cd frontend
npm test
npm run build
```

Manual checks:

- Existing single-task flow still works.
- Workflow steps stay ordered.
- Users cannot add the next step before review gates are satisfied.

## Risks

- **Duplicate task logic:** Keep workflow prepare thin and reuse task behavior.
- **Status confusion:** Workflow status summarizes step state; task status still
  owns actual form-fill progress.
- **Premature automation:** This phase creates structure and gates only, not
  automatic multi-step execution.

## Follow-Up

- Add reviewable plans in Phase 4.
- Add template-bound personal workflows in Phase 5.
- Add branching only after linear workflows are tested and insufficient.

## Acceptance Criteria

- Workflow storage exists without disrupting tasks.
- Workflow APIs create, list, fetch, and append ordered steps.
- Preparing a step creates or reuses a linked task.
- The frontend shell shows workflow progress and links to task review.
- Progression is blocked until review gates are met.

## Self-Review

- This phase adds the smallest workflow layer that can work.
- It does not build a planner, scheduler, or autonomous browser.
- The existing task flow remains the execution authority.
