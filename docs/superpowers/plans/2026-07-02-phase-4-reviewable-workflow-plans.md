# Phase 4 Reviewable Workflow Plans Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reviewable action plan layer so users approve a sequence of browser actions before execution.

**Architecture:** Build on Phase 2 action candidates and Phase 3 workflow steps. The backend creates `WorkflowPlan` and `WorkflowPlanStep` records from safe candidates; the frontend provides a Review Plan page where users can approve, skip, or edit non-sensitive steps.

**Tech Stack:** Python, FastAPI, SQLAlchemy, SQLite, pytest, React, Vite, Node test runner, Playwright.

## Global Constraints

- All user-facing page text must be English.
- All new code comments and docstrings must be English.
- The system must never execute an unapproved plan step.
- Blocked candidates cannot be approved from the UI.
- Final submission remains a separate explicit approval.
- Do not support natural-language arbitrary browser commands in this phase.

---

## File Structure

- `backend/app/models.py`: add `WorkflowPlan` and `WorkflowPlanStep`.
- `backend/app/schemas.py`: add plan request and response schemas.
- `backend/app/services/workflow_plan_service.py`: generate and validate plans.
- `backend/app/services/plan_execution_service.py`: execute approved non-final steps through existing browser executor.
- `backend/app/routers/workflows.py`: plan endpoints.
- `backend/tests/test_workflow_plan_service.py`: generation and validation tests.
- `backend/tests/test_workflow_plan_endpoints.py`: API tests.
- `frontend/src/workflowPlanPresentation.js`: plan labels and validation helpers.
- `frontend/src/workflowPlanPresentation.test.js`: helper tests.
- `frontend/src/pages/ReviewWorkflowPlan.jsx`: review UI.
- `frontend/src/App.jsx`: route registration.

---

### Task 1: Add Workflow Plan Models

**Purpose:** Persist action plans separately from raw action candidates.

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Test: `backend/tests/test_database_migrations.py`

**Interfaces:**
- `WorkflowPlan`:
  - `id`
  - `workflow_run_id`
  - `workflow_step_id`
  - `status`
  - `created_at`
  - `updated_at`
- `WorkflowPlanStep`:
  - `id`
  - `workflow_plan_id`
  - `step_index`
  - `action_candidate_id`
  - `action_type`
  - `label`
  - `selector`
  - `value`
  - `status`
  - `safety_level`
  - `blocked_reason`

**Implementation Instructions:**
- [ ] Use statuses:
  - `"DRAFT"`
  - `"APPROVED"`
  - `"EXECUTING"`
  - `"WAITING_APPROVAL"`
  - `"COMPLETED"`
  - `"FAILED"`
- [ ] Use plan step statuses:
  - `"PENDING_REVIEW"`
  - `"APPROVED"`
  - `"SKIPPED"`
  - `"BLOCKED"`
  - `"DONE"`
  - `"FAILED"`
- [ ] Do not reuse `FormField` status fields for plan steps.

**Tests:**
- [ ] Tables are created.
- [ ] Plan steps order by `step_index`.
- [ ] Run: `cd backend; pytest tests/test_database_migrations.py -v`

**Acceptance Criteria:**
- Plans can be persisted independently from candidates.

---

### Task 2: Generate Draft Plans From Candidates

**Purpose:** Create a deterministic draft plan that users can review.

**Files:**
- Create: `backend/app/services/workflow_plan_service.py`
- Test: `backend/tests/test_workflow_plan_service.py`

**Interfaces:**

```python
def generate_draft_plan(db, workflow_run_id: int, workflow_step_id: int):
    """Create a draft plan from action candidates for one workflow step."""

def validate_plan_for_approval(plan) -> list[dict[str, str]]:
    """Return blocking validation errors for a draft plan."""
```

**Implementation Instructions:**
- [ ] Include safe and review-required candidates.
- [ ] Include blocked candidates as `BLOCKED` plan steps for visibility.
- [ ] Sort by candidate id unless DOM order is available.
- [ ] Set text/select/check actions to `PENDING_REVIEW`.
- [ ] Set blocked actions to `BLOCKED`.
- [ ] Do not generate a submit action.
- [ ] Validation must fail if required fill/select/check steps lack values.

**Tests:**
- [ ] Safe candidates become pending review steps.
- [ ] Blocked candidates become blocked steps.
- [ ] Missing required value blocks approval.
- [ ] Run: `cd backend; pytest tests/test_workflow_plan_service.py -v`

**Acceptance Criteria:**
- Draft plans are deterministic and reviewable.

---

### Task 3: Add Plan API Endpoints

