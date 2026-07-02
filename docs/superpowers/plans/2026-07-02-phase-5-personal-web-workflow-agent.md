# Phase 5 Personal Web Workflow Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand from application-style form flows into a controlled personal web workflow agent for approved browser tasks such as profile updates, appointment requests, status checks, and receipt downloads.

**Architecture:** Add task templates and workflow intents on top of the reviewable workflow-plan system. The system selects a supported template, creates a workflow, generates a reviewable plan, executes only approved safe steps, and records evidence.

**Tech Stack:** Python, FastAPI, SQLAlchemy, SQLite, pytest, React, Vite, Node test runner, Playwright.

## Global Constraints

- All user-facing page text must be English.
- All new code comments and docstrings must be English.
- Do not support arbitrary free-form web automation.
- Every workflow must use a supported template.
- Every execution must keep the review-first approval model.
- Payment, purchase, account deletion, destructive settings changes, CAPTCHA solving, and anti-bot bypass remain out of scope.

---

## File Structure

- `backend/app/models.py`: add `WorkflowTemplate` and `WorkflowIntent` if persistence is needed.
- `backend/app/schemas.py`: add template and intent schemas.
- `backend/app/services/workflow_template_service.py`: define and validate supported templates.
- `backend/app/services/workflow_intent_service.py`: map user goals to supported templates.
- `backend/app/routers/workflow_templates.py`: list templates and create workflow from template.
- `backend/app/main.py`: include template router.
- `backend/tests/test_workflow_template_service.py`: template rules.
- `backend/tests/test_workflow_template_endpoints.py`: API tests.
- `frontend/src/workflowTemplatePresentation.js`: template labels and limitations.
- `frontend/src/workflowTemplatePresentation.test.js`: helper tests.
- `frontend/src/pages/CreateWorkflow.jsx`: workflow creation UI.
- `frontend/src/pages/WorkflowTemplates.jsx`: supported template catalog.
- `frontend/src/App.jsx`: route registration.
- `docs/personal-web-workflow-scope.md`: final scope documentation.

---

### Task 1: Define Supported Workflow Templates

**Purpose:** Keep Phase 5 broad enough to be useful but bounded enough to be safe.

**Files:**
- Create: `backend/app/services/workflow_template_service.py`
- Test: `backend/tests/test_workflow_template_service.py`

**Interfaces:**

```python
SUPPORTED_WORKFLOW_TEMPLATES = [
    {
        "id": "application_flow",
        "title": "Application flow",
        "allowed_actions": ["fill", "select", "check", "upload", "click_next", "pause_for_review"],
    }
]

def list_workflow_templates() -> list[dict[str, object]]:
    """Return supported workflow templates."""

def get_workflow_template(template_id: str) -> dict[str, object]:
    """Return one supported workflow template or raise ValueError."""
```

**Required Templates:**
- `application_flow`
- `profile_update`
- `appointment_request`
- `status_check`
- `receipt_download`

**Implementation Instructions:**
- [ ] Each template must include `id`, `title`, `description`, `allowed_actions`, `blocked_actions`, and `review_policy`.
- [ ] `payment`, `purchase`, `delete`, and `captcha` must be listed under `blocked_actions` for every template.
- [ ] Use English descriptions.
- [ ] Do not call an LLM in this task.

**Tests:**
- [ ] All required templates exist.
- [ ] Every template blocks payment and delete.
- [ ] Unknown template id raises `ValueError`.
- [ ] Run: `cd backend; pytest tests/test_workflow_template_service.py -v`

**Acceptance Criteria:**
- The product has explicit supported workflow categories.

---

### Task 2: Add Template API

**Purpose:** Let the frontend show supported workflow types and create workflows from them.

**Files:**
- Create: `backend/app/routers/workflow_templates.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas.py`
- Test: `backend/tests/test_workflow_template_endpoints.py`

**Endpoints:**
- `GET /workflow-templates`
- `GET /workflow-templates/{template_id}`
- `POST /workflow-templates/{template_id}/workflows`

**Implementation Instructions:**
- [ ] `GET /workflow-templates` returns all supported templates.
- [ ] `POST /workflow-templates/{template_id}/workflows` accepts `profile_id`, `start_url`, and optional `title`.
- [ ] Use Phase 3 workflow creation service to create the workflow.
- [ ] Store or return the selected template id with the workflow response.
- [ ] Unknown template returns `404`.
- [ ] Missing profile returns `404`.

**Tests:**
- [ ] Lists templates.
- [ ] Unknown template returns `404`.
- [ ] Valid template creates workflow.
- [ ] Run: `cd backend; pytest tests/test_workflow_template_endpoints.py -v`

**Acceptance Criteria:**
- Workflows can be created from explicit templates.

---

### Task 3: Add Template Catalog UI

**Purpose:** Show users what the agent can and cannot do.

