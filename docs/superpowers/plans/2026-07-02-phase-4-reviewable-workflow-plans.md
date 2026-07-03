# Phase 4 Reviewable Workflow Plans

> For agentic workers: plan execution is allowed only after explicit approval. Blocked steps stay blocked even if the database is edited by hand.

## Background

Phase 2 adds typed action candidates. Phase 3 adds ordered workflow steps. Phase
4 connects them with a reviewable plan layer: the system proposes a sequence of
safe browser actions, the user reviews the plan, and only approved non-final
steps may execute.

This is the first phase that broadens execution beyond the original single-form
fill path, so the approval model must stay simple and strict.

## Goals

- Persist draft workflow plans separately from raw action candidates.
- Let users review, edit, approve, or skip plan steps.
- Keep blocked candidates visible but unapprovable.
- Execute only approved, non-final, non-blocked plan steps.
- Preserve explicit final submission approval.

## Non-Goals

- Do not support natural-language arbitrary browser commands.
- Do not run unapproved plans.
- Do not approve blocked steps from the UI.
- Do not submit forms automatically.
- Do not add branching, retries, scheduling, or background execution.

## Ponytail Scope Controls

| Temptation | Do instead | Add later only when |
| --- | --- | --- |
| Full workflow DSL | Persist simple ordered plan steps | Users need branching and conditionals |
| Policy engine | Validate approval with deterministic functions | Safety rules become too numerous for clear code |
| Background executor | Execute through one request path | Execution becomes long-running or resumable |
| Plan diff UI | Show current draft steps | Users need to compare plan revisions |
| Editable selector tooling | Allow only value/status edits | Real review shows selectors need correction |

The minimal safe version is a draft plan, approval validation, and execution of
approved non-final steps only.

## Design

### Architecture

```text
WorkflowStep
  -> ActionCandidate records
  -> WorkflowPlan
    -> WorkflowPlanStep records
    -> Review Plan UI
    -> Approval validation
    -> Execute approved non-final steps
    -> WAITING_APPROVAL before final submit
```

Raw candidates are observations. Plan steps are user-reviewable instructions.
Execution reads plan steps, not candidates directly.

### Plan Statuses

Plan statuses:

```text
DRAFT
APPROVED
EXECUTING
WAITING_APPROVAL
COMPLETED
FAILED
```

Plan step statuses:

```text
PENDING_REVIEW
APPROVED
SKIPPED
BLOCKED
DONE
FAILED
```

Blocked steps are retained for visibility and cannot become approved through the
normal API.

### Approval Rules

Approval fails when:

- A blocked step is being approved.
- A required fill/select/check step has no value.
- The plan contains an unsupported action type.
- The plan attempts final submission.

Return `409` with English validation details.

## Implementation Plan

### Task 1: Workflow Plan Models

Files:

- Modify `backend/app/models.py`.
- Modify `backend/app/schemas.py`.
- Test with `backend/tests/test_database_migrations.py`.

Interfaces:

```text
WorkflowPlan:
  id, workflow_run_id, workflow_step_id, status, created_at, updated_at

WorkflowPlanStep:
  id, workflow_plan_id, step_index, action_candidate_id, action_type,
  label, selector, value, status, safety_level, blocked_reason
```

Implementation:

- Add SQLAlchemy models with English docstrings.
- Add response schemas.
- Order plan steps by `step_index`.
- Do not reuse `FormField` status fields.

Validation:

```powershell
cd backend
pytest tests/test_database_migrations.py -v
```

### Task 2: Generate Draft Plans

Files:

- Create `backend/app/services/workflow_plan_service.py`.
- Test with `backend/tests/test_workflow_plan_service.py`.

Interface:

```python
def generate_draft_plan(db, workflow_run_id: int, workflow_step_id: int):
    """Create a draft plan from action candidates for one workflow step."""

def validate_plan_for_approval(plan) -> list[dict[str, str]]:
    """Return blocking validation errors for a draft plan."""
```

Implementation:

- Include safe and review-required candidates.
- Include blocked candidates as `BLOCKED` plan steps for visibility.
- Sort by candidate id unless tested DOM order is available.
- Set fill/select/check actions to `PENDING_REVIEW`.
- Set blocked actions to `BLOCKED`.
- Do not generate submit actions.
- Fail approval when required values are missing.

