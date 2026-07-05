# Phase 05 - Planner And Tool Protocol — Design

Date: 2026-07-05

## Background & Goals

Phases 01-04 established the core workflow vocabulary for this project:

- `Task` now carries `workflow_type` and `workflow_status`
- workflow transitions are validated explicitly
- workflow traces and approval requests are persisted independently
- workflow templates make the product look like a workflow platform instead of one hard-coded form filler

However, the current execution path is still mostly expressed as route-specific orchestration inside `tasks.py` and stage-specific code in `job_worker.py`. The system knows how to execute the form-fill workflow, but it does not yet expose a first-class, inspectable workflow plan.

This phase adds the minimum architecture needed to make workflow planning explicit without turning the system into an autonomous agent framework.

The goals are:

- Add a local tool registry describing the bounded set of supported workflow tools
- Add a deterministic planner for `form_fill`
- Persist a saved workflow plan on each task
- Expose `GET/POST /tasks/{task_id}/plan`
- Show a compact read-only Workflow Plan card on Task Detail
- Keep existing execution behavior unchanged

## Non-Goals

- No planner LLM
- No LangChain, LangGraph, or external agent framework
- No autonomous tool execution from user prompts
- No worker refactor and no planner-controlled execution loop
- No plan history, versioning, or separate `workflow_plans` table
- No editable workflow plan UI
- No non-`form_fill` execution support in this phase

## Current State & Constraints

- `Task` is the current `WorkflowRun` equivalent and should continue to be extended rather than replaced
- The main user flow still relies on explicit endpoints such as:
  - `POST /tasks`
  - `POST /tasks/{id}/analyze`
  - `POST /tasks/{id}/map-fields`
  - `POST /tasks/{id}/fill`
  - `POST /tasks/{id}/confirm-submit`
- The async worker already executes known job types and should not be re-routed through a planner in this phase
- Trace persistence is best-effort and must not break the primary workflow
- Only `form_fill` is enabled as an executable workflow template after Phase 04

These constraints mean the planner must be added as an explanatory and persistence layer first, not as a new runtime engine.

## Chosen Approach

Choose the minimal approach:

- Add `workflow_plan_json` directly to `Task`
- Add a local `tool_registry.py` that describes tools as metadata only
- Add a deterministic `planner_service.py` that builds a fixed `form_fill` plan
- On `POST /tasks`, immediately create and save a default `form_fill` plan
- Keep `GET /tasks/{task_id}/plan` read-only and return `404` when no saved plan exists
- Add `POST /tasks/{task_id}/plan` to explicitly rebuild and overwrite the saved plan
- Render the saved plan on Task Detail as a compact read-only card

Rationale:

- It matches the architectural direction in Phase 00 and the minimal data-model preference in Phase 05
- It keeps the change isolated from `job_worker.py`, queue handling, approval gates, and browser execution
- It makes workflow planning visible to users and reviewers immediately
- It avoids premature complexity such as plan versioning or a planner-controlled runtime

## Data Model

### `Task.workflow_plan_json`

Add one nullable text column to `Task`:

```python
workflow_plan_json: Mapped[Optional[str]] = mapped_column(Text)
```

Add a safe property:

```python
workflow_plan: dict[str, object]
```

Behavior:

- Getter returns `{}` only when the JSON field is empty or null
- Getter raises `ValueError` when `workflow_plan_json` is present but malformed
- Setter serializes with stable key ordering
- The persisted shape is the serialized `WorkflowPlan`

### SQLite Compatibility

Extend the existing migration-like helper in `backend/app/database.py` so older SQLite databases automatically receive:

- `workflow_plan_json TEXT`

This should be added to the existing task workflow column helper rather than creating a new migration system.

## Plan Shape

The saved plan shape is:

```json
{
  "workflow_type": "form_fill",
  "goal": "Fill this internship application using my student profile.",
  "steps": [
    {
      "step_id": "open_url",
      "tool": "open_url",
      "reason": "Open the target page.",
      "requires_approval": false,
      "status": "PENDING"
    }
  ]
}
```

Notes:

- `status` is descriptive plan metadata in this phase, not a runtime step engine state
- Step order must be preserved exactly as produced by the planner
- `goal` is user-facing and should come from task context

