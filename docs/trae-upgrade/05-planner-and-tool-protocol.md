# Phase 05 - Planner And Tool Protocol

## Goal

Introduce a bounded planner and tool registry so workflow execution is expressed as planned tool calls instead of route-specific hidden logic.

The first planner can be deterministic. The goal is architecture, not a fully autonomous agent.

## Why This Matters

AI Engineer projects look more professional when they separate:

- planning
- policy checking
- tool selection
- execution
- verification

This phase creates the structure needed for real agent workflows while keeping autonomy bounded.

## Current Code To Read

- `backend/app/routers/tasks.py`
- `backend/app/services/form_extractor.py`
- `backend/app/services/field_mapper.py`
- `backend/app/services/browser_executor.py`
- `backend/app/services/workflow_trace_service.py`
- `backend/app/services/policy_engine.py`
- `backend/app/workflow_templates.py`
- `backend/app/models.py`
- `backend/app/schemas.py`

## Scope

Add:

- tool registry
- deterministic planner for `form_fill`
- planned workflow steps persisted as JSON on task or as a new table
- API to view a plan
- trace spans for planning

## Out Of Scope

- Do not let LLM autonomously click pages.
- Do not execute arbitrary tools from user input.
- Do not add LangChain/LangGraph.
- Do not implement non-form workflow tools yet.
- Do not remove existing task route endpoints.

## Data Model

Prefer the minimal approach:

Add to `Task`:

```python
workflow_plan_json: Mapped[Optional[str]] = mapped_column(Text)
```

Add safe property:

```python
workflow_plan: dict[str, object]
```

If a separate table is preferred later, do it after the feature is stable.

## Tool Protocol

Create `backend/app/services/tool_registry.py`.

Tool definition shape:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    risk_level: str
    requires_approval: bool
    implemented: bool
```

Registry:

```python
TOOL_REGISTRY = {
    "open_url": ToolDefinition(...),
    "extract_dom": ToolDefinition(...),
    "extract_form": ToolDefinition(...),
    "map_fields": ToolDefinition(...),
    "request_human_approval": ToolDefinition(...),
    "fill_field": ToolDefinition(...),
    "fill_form": ToolDefinition(...),
    "click_element": ToolDefinition(...),
    "verify_fields": ToolDefinition(...),
    "capture_screenshot": ToolDefinition(...),
    "submit_form": ToolDefinition(...),
}
```

Required functions:

```python
def list_tools(include_unimplemented: bool = True) -> list[ToolDefinition]:
    ...

def get_tool(name: str) -> ToolDefinition | None:
    ...

def require_tool(name: str) -> ToolDefinition:
    ...
```

Rules:

- Unknown tool raises `ValueError`.
- Unimplemented tool should be visible but not executable.
- `submit_form` requires approval.
- `click_element` requires approval by default.
- `fill_field` is medium risk.

## Planner Service

Create `backend/app/services/planner_service.py`.

Required dataclasses:

```python
@dataclass(frozen=True)
class PlannedStep:
    step_id: str
    tool: str
    reason: str
    requires_approval: bool
    status: str = "PENDING"

@dataclass(frozen=True)
class WorkflowPlan:
    workflow_type: str
    goal: str
    steps: list[PlannedStep]
```

Required functions:

```python
def build_form_fill_plan(*, goal: str) -> WorkflowPlan:
    ...

def build_plan(*, workflow_type: str, goal: str) -> WorkflowPlan:
    ...

def plan_to_dict(plan: WorkflowPlan) -> dict[str, object]:
    ...

def save_plan(db: Session, task: Task, plan: WorkflowPlan) -> None:
    ...
