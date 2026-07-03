# Phase 5 Personal Web Workflow Agent

> For agentic workers: templates are the boundary. If a user goal does not match a supported template, do not automate it.

## Background

By Phase 4, the product can represent workflows, generate reviewable plans, and
execute approved safe steps. Phase 5 packages that capability as a bounded
personal web workflow agent for common browser tasks such as application flows,
profile updates, appointment requests, status checks, and receipt downloads.

The key product decision is restraint: users may describe goals, but execution
must stay inside supported templates and the review-first approval model.

## Goals

- Define explicit supported workflow templates.
- Add API and UI surfaces for template-bound workflow creation.
- Classify user goals into supported templates using deterministic rules.
- Document product scope and safety boundaries.
- Update portfolio docs to reflect the form-agent to workflow-agent evolution.

## Non-Goals

- Do not support arbitrary free-form web automation.
- Do not call an LLM for intent classification in this phase.
- Do not automate payments, purchases, account deletion, CAPTCHA solving,
  anti-bot bypass, or hidden bulk submissions.
- Do not claim support for websites or flows that have not been tested.
- Do not weaken final-submission approval.

## Ponytail Scope Controls

| Temptation | Do instead | Add later only when |
| --- | --- | --- |
| LLM router for every goal | Deterministic keyword mapping | Real usage shows rules are inadequate |
| Template database | Static service list | Users need admin-managed templates |
| Arbitrary workflow builder | Fixed supported templates | A tested template cannot express needed flow |
| Marketing landing page | Operational template catalog | The app needs public positioning |
| Broad website claims | Document tested local/safe flows only | Real compatibility data exists |

The smallest useful agent is template-bound, deterministic, and review-first.

## Design

### Product Positioning

```text
A review-first personal web workflow agent for approved browser tasks.
```

### Template Boundary

Required templates:

```text
application_flow
profile_update
appointment_request
status_check
receipt_download
```

Each template defines:

- `id`
- `title`
- `description`
- `allowed_actions`
- `blocked_actions`
- `review_policy`

Every template must block:

```text
payment, purchase, delete, captcha
```

### Intent Classification

Intent classification is deterministic in Phase 5:

- apply/register/admission/job/internship -> `application_flow`
- update/profile/account information -> `profile_update`
- appointment/book/reserve/schedule -> `appointment_request`
- status/check/progress/application status -> `status_check`
- receipt/download/confirmation -> `receipt_download`

No match returns no template and a clear reason.

## Implementation Plan

### Task 1: Supported Workflow Templates

Files:

- Create `backend/app/services/workflow_template_service.py`.
- Test with `backend/tests/test_workflow_template_service.py`.

Interface:

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

Implementation:

- Include all required templates.
- Add English descriptions.
- Include `allowed_actions`, `blocked_actions`, and `review_policy`.
- Ensure every template blocks payment and delete.
- Do not call an LLM.

Validation:

```powershell
cd backend
pytest tests/test_workflow_template_service.py -v
```

### Task 2: Template API

Files:

- Create `backend/app/routers/workflow_templates.py`.
- Modify `backend/app/main.py`.
- Modify `backend/app/schemas.py`.
- Test with `backend/tests/test_workflow_template_endpoints.py`.

Endpoints:

```text
GET /workflow-templates
GET /workflow-templates/{template_id}
POST /workflow-templates/{template_id}/workflows
```

Implementation:

- Return all supported templates.
- Return `404` for unknown templates.
- Create workflows from valid templates using the Phase 3 workflow service.
- Accept `profile_id`, `start_url`, and optional `title`.
- Store or return the selected template id with the workflow response.
- Return `404` for missing profile.

Validation:

```powershell
cd backend
pytest tests/test_workflow_template_endpoints.py -v
```

### Task 3: Template Catalog UI

Files:

- Create `frontend/src/workflowTemplatePresentation.js`.
- Create `frontend/src/workflowTemplatePresentation.test.js`.
- Create `frontend/src/pages/WorkflowTemplates.jsx`.
- Modify `frontend/src/api.js`.
- Modify `frontend/src/App.jsx`.
- Modify `frontend/src/styles.css` only as needed.