**Files:**
- Create: `frontend/src/workflowTemplatePresentation.js`
- Create: `frontend/src/workflowTemplatePresentation.test.js`
- Create: `frontend/src/pages/WorkflowTemplates.jsx`
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/styles.css`

**Implementation Instructions:**
- [ ] Add route `/workflow-templates`.
- [ ] Page heading: `"Workflow Templates"`.
- [ ] Show each template title, description, allowed actions, and blocked actions.
- [ ] Use clear English blocked action labels:
  - `"No payments"`
  - `"No purchases"`
  - `"No account deletion"`
  - `"No CAPTCHA bypass"`
- [ ] Do not use marketing copy; this is an operational product page.

**Tests:**
- [ ] Template labels are stable.
- [ ] Blocked action labels are stable.
- [ ] Run: `cd frontend; npm test -- workflowTemplatePresentation.test.js`

**Acceptance Criteria:**
- Users understand supported and unsupported workflow categories.

---

### Task 4: Add Create Workflow UI

**Purpose:** Replace ad hoc task creation for broader workflows with a template-driven entry point.

**Files:**
- Create: `frontend/src/pages/CreateWorkflow.jsx`
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/styles.css`

**Implementation Instructions:**
- [ ] Add route `/workflows/new`.
- [ ] Controls:
  - template selector
  - profile selector
  - start URL input
  - optional title input
- [ ] Button text: `"Create workflow"`.
- [ ] After creation, navigate to `/workflows/:workflowId`.
- [ ] Validate URL is non-empty before sending request.
- [ ] Show English errors from API.

**Tests:**
- [ ] If page-level tests exist, add helper-level tests for label functions. If no page testing pattern exists, keep this task covered by manual verification in Task 8.

**Acceptance Criteria:**
- Users can start a template-bound workflow from the UI.

---

### Task 5: Add Intent Classification Without Autonomy

**Purpose:** Let users describe a goal while still mapping only to supported templates.

**Files:**
- Create: `backend/app/services/workflow_intent_service.py`
- Test: `backend/tests/test_workflow_template_service.py`

**Interfaces:**

```python
def classify_workflow_intent(user_goal: str) -> dict[str, str]:
    """Map a user goal to a supported workflow template using deterministic rules."""
```

**Implementation Instructions:**
- [ ] Use deterministic keyword rules only.
- [ ] Map apply/register/admission/job/internship to `application_flow`.
- [ ] Map update/profile/account information to `profile_update`.
- [ ] Map appointment/book/reserve/schedule to `appointment_request`.
- [ ] Map status/check/progress/application status to `status_check`.
- [ ] Map receipt/download/confirmation to `receipt_download`.
- [ ] If no rule matches, return `{"template_id": "", "reason": "No supported template matched this goal."}`.
- [ ] Do not call an LLM in this task.

**Tests:**
- [ ] Each template has at least one matching goal example.
- [ ] Unsupported goal returns no template id.
- [ ] Run: `cd backend; pytest tests/test_workflow_template_service.py -v`

**Acceptance Criteria:**
- Goal text improves UX without enabling arbitrary automation.

---

### Task 6: Add Scope Documentation

**Purpose:** Present the product as a personal web workflow agent with clear limits.

**Files:**
- Create: `docs/personal-web-workflow-scope.md`
- Modify: `README.md`

**Implementation Instructions:**
- [ ] Use this English positioning:

```text
A review-first personal web workflow agent for approved browser tasks.
```

- [ ] Explain supported templates.
- [ ] Explain out-of-scope tasks:
  - payments
  - purchases
  - deletes
  - CAPTCHA solving
  - anti-bot bypass
  - hidden bulk submissions
- [ ] Explain why the system uses templates instead of arbitrary autonomous browsing.
- [ ] Link the document from README.

**Acceptance Criteria:**
- The expanded product positioning is broad but not vague.

---

### Task 7: Add Portfolio Packaging Updates

**Purpose:** Make the final expanded system easy to evaluate.

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/demo-walkthrough.md`
- Modify: `docs/safety-boundaries.md`

**Implementation Instructions:**
- [ ] Update architecture docs to include templates, workflows, plans, and evidence.
- [ ] Update demo walkthrough with one template-driven flow.
- [ ] Keep safety boundaries prominent.
- [ ] Do not claim support for websites or workflows that have not been tested.
- [ ] Keep all copy English.

**Acceptance Criteria:**
- The README communicates the evolution from form agent to workflow agent.

---

### Task 8: Verification

**Commands:**
- [ ] Run: `cd backend; pytest -v`
- [ ] Run: `cd frontend; npm test`
- [ ] Run: `cd frontend; npm run build`

**Manual Verification:**
- [ ] Open `/workflow-templates`.
- [ ] Open `/workflows/new`.
- [ ] Create a workflow from each supported template using a safe local URL.
- [ ] Confirm unsupported actions remain blocked.
- [ ] Confirm final submission still requires explicit approval.

**Acceptance Criteria:**
- Template-driven workflows work without enabling arbitrary browsing.
- Product docs match actual capabilities.

## Self-Review

- Spec coverage: This plan expands the product into supported personal web workflows.
- Placeholder scan: No placeholder implementation steps remain.
- Scope check: This phase remains template-bound and review-first.