Validation:

```powershell
cd backend
pytest tests/test_workflow_plan_service.py -v
```

### Task 3: Plan API

Files:

- Modify `backend/app/routers/workflows.py`.
- Modify `backend/app/schemas.py`.
- Test with `backend/tests/test_workflow_plan_endpoints.py`.

Endpoints:

```text
POST /workflows/{workflow_id}/steps/{step_id}/plan
GET /workflows/{workflow_id}/steps/{step_id}/plan
PUT /workflows/{workflow_id}/plans/{plan_id}/steps/{plan_step_id}
POST /workflows/{workflow_id}/plans/{plan_id}/approve
```

Implementation:

- Updating a step may change only `value` and `status`.
- Disallow `APPROVED` on blocked steps.
- Approval returns `409` with English validation errors when incomplete.
- Approval sets plan status to `APPROVED`.
- Approval does not execute the plan.

Validation:

```powershell
cd backend
pytest tests/test_workflow_plan_endpoints.py -v
```

### Task 4: Review Plan UI

Files:

- Create `frontend/src/workflowPlanPresentation.js`.
- Create `frontend/src/workflowPlanPresentation.test.js`.
- Create `frontend/src/pages/ReviewWorkflowPlan.jsx`.
- Modify `frontend/src/api.js`.
- Modify `frontend/src/App.jsx`.
- Modify `frontend/src/styles.css` only as needed.

Implementation:

- Add route `/workflows/:workflowId/steps/:stepId/review-plan`.
- Show heading `Review Plan`.
- Show step number, action type, label, value control where applicable, status,
  safety level, and blocked reason.
- Use buttons:
  - `Approve plan`
  - `Skip step`
  - `Save value`
  - `Back to workflow`
- Disable blocked steps.
- Do not show `Run automatically`.

Validation:

```powershell
cd frontend
npm test -- workflowPlanPresentation.test.js
```

### Task 5: Execute Approved Non-Final Steps

Files:

- Create `backend/app/services/plan_execution_service.py`.
- Modify `backend/app/routers/workflows.py`.
- Modify `backend/app/services/browser_executor.py` only for minimal reusable
  action helpers.
- Test with `backend/tests/test_workflow_plan_endpoints.py`.

Endpoint:

```text
POST /workflows/{workflow_id}/plans/{plan_id}/execute
```

Implementation:

- Reject execution unless plan status is `APPROVED`.
- Execute only steps with status `APPROVED`.
- Skip steps with status `SKIPPED`.
- Reject blocked steps even if persisted status was tampered with.
- Reuse existing browser executor patterns for fill/select/check.
- Do not submit final forms.
- Capture a screenshot after execution.
- Set plan status to `WAITING_APPROVAL` when final review is required.

Validation:

```powershell
cd backend
pytest tests/test_workflow_plan_endpoints.py -v
```

### Task 6: Verification

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

- Draft plan can be created and reviewed.
- Missing required values block approval.
- Blocked steps cannot be approved.
- Approved non-final steps execute.
- Final submission remains a separate explicit approval.

## Risks

- **Approval bypass:** Validate safety in backend execution, not only in the UI.
- **Plan/action drift:** Generate plans from persisted candidates and keep each
  plan step linked to its candidate for traceability.
- **Executor expansion:** Add only the browser helper calls needed by approved
  fill/select/check steps.
- **Unsafe final action:** Treat submit-like actions as blocked or final-review
  only; never execute them in this phase.

## Follow-Up

- Add plan revision history only after users need to compare drafts.
- Add retries only after real failures show repeatable transient patterns.
- Add richer value editing only after the basic review UI is used.

## Acceptance Criteria

- Plans persist independently from candidates.
- Draft plans are deterministic and reviewable.
- API approval blocks unsafe or incomplete plans.
- UI prevents approving blocked steps.
- Execution rejects unapproved or blocked steps.
- Existing single-task fill flow still works.

## Self-Review

- This phase adds reviewed execution, not open-ended automation.
- The backend remains the safety authority.
- The plan model is intentionally small until real workflows prove it needs more.
