# Phase 3 Multi-Step Application Flows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support safe, reviewed, multi-page application-style workflows while preserving the existing single-page form flow.

**Architecture:** Add a workflow-run layer above tasks. A workflow contains ordered steps; each step points to a URL or current-page action set, stores extracted fields and action candidates, and pauses at review gates.

**Tech Stack:** Python, FastAPI, SQLAlchemy, SQLite, pytest, React, Vite, Node test runner, Playwright.

## Global Constraints

- All user-facing page text must be English.
- All new code comments and docstrings must be English.
- Do not implement free-form web browsing.
- Multi-step execution must pause before final submission.
- Only support same-tab, user-approved progression in this phase.
- File upload support must be review-required and must not auto-select local files without user selection.

---

## File Structure

- `backend/app/models.py`: add `WorkflowRun` and `WorkflowStep`.
- `backend/app/schemas.py`: add workflow response models.
- `backend/app/services/workflow_step_service.py`: create, order, and summarize workflow steps.
- `backend/app/services/browser_executor.py`: add next-step navigation helper only after review.
- `backend/app/routers/workflows.py`: new workflow endpoints.
- `backend/app/main.py`: include workflow router.
- `backend/tests/test_workflow_steps.py`: service tests.
- `backend/tests/test_workflow_endpoints.py`: API tests.
- `frontend/src/workflowPresentation.js`: status and step labels.
- `frontend/src/workflowPresentation.test.js`: helper tests.
- `frontend/src/pages/WorkflowDetail.jsx`: workflow UI.
- `frontend/src/App.jsx`: route registration.

---

### Task 1: Add Workflow Run And Step Models

**Purpose:** Store multi-step application flows separately from existing single tasks.

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Test: `backend/tests/test_database_migrations.py`

**Interfaces:**
- `WorkflowRun`:
  - `id`
  - `profile_id`
  - `start_url`
  - `title`
  - `status`
  - `created_at`
  - `updated_at`
- `WorkflowStep`:
  - `id`
  - `workflow_run_id`
  - `step_index`
  - `task_id`
  - `url`
  - `status`
  - `review_required`
  - `summary`

**Implementation Instructions:**
- [ ] Add models with English docstrings.
- [ ] Add relationships from `Profile` to workflow runs if useful.
- [ ] Use statuses:
  - `"CREATED"`
  - `"ANALYZING_STEP"`
  - `"STEP_REVIEW_REQUIRED"`
  - `"READY_FOR_NEXT_STEP"`
  - `"WAITING_APPROVAL"`
  - `"COMPLETED"`
  - `"FAILED"`
- [ ] Do not change existing `Task.status` values.

**Tests:**
- [ ] Tables are created.
- [ ] Step ordering by `step_index` works.
- [ ] Run: `cd backend; pytest tests/test_database_migrations.py -v`

**Acceptance Criteria:**
- Workflow storage exists without disrupting existing tasks.

---

### Task 2: Add Workflow Service

**Purpose:** Centralize workflow step creation and status transitions.

**Files:**
- Create: `backend/app/services/workflow_step_service.py`
- Test: `backend/tests/test_workflow_steps.py`

**Interfaces:**

```python
def create_workflow_run(db, profile_id: int, start_url: str, title: str | None = None):
    """Create a workflow run with an initial step."""

def append_workflow_step(db, workflow_run_id: int, url: str, task_id: int | None = None):
    """Append the next ordered workflow step."""

def summarize_workflow_run(workflow_run) -> dict[str, int]:
    """Return counts for total, completed, blocked, and failed steps."""
```

**Implementation Instructions:**
- [ ] `create_workflow_run()` must create step index `1`.
- [ ] `append_workflow_step()` must use max existing index + 1.
- [ ] Do not allow duplicate active steps with the same index.
- [ ] Keep all comments/docstrings English.

**Tests:**
- [ ] Initial workflow has one step.
- [ ] Appended steps increment index.
- [ ] Summary counts statuses correctly.
- [ ] Run: `cd backend; pytest tests/test_workflow_steps.py -v`

**Acceptance Criteria:**
- Workflow step ordering is deterministic.

---

### Task 3: Add Workflow API

**Purpose:** Let frontend create and inspect multi-step workflow runs.

**Files:**
- Create: `backend/app/routers/workflows.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas.py`
- Test: `backend/tests/test_workflow_endpoints.py`

**Endpoints:**
- `POST /workflows`
- `GET /workflows`
- `GET /workflows/{workflow_id}`
- `POST /workflows/{workflow_id}/steps`

**Implementation Instructions:**
- [ ] `POST /workflows` accepts `profile_id`, `start_url`, and optional `title`.
- [ ] Validate profile exists.
- [ ] `POST /workflows/{workflow_id}/steps` appends a step with `url`.
- [ ] Do not execute browser actions from these endpoints.
- [ ] Return ordered steps in workflow detail response.

