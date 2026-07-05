# Phase 05 Planner And Tool Protocol Implementation Plan

> **For agentic workers:** Execute this plan in order. Keep the planner deterministic, metadata-only, and isolated from runtime execution. Track progress task-by-task and do not expand scope beyond the approved Phase 05 boundaries.

**Goal:** Persist an inspectable deterministic `form_fill` workflow plan on each task, expose `GET/POST /tasks/{id}/plan`, and render a compact read-only Workflow Plan card on Task Detail without changing the existing execution engine.

**Architecture:** Extend `Task` with `workflow_plan_json`, add a metadata-only local tool registry and deterministic planner service, generate/save a default plan during task creation, add explicit plan read/rebuild endpoints under `/tasks`, and expose the saved plan in the frontend as informational UI only.

**Tech Stack:** Python, FastAPI, SQLAlchemy, SQLite, pytest, React, Vite, Node test runner.

## Global Constraints

- Do not introduce a planner LLM.
- Do not add LangChain, LangGraph, or any external agent framework.
- Do not create a `workflow_plans` table.
- Do not add plan version history.
- Do not add editable plan UI.
- Do not refactor `job_worker.py`, job queue handling, or `browser_executor.py`.
- Planner output is deterministic and supports `form_fill` only in this phase.
- `tool_registry.py` is metadata only and must not execute tools by name.
- `GET /tasks/{id}/plan` returns only persisted plans and must not generate one implicitly.
- Frontend may treat only `404` from `getTaskPlan` as “no plan”; any other error must surface through normal error handling.

---

## File Structure

- Modify: `backend/app/models.py`
- Modify: `backend/app/database.py`
- Create: `backend/app/services/tool_registry.py`
- Create: `backend/app/services/planner_service.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routers/tasks.py`
- Modify: `frontend/src/api.js`
- Create: `frontend/src/workflowPlanPresentation.js`
- Create: `frontend/src/workflowPlanPresentation.test.js`
- Modify: `frontend/src/pages/TaskDetail.jsx`
- Add backend and frontend tests

---

### Task 1: Persist Workflow Plan On Task

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/database.py`
- Modify: `backend/tests/test_database_migrations.py`

**Behavior:**
- [ ] Add `workflow_plan_json` to `Task`.
- [ ] Add `Task.workflow_plan` property.
- [ ] Return `{}` only when `workflow_plan_json` is empty or null.
- [ ] Raise `ValueError` when `workflow_plan_json` is present but malformed.
- [ ] Serialize saved plan JSON with stable key ordering.
- [ ] Extend SQLite helper to add `workflow_plan_json TEXT` to legacy `tasks`.

**Tests:**
- [ ] Add migration coverage for `workflow_plan_json`.
- [ ] Add model coverage proving valid JSON round-trips.
- [ ] Add model coverage proving malformed JSON raises `ValueError`.

**Acceptance Criteria:**
- Saved plan metadata lives directly on `Task`.
- Older SQLite databases receive the new column automatically.

---

### Task 2: Add Metadata-Only Tool Registry

**Files:**
- Create: `backend/app/services/tool_registry.py`
- Create: `backend/tests/test_tool_registry.py`

**Behavior:**
- [ ] Define frozen `ToolDefinition` dataclass.
- [ ] Register all approved tool names.
- [ ] Keep unimplemented tools visible to registry listing.
- [ ] Mark `submit_form.requires_approval = True`.
- [ ] Mark `click_element.requires_approval = True`.
- [ ] Keep `fill_field` at medium risk.
- [ ] Raise `ValueError` for unknown tool lookup in `require_tool`.

**Tests:**
- [ ] Known tool lookup succeeds.
- [ ] Unknown tool lookup raises.
- [ ] `submit_form` requires approval.
- [ ] Unimplemented tools remain visible in `list_tools()`.

**Acceptance Criteria:**
- The registry exposes inspectable tool metadata only.

---

### Task 3: Add Deterministic Planner Service

**Files:**
- Create: `backend/app/services/planner_service.py`
- Create: `backend/tests/test_planner_service.py`

**Behavior:**
- [ ] Define `PlannedStep` and `WorkflowPlan` dataclasses.
- [ ] Implement deterministic `build_form_fill_plan(goal=...)`.
- [ ] Implement `build_plan(workflow_type, goal)` for `form_fill` only.
- [ ] Validate that every planned tool exists in the local registry.
- [ ] Implement stable `plan_to_dict(plan)`.
- [ ] Implement `save_plan(db, task, plan)` as in-place overwrite.
- [ ] Implement goal resolution helper for task creation fallback.

**Tests:**
- [ ] `form_fill` plan uses the approved step order.
- [ ] Every planned tool exists in the registry.
- [ ] `submit_form` step requires approval.
- [ ] Unsupported workflow type raises `ValueError`.
- [ ] `plan_to_dict()` output is stable.

**Acceptance Criteria:**
- Planner output is deterministic, inspectable, and bounded to `form_fill`.

---

### Task 4: Integrate Plan Creation And Plan Endpoints

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/tests/test_workflow_plan_endpoint.py`
- Update: `backend/tests/test_task_mapping_endpoint.py`