```

`build_form_fill_plan()` should produce:

```python
[
    PlannedStep("open_url", "open_url", "Open the target page.", False),
    PlannedStep("extract_form", "extract_form", "Discover fillable fields and form metadata.", False),
    PlannedStep("map_fields", "map_fields", "Map profile data to extracted fields.", False),
    PlannedStep("review_mapping", "request_human_approval", "Let the user review values before execution.", True),
    PlannedStep("fill_form", "fill_form", "Fill approved values in the browser.", False),
    PlannedStep("verify_fields", "verify_fields", "Verify the browser state after filling.", False),
    PlannedStep("submit_form", "submit_form", "Submit only after explicit approval.", True),
]
```

## API Contract

Add to `backend/app/routers/workflows.py` or create `backend/app/routers/plans.py`.

### POST `/tasks/{task_id}/plan`

Creates or replaces plan for a task.

Request:

```json
{
  "goal": "Fill this internship application using my student profile."
}
```

Response:

```json
{
  "workflow_type": "form_fill",
  "goal": "Fill this internship application using my student profile.",
  "steps": [
    {
      "step_id": "extract_form",
      "tool": "extract_form",
      "reason": "Discover fillable fields and form metadata.",
      "requires_approval": false,
      "status": "PENDING"
    }
  ]
}
```

### GET `/tasks/{task_id}/plan`

Returns saved plan. If no plan exists, return `404` or generate default. Prefer `404` to avoid hidden behavior.

## Schema

Add:

```python
class PlannedStepResponse(BaseModel):
    step_id: str
    tool: str
    reason: str
    requires_approval: bool
    status: str

class WorkflowPlanRequest(BaseModel):
    goal: str

class WorkflowPlanResponse(BaseModel):
    workflow_type: str
    goal: str
    steps: list[PlannedStepResponse]
```

## Integration With Existing Flow

In `analyzeAndReview` frontend action, do not require plan yet.

Backend:

- On task creation, optionally create a default form_fill plan using task description or URL.
- If creating plan on task creation is too invasive, expose the endpoint and add a button later.

Recommended this phase:

- Create default plan during `POST /tasks`.
- Add trace span `planning.build_plan`.
- Store plan in `workflow_plan_json`.

## Frontend API

Update `frontend/src/api.js`:

```js
createTaskPlan: (taskId, goal) => ...
getTaskPlan: (taskId) => request(`/tasks/${taskId}/plan`)
```

## Frontend UI

In `TaskDetail.jsx`:

- fetch plan.
- show a compact `Workflow Plan` card.
- list step names, tools, and approval markers.

No editing UI in this phase.

## Tests Required

### Backend

Create `backend/tests/test_tool_registry.py`:

- known tool is returned.
- unknown tool raises.
- submit tool requires approval.
- unimplemented tools are listed.

Create `backend/tests/test_planner_service.py`:

- form_fill plan includes expected step ids in order.
- every planned tool exists in registry.
- submit step requires approval.
- unsupported workflow type raises.
- plan serialization is stable.

Create `backend/tests/test_workflow_plan_endpoint.py`:

- creating task stores default plan.
- GET plan returns saved plan.
- POST plan replaces plan.

### Frontend

Create `frontend/src/workflowPlanPresentation.test.js`:

- step label.
- approval marker.
- sorting preserves array order.

## Acceptance Criteria

- Tasks can have a saved workflow plan.
- Form-fill plan is deterministic and tested.
- Every planned tool must exist in registry.
- Task Detail can display a workflow plan.
- Existing task execution still works.

## Implementation Order

1. Add `workflow_plan_json` model field and migration helper.
2. Add tool registry.
3. Add planner service.
4. Add schemas.
5. Add plan endpoints.
6. Create default plan on task creation.
7. Write planning trace span if Phase 02 exists.
8. Add frontend API and Task Detail plan card.
9. Add tests.

## Trae Prompt

Implement Phase 05. Add a deterministic planner and local tool registry, store a form-fill workflow plan on tasks, expose GET/POST plan endpoints, show the plan on Task Detail, and add tests. Do not add external agent frameworks or autonomous browser control.