**Tests:**
- [ ] Creating workflow with missing profile returns `404`.
- [ ] Creating workflow with valid profile returns first step.
- [ ] Appending step returns ordered steps.
- [ ] Run: `cd backend; pytest tests/test_workflow_endpoints.py -v`

**Acceptance Criteria:**
- Workflows can be created and inspected.

---

### Task 4: Analyze One Workflow Step Through Existing Task Flow

**Purpose:** Reuse current task analysis and mapping for each workflow step.

**Files:**
- Modify: `backend/app/routers/workflows.py`
- Modify: `backend/app/services/workflow_step_service.py`
- Test: `backend/tests/test_workflow_endpoints.py`

**Endpoint:**
- `POST /workflows/{workflow_id}/steps/{step_id}/prepare`

**Implementation Instructions:**
- [ ] Create a normal `Task` for the step if it does not already have one.
- [ ] Call existing task analysis behavior through shared service logic if available; if not available, keep this endpoint thin and call reusable functions from `tasks.py` only after extracting them safely.
- [ ] Set step status to `"STEP_REVIEW_REQUIRED"` when mapping is ready.
- [ ] Set workflow status to `"STEP_REVIEW_REQUIRED"`.
- [ ] If login is required, keep step linked to the task and surface the task status.
- [ ] Do not auto-fill in this task.

**Tests:**
- [ ] Prepare creates a linked task.
- [ ] Existing linked task is reused.
- [ ] Workflow status reflects step review requirement.
- [ ] Run: `cd backend; pytest tests/test_workflow_endpoints.py -v`

**Acceptance Criteria:**
- Multi-step workflows reuse the current safe task pipeline.

---

### Task 5: Add Workflow Frontend Shell

**Purpose:** Provide an English UI for reviewing workflow steps.

**Files:**
- Create: `frontend/src/workflowPresentation.js`
- Create: `frontend/src/workflowPresentation.test.js`
- Create: `frontend/src/pages/WorkflowDetail.jsx`
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/App.jsx`

**Interfaces:**

```javascript
export function workflowStatusLabel(status) {
  return "Step review required";
}

export function stepStatusLabel(status) {
  return "Ready for review";
}
```

**Implementation Instructions:**
- [ ] Add API methods for workflow endpoints.
- [ ] Add route `/workflows/:workflowId`.
- [ ] Show workflow title, start URL, status, and ordered steps.
- [ ] Each step should show:
  - step number
  - URL
  - status
  - linked task button if `task_id` exists
- [ ] Button text must be English:
  - `"Prepare step"`
  - `"Open task review"`
  - `"Add next step"`
- [ ] Do not add automatic browser execution buttons.

**Tests:**
- [ ] Status labels are stable.
- [ ] Unknown statuses are humanized.
- [ ] Run: `cd frontend; npm test -- workflowPresentation.test.js`

**Acceptance Criteria:**
- Users can see a multi-step workflow shell and open existing task review.

---

### Task 6: Add Next-Step Gate

**Purpose:** Prevent workflow progression unless the current step has been reviewed and filled or intentionally skipped.

**Files:**
- Modify: `backend/app/services/workflow_step_service.py`
- Modify: `backend/app/routers/workflows.py`
- Test: `backend/tests/test_workflow_endpoints.py`

**Implementation Instructions:**
- [ ] Add a function:

```python
def can_append_next_step(current_step) -> tuple[bool, str | None]:
    """Return whether a next step can be appended after the current step."""
```

- [ ] Allow next step only when current linked task status is `"WAITING_APPROVAL"` or `"COMPLETED"`.
- [ ] Return a clear English reason when blocked.
- [ ] API should return `409` when next step is blocked.

**Tests:**
- [ ] Created step blocks next step.
- [ ] Waiting approval allows next step.
- [ ] Completed allows next step.
- [ ] Run: `cd backend; pytest tests/test_workflow_endpoints.py -v`

**Acceptance Criteria:**
- Multi-step flows cannot silently skip review gates.

---

### Task 7: Verification

**Commands:**
- [ ] Run: `cd backend; pytest -v`
- [ ] Run: `cd frontend; npm test`
- [ ] Run: `cd frontend; npm run build`

**Acceptance Criteria:**
- Single-page task flow still works.
- Workflow shell supports ordered steps.
- No multi-step action executes without review.

## Self-Review

- Spec coverage: This plan adds multi-step application workflow structure while reusing the existing task pipeline.
- Placeholder scan: No placeholder implementation steps remain.
- Scope check: This phase avoids autonomous planning and keeps same-tab, user-approved progression.