Implementation:

- Add route `/workflow-templates`.
- Page heading: `Workflow Templates`.
- Show each template title, description, allowed actions, and blocked actions.
- Use blocked labels:
  - `No payments`
  - `No purchases`
  - `No account deletion`
  - `No CAPTCHA bypass`
- Keep copy operational, not marketing-heavy.

Validation:

```powershell
cd frontend
npm test -- workflowTemplatePresentation.test.js
```

### Task 4: Create Workflow UI

Files:

- Create `frontend/src/pages/CreateWorkflow.jsx`.
- Modify `frontend/src/api.js`.
- Modify `frontend/src/App.jsx`.
- Modify `frontend/src/styles.css` only as needed.

Implementation:

- Add route `/workflows/new`.
- Add controls:
  - template selector
  - profile selector
  - start URL input
  - optional title input
- Button text: `Create workflow`.
- Navigate to `/workflows/:workflowId` after creation.
- Validate non-empty URL before sending.
- Show English API errors.

Validation:

- Add helper tests if matching page-level test patterns exist.
- Otherwise cover this through manual verification in Task 8.

### Task 5: Deterministic Intent Classification

Files:

- Create `backend/app/services/workflow_intent_service.py`.
- Test with `backend/tests/test_workflow_template_service.py`.

Interface:

```python
def classify_workflow_intent(user_goal: str) -> dict[str, str]:
    """Map a user goal to a supported workflow template using deterministic rules."""
```

Implementation:

- Use keyword rules only.
- Return a template id and reason when matched.
- Return `{"template_id": "", "reason": "No supported template matched this goal."}` when unsupported.
- Do not call an LLM.

Validation:

```powershell
cd backend
pytest tests/test_workflow_template_service.py -v
```

### Task 6: Scope Documentation

Files:

- Create `docs/personal-web-workflow-scope.md`.
- Modify `README.md`.

Content:

- Use the product positioning:

```text
A review-first personal web workflow agent for approved browser tasks.
```

- Explain supported templates.
- Explain out-of-scope tasks:
  - payments
  - purchases
  - deletes
  - CAPTCHA solving
  - anti-bot bypass
  - hidden bulk submissions
- Explain why templates are used instead of arbitrary autonomous browsing.

### Task 7: Portfolio Packaging Updates

Files:

- Modify `README.md`.
- Modify `docs/architecture.md`.
- Modify `docs/demo-walkthrough.md`.
- Modify `docs/safety-boundaries.md`.

Implementation:

- Update architecture docs with templates, workflows, plans, and evidence.
- Add one template-driven flow to the demo walkthrough.
- Keep safety boundaries prominent.
- Do not claim support for untested websites.
- Keep all copy English.

### Task 8: Verification

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

- Open `/workflow-templates`.
- Open `/workflows/new`.
- Create a workflow from each supported template using a safe local URL.
- Confirm unsupported actions remain blocked.
- Confirm final submission still requires explicit approval.

## Risks

- **Template sprawl:** Keep templates static until real usage proves the need for
  admin-managed templates.
- **False autonomy:** The UI must make template boundaries obvious.
- **Intent misclassification:** Deterministic rules should fail closed with a
  clear unsupported reason.
- **Portfolio overclaiming:** Documentation must describe approved browser tasks,
  not general-purpose autonomous web control.

## Follow-Up

- Add LLM-assisted intent classification only after deterministic rules produce
  measurable friction, and keep template validation as the final authority.
- Add template persistence only when templates need user or admin management.
- Add compatibility notes only for websites that have been tested.

## Acceptance Criteria

- All required templates exist and block unsafe actions.
- Template API lists, fetches, and creates template-bound workflows.
- Template catalog and create-workflow UI are available.
- Intent classification is deterministic and fails closed.
- Product documentation clearly states supported and unsupported scope.
- Final submission remains explicitly approved.

## Self-Review

- This phase expands product framing without expanding into arbitrary browsing.
- The template boundary is the safety boundary.
- The implementation stays static and deterministic until evidence demands more.
