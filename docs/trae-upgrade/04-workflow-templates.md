# Phase 04 - Workflow Templates

## Goal

Introduce reusable workflow templates so the product is no longer framed as one hard-coded form-fill flow.

The first executable template remains `form_fill`; additional templates can exist as planned or disabled templates until later phases implement them.

## Why This Matters

Templates make the system look and behave like a workflow platform:

- users choose a workflow type
- each workflow has explicit steps
- approval policy is attached to the workflow
- future workflows can reuse planner, policy, trace, and executor infrastructure

## Current Code To Read

- `backend/app/routers/tasks.py`
- `backend/app/schemas.py`
- `backend/app/workflow_constants.py`
- `frontend/src/pages/CreateTask.jsx`
- `frontend/src/pages/Dashboard.jsx`
- `frontend/src/App.jsx`
- `frontend/src/api.js`

## Scope

Add static workflow template definitions, expose them via API, and let task creation choose a workflow type.

## Out Of Scope

- Do not implement non-form workflows yet.
- Do not add drag-and-drop workflow builder.
- Do not allow user-defined templates in the database.
- Do not rewrite task execution.

## Template Definitions

Create `backend/app/workflow_templates.py`.

Required structure:

```python
WORKFLOW_TEMPLATES = {
    "form_fill": {
        "id": "form_fill",
        "name": "Form Fill Workflow",
        "description": "Analyze a web form, map profile data, review values, fill fields, verify, and wait for submit approval.",
        "enabled": True,
        "steps": [
            "open_url",
            "extract_form",
            "map_fields",
            "review_mapping",
            "confirm_mapping",
            "fill_form",
            "verify_fields",
            "wait_for_submit_approval",
            "submit_form"
        ],
        "approval_policy": {
            "submit": "always_required",
            "password": "blocked",
            "otp": "blocked",
            "payment": "blocked",
            "low_confidence_mapping": "review_required"
        }
    },
    "web_data_extract": {
        "id": "web_data_extract",
        "name": "Web Data Extraction Workflow",
        "description": "Open a page, extract structured data, review the result, and save it.",
        "enabled": False,
        "steps": [
            "open_url",
            "extract_dom",
            "identify_target_data",
            "extract_structured_json",
            "review_extraction",
            "save_result"
        ],
        "approval_policy": {
            "external_navigation": "review_required"
        }
    },
    "data_entry": {
        "id": "data_entry",
        "name": "Data Entry Workflow",
        "description": "Map a structured record into a web application form and verify the saved result.",
        "enabled": False,
        "steps": [
            "open_url",
            "extract_form",
            "map_structured_record",
            "review_mapping",
            "fill_form",
            "verify_fields",
            "save_after_approval"
        ],
        "approval_policy": {
            "save": "review_required",
            "destructive_action": "blocked"
        }
    },
    "job_application": {
        "id": "job_application",
        "name": "Job Application Workflow",
        "description": "Apply to a job using a profile while preserving user review and submit approval.",
        "enabled": False,
        "steps": [
            "open_url",
            "detect_login_gate",
            "extract_job_context",
            "extract_application_form",
            "map_profile_and_resume_context",
            "review_mapping",
            "fill_form",
            "verify_fields",
            "wait_for_submit_approval",
            "submit_form"
        ],
        "approval_policy": {
            "submit": "always_required",
            "password": "blocked",
            "otp": "blocked",
            "payment": "blocked"
        }
    }
}
```

Add helpers:

```python
def list_workflow_templates(include_disabled: bool = True) -> list[dict[str, object]]:
    ...

def get_workflow_template(template_id: str) -> dict[str, object] | None:
    ...

def require_enabled_template(template_id: str) -> dict[str, object]:
    ...
```

`require_enabled_template()` should raise `ValueError` if missing or disabled.

## Schema

Add to `backend/app/schemas.py`:

```python
class WorkflowTemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    enabled: bool
    steps: list[str]
    approval_policy: dict[str, str] = Field(default_factory=dict)
```

Ensure `TaskCreate.workflow_type` defaults to `form_fill`.

## API Contract

Create `backend/app/routers/workflows.py`.

### GET `/workflows/templates`

Response:

```json
[
  {
    "id": "form_fill",
    "name": "Form Fill Workflow",
    "description": "Analyze a web form...",
    "enabled": true,
    "steps": ["open_url", "extract_form"],
    "approval_policy": {"submit": "always_required"}
  }
]
```

Register router in `backend/app/main.py`.

## Task Creation Behavior

In `POST /tasks`:

- If `workflow_type` missing, use `form_fill`.
- If `workflow_type` disabled, return `400`:

```json
{
  "detail": "Workflow template is not enabled: web_data_extract"
}
```

- If enabled, create task.

Only `form_fill` should be enabled in this phase.

## Frontend API

Update `frontend/src/api.js`:

```js
listWorkflowTemplates: () => request("/workflows/templates")
```

## Frontend UI

### Create Task

Modify `frontend/src/pages/CreateTask.jsx`:

- load workflow templates
- show a select or segmented control
- default selected workflow is `form_fill`
- disabled templates should appear with label `Coming soon` or be hidden; choose one and be consistent
- include selected `workflow_type` in `api.createTask()`

Recommended simple UI:

```text
Workflow
[Form Fill Workflow v]
```

Below it:

```text
Analyze a web form, map profile data, review values, fill fields, verify, and wait for submit approval.
```

No marketing copy.

### Dashboard

In task table, optionally show workflow type as a small badge if it fits. If it makes layout messy, skip it.

## Tests Required

### Backend

Create `backend/tests/test_workflow_templates.py`:

- list templates includes `form_fill`.
- `form_fill` is enabled.
- disabled templates are present when include_disabled is true.
- `require_enabled_template("form_fill")` succeeds.
- `require_enabled_template("web_data_extract")` raises.
- missing template raises.

Create `backend/tests/test_workflow_templates_endpoint.py`:

- endpoint returns templates.
- task creation with default workflow succeeds.
- task creation with disabled workflow returns 400.

### Frontend

Create `frontend/src/workflowTemplatePresentation.js` if helper logic is needed.

Test:

- enabled template label.
- disabled template label.
- default template selection picks `form_fill`.

## Acceptance Criteria

- `/workflows/templates` returns static template definitions.
- Create Task can send `workflow_type`.
- Disabled templates cannot be executed.
- Existing form-fill tasks still work.
- No database table for templates is added.

## Implementation Order

1. Add template definitions.
2. Add schema.
3. Add workflows router.
4. Register router.
5. Validate template in task creation.
6. Add frontend API.
7. Update Create Task.
8. Add tests.

## Trae Prompt

Implement Phase 04. Add static workflow templates, expose them through `/workflows/templates`, validate `workflow_type` during task creation, and add a simple Create Task workflow selector. Keep only `form_fill` enabled and do not implement execution for other workflow types.