**Behavior:**
- [ ] Add `WorkflowPlanRequest`, `PlannedStepResponse`, and `WorkflowPlanResponse`.
- [ ] During `POST /tasks`, build and save the default plan synchronously after task creation.
- [ ] Keep the current automatic `create -> analyze -> map` frontend chain unchanged.
- [ ] Add best-effort planning trace span for default creation and explicit rebuild.
- [ ] Add `GET /tasks/{task_id}/plan` under the `/tasks` router.
- [ ] Return `404` when the task is missing.
- [ ] Return `404` when the task exists but has no saved plan.
- [ ] Return `500` when `workflow_plan_json` is present but malformed.
- [ ] Add `POST /tasks/{task_id}/plan` to rebuild and overwrite the saved plan.
- [ ] Allow explicit overwrite even if the previous saved JSON is malformed.

**Tests:**
- [ ] Creating a task stores the default plan.
- [ ] `GET /tasks/{id}/plan` returns the saved plan.
- [ ] `GET /tasks/{id}/plan` returns `404` when the plan is missing.
- [ ] `GET /tasks/{id}/plan` returns `500` for malformed saved JSON.
- [ ] `POST /tasks/{id}/plan` rebuilds and replaces the saved plan.
- [ ] Update existing task-creation tests to assert the default saved plan exists.

**Acceptance Criteria:**
- Task creation persists a deterministic plan immediately.
- Plan endpoints live under `/tasks`, not `/workflows`.

---

### Task 5: Expose Plan In Frontend

**Files:**
- Modify: `frontend/src/api.js`
- Create: `frontend/src/workflowPlanPresentation.js`
- Create: `frontend/src/workflowPlanPresentation.test.js`
- Modify: `frontend/src/pages/TaskDetail.jsx`

**Behavior:**
- [ ] Add `api.getTaskPlan(taskId)`.
- [ ] Add `api.createTaskPlan(taskId, goal)`.
- [ ] Introduce a small presentation helper for compact plan rendering.
- [ ] Fetch the saved plan on Task Detail with existing task data loading.
- [ ] Treat only `error.status === 404` as “no plan”.
- [ ] Surface non-404 plan fetch failures through the normal error UI.
- [ ] Render a read-only `Workflow Plan` card showing goal, ordered steps, tool names, and approval markers.
- [ ] Do not add execute, edit, retry, or rebuild controls.

**Tests:**
- [ ] Add lightweight helper coverage for approval marker presentation.
- [ ] Add lightweight helper coverage preserving provided step ordering.
- [ ] Reuse the existing Node test runner only.

**Acceptance Criteria:**
- Task Detail shows saved plan metadata without changing execution behavior.

---

### Task 6: Validate The Whole Slice

**Commands:**
- [ ] Run: `python -m pytest backend/tests/test_tool_registry.py backend/tests/test_planner_service.py backend/tests/test_workflow_plan_endpoint.py backend/tests/test_database_migrations.py backend/tests/test_task_mapping_endpoint.py`
- [ ] Run: `npm test -- workflowPlanPresentation.test.js api.test.js`
- [ ] Run diagnostics on recently edited files and fix any introduced issues.

**Done Criteria:**
- Backend and frontend tests covering Phase 05 pass.
- Planner remains deterministic and metadata-only.
- Worker, queue, approval, browser executor, and runtime orchestration remain unchanged.