**Purpose:** Let the UI create, fetch, update, and approve plans.

**Files:**
- Modify: `backend/app/routers/workflows.py`
- Modify: `backend/app/schemas.py`
- Test: `backend/tests/test_workflow_plan_endpoints.py`

**Endpoints:**
- `POST /workflows/{workflow_id}/steps/{step_id}/plan`
- `GET /workflows/{workflow_id}/steps/{step_id}/plan`
- `PUT /workflows/{workflow_id}/plans/{plan_id}/steps/{plan_step_id}`
- `POST /workflows/{workflow_id}/plans/{plan_id}/approve`

**Implementation Instructions:**
- [ ] Updating a plan step may change only `value` and `status`.
- [ ] Disallow setting `APPROVED` on blocked steps.
- [ ] Plan approval returns `409` with English validation errors if required steps are incomplete.
- [ ] Plan approval sets plan status to `"APPROVED"` and step statuses to `"APPROVED"` or `"SKIPPED"`.
- [ ] Do not execute the plan in approval endpoint.

**Tests:**
- [ ] Draft plan can be created.
- [ ] Blocked step cannot be approved.
- [ ] Missing values block plan approval.
- [ ] Valid plan can be approved.
- [ ] Run: `cd backend; pytest tests/test_workflow_plan_endpoints.py -v`

**Acceptance Criteria:**
- Plans are user-reviewable through API.

---

### Task 4: Add Review Plan UI

**Purpose:** Let users inspect and approve the planned browser actions.

**Files:**
- Create: `frontend/src/workflowPlanPresentation.js`
- Create: `frontend/src/workflowPlanPresentation.test.js`
- Create: `frontend/src/pages/ReviewWorkflowPlan.jsx`
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/styles.css`

**Implementation Instructions:**
- [ ] Add route `/workflows/:workflowId/steps/:stepId/review-plan`.
- [ ] Show heading `"Review Plan"`.
- [ ] Show each step with:
  - step number
  - action type
  - label
  - value control where applicable
  - status
  - safety level
  - blocked reason
- [ ] Use English buttons:
  - `"Approve plan"`
  - `"Skip step"`
  - `"Save value"`
  - `"Back to workflow"`
- [ ] Blocked steps must be visibly disabled.
- [ ] Do not show a button that says `"Run automatically"` in this phase.

**Tests:**
- [ ] Status labels are stable.
- [ ] Blocked steps are identified by helper.
- [ ] Missing required value is flagged.
- [ ] Run: `cd frontend; npm test -- workflowPlanPresentation.test.js`

**Acceptance Criteria:**
- A user can approve only safe/review-required plan steps.

---

### Task 5: Execute Approved Non-Final Plan Steps

**Purpose:** Execute reviewed plan steps while keeping final submit separate.

**Files:**
- Create: `backend/app/services/plan_execution_service.py`
- Modify: `backend/app/routers/workflows.py`
- Modify: `backend/app/services/browser_executor.py`
- Test: `backend/tests/test_workflow_plan_endpoints.py`

**Endpoint:**
- `POST /workflows/{workflow_id}/plans/{plan_id}/execute`

**Implementation Instructions:**
- [ ] Reject execution unless plan status is `"APPROVED"`.
- [ ] Execute only steps with status `"APPROVED"`.
- [ ] Skip steps with status `"SKIPPED"`.
- [ ] Reject blocked steps even if database status was manually changed.
- [ ] Use existing browser executor patterns for fill/select/check.
- [ ] After execution, set plan status to `"WAITING_APPROVAL"` if any final review is required.
- [ ] Do not submit forms in this endpoint.
- [ ] Capture screenshot after execution.

**Tests:**
- [ ] Draft plan execution returns `409`.
- [ ] Approved fill step calls executor path.
- [ ] Blocked step prevents execution.
- [ ] Execution does not submit final form.
- [ ] Run: `cd backend; pytest tests/test_workflow_plan_endpoints.py -v`

**Acceptance Criteria:**
- Reviewed plans can be executed safely.
- Final submit remains gated.

---

### Task 6: Verification

**Commands:**
- [ ] Run: `cd backend; pytest -v`
- [ ] Run: `cd frontend; npm test`
- [ ] Run: `cd frontend; npm run build`

**Acceptance Criteria:**
- Plan review and approval work.
- Execution rejects unapproved or blocked steps.
- Existing single-task fill flow still works.

## Self-Review

- Spec coverage: This plan adds Review Plan, approval, and safe plan execution.
- Placeholder scan: No placeholder implementation steps remain.
- Scope check: This phase does not add natural-language arbitrary browser control.