## Tool Registry

Create `backend/app/services/tool_registry.py`.

### Dataclass

```python
@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    risk_level: str
    requires_approval: bool
    implemented: bool
```

### Registry Contents

The initial registry should include these tool names:

- `open_url`
- `extract_dom`
- `extract_form`
- `map_fields`
- `request_human_approval`
- `fill_field`
- `fill_form`
- `click_element`
- `verify_fields`
- `capture_screenshot`
- `submit_form`

### Rules

- Unknown tool name raises `ValueError`
- Unimplemented tools remain visible in `list_tools()` so the architecture is inspectable
- `submit_form.requires_approval = True`
- `click_element.requires_approval = True`
- `fill_field` is medium risk
- The registry is metadata only in this phase; it does not execute tools

### Helper Functions

Add:

```python
def list_tools(include_unimplemented: bool = True) -> list[ToolDefinition]:
    ...

def get_tool(name: str) -> ToolDefinition | None:
    ...

def require_tool(name: str) -> ToolDefinition:
    ...
```

## Planner Service

Create `backend/app/services/planner_service.py`.

### Dataclasses

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

### Supported Planner Behavior

Only `form_fill` is supported in this phase.

`build_form_fill_plan(goal=...)` should deterministically produce these steps in order:

1. `open_url` via `open_url`
2. `extract_form` via `extract_form`
3. `map_fields` via `map_fields`
4. `review_mapping` via `request_human_approval`
5. `fill_form` via `fill_form`
6. `verify_fields` via `verify_fields`
7. `submit_form` via `submit_form`

Step semantics:

- `review_mapping` is represented explicitly as a human approval step in the plan even though the runtime still uses the existing Review Mapping page
- `submit_form` must be marked `requires_approval=True`
- Every planned tool must exist in the local tool registry

### Helper Functions

Add:

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

Rules:

- `build_plan()` raises `ValueError` for unsupported workflow types
- `plan_to_dict()` must produce stable JSON-ready output
- `save_plan()` overwrites the saved task plan in-place

## Goal Resolution

When automatically creating a default plan during `POST /tasks`, the planner goal should be resolved using:

1. `task.description` when present and non-empty
2. Otherwise a deterministic fallback derived from the task URL, such as:
   - `"Complete the form workflow for https://example.com/form."`

This avoids hidden LLM behavior while still giving each plan a meaningful goal string.

## API Contract

To avoid URL ambiguity, Phase 05 plan endpoints should live under the existing `/tasks` prefix. The simplest implementation is to add them directly to `backend/app/routers/tasks.py`.

### `GET /tasks/{task_id}/plan`

Behavior:

- Return the saved workflow plan for the task
- Return `404` if the task does not exist
- Return `404` if the task exists but has no saved plan
- Return `500` if a saved `workflow_plan_json` exists but cannot be parsed
- Do not silently generate a plan

Recommended missing-plan error:

```json
{
  "detail": "Workflow plan not found"
}
```

### `POST /tasks/{task_id}/plan`

Behavior:

- Rebuild the plan for the task using the request goal
- Overwrite any existing saved plan
- Return the saved plan
- Allow explicit overwrite even when the previous saved JSON was malformed

Request body:

```json
{
  "goal": "Fill this internship application using my student profile."
}
```

This endpoint is intentionally a replace operation, not a merge operation.

## Task Creation Integration

`POST /tasks` should now do three things after validation:

1. Create the task record
2. Build the deterministic default plan for `task.workflow_type`
3. Persist that plan to `task.workflow_plan_json`

This write should happen synchronously so Task Detail can read the saved plan immediately on first load.

Important boundaries:

- The default plan is metadata, not execution
- Existing automatic `create -> analyze -> map` frontend behavior remains unchanged
- Planner failure should fail task creation only if the selected enabled workflow type cannot be planned deterministically

Because only `form_fill` is enabled in this phase, this is acceptable and predictable.

## Planning Trace

If Phase 02 tracing exists, add a planning span during default plan creation and explicit rebuild:

- `phase = planning`
- `name = planning.build_plan`

Suggested span contents:

- Input:
  - `workflow_type`
  - `goal`
- Output:
  - `step_count`
  - `step_ids`

Trace writes must remain best-effort:

- If planning span persistence fails, task creation and plan rebuild must still succeed

## Schemas

Add to `backend/app/schemas.py`:

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

No plan editing schema is needed in this phase beyond replacing the whole plan via POST.

## Frontend Changes

### API Layer

Update `frontend/src/api.js`:

- `getTaskPlan(taskId)`
- `createTaskPlan(taskId, goal)`

`createTaskPlan` should POST a goal and return the replaced plan.

### Task Detail

Task Detail should:

- Fetch the saved plan with the rest of the task detail data
- Treat only `error.status === 404` as “no plan available”
- Surface non-404 plan fetch failures through the normal error UI instead of swallowing them
- Render a compact read-only `Workflow Plan` card

The card should show:

- plan goal
- ordered steps
- tool name for each step
- a small approval marker for steps with `requires_approval=true`

This card is informational only. It does not add any edit, retry, or execute controls in this phase.

## Execution Boundaries

This phase must not change runtime ownership:

- `tasks.py` remains the orchestrator for route-driven actions
- `job_worker.py` remains the executor for async jobs
- `browser_executor.py` remains the only browser automation surface
- The planner does not dispatch tools
- The tool registry does not expose a public execute-by-name interface

This keeps Phase 05 architectural while avoiding a premature partial runtime rewrite.

## Error Handling

- Unknown workflow type in planner: `ValueError`, converted to `400` or internal creation failure as appropriate
- Unknown tool in registry validation: `ValueError`
- Missing task on plan endpoints: `404`
- Missing plan on `GET /tasks/{id}/plan`: `404`
- Malformed saved plan on `GET /tasks/{id}/plan`: `500`
- Trace persistence errors: logged/best-effort only

## Test Plan

### Backend

Add `backend/tests/test_tool_registry.py`:

- known tool is returned
- unknown tool raises
- `submit_form` requires approval
- unimplemented tools are listed when requested

Add `backend/tests/test_planner_service.py`:

- `form_fill` plan contains the expected step ids in order
- every planned tool exists in registry
- `submit_form` step requires approval
- unsupported workflow type raises
- `plan_to_dict()` output is stable

Add `backend/tests/test_workflow_plan_endpoint.py`:

- creating a task stores the default plan
- `GET /tasks/{id}/plan` returns the saved plan
- `GET /tasks/{id}/plan` returns `404` when plan is missing
- `GET /tasks/{id}/plan` returns `500` when saved plan JSON is malformed
- `POST /tasks/{id}/plan` rebuilds and replaces the saved plan

Update task-creation tests as needed to assert the default saved plan exists.

### Frontend

Use only the existing lightweight Node test setup.

Add a small helper test, for example `frontend/src/workflowPlanPresentation.test.js`, covering:

- approval marker presentation
- step ordering preserved as provided
- compact label behavior if a presentation helper is introduced

Do not add a new test framework and do not add heavy component tests in this phase.

## Risks & Mitigations

- Risk: plan metadata is confused with executable runtime state
  - Mitigation: keep the plan card read-only, keep worker and routes unchanged, and keep step `status` descriptive only
- Risk: future non-`form_fill` workflow types appear plannable but are not executable
  - Mitigation: only `form_fill` is enabled, and planner support is explicitly limited in code and tests
- Risk: task creation grows too coupled to planner internals
  - Mitigation: isolate plan generation in `planner_service.py` and keep `POST /tasks` limited to “build and save”
- Risk: trace failures interfere with task creation
  - Mitigation: reuse best-effort planning span writes only

## Acceptance Criteria

- Every newly created `form_fill` task has a saved deterministic workflow plan
- `GET /tasks/{id}/plan` returns only persisted plans and returns `404` when absent
- `GET /tasks/{id}/plan` fails loudly for malformed saved JSON instead of treating it as “no plan”
- `POST /tasks/{id}/plan` replaces the saved plan
- Every planned step references a known tool from the local registry
- Task Detail can display a compact read-only workflow plan
- Existing analyze/map/fill/submit behavior still works without planner-driven execution
