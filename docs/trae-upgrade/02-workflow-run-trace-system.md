# Phase 02 - Workflow Run Trace System

## Goal

Add a first-class workflow trace system that records every important operation in a run as queryable spans.

This should make the project feel like a professional AI workflow system: every LLM call, browser action, policy check, verification, and user approval can be inspected after the run.

## Why This Matters

AI workflow systems fail in messy ways. A trace system shows engineering maturity because it answers:

- What happened?
- In what order?
- Which step failed?
- What did the model/tool receive?
- What did it output?
- How long did it take?
- How much did it cost?
- Which screenshot or verification result proves it?

## Current Code To Read

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/main.py`
- `backend/app/routers/tasks.py`
- `backend/app/routers/admin.py`
- `backend/app/services/action_trace_service.py`
- `backend/app/services/log_service.py`
- `backend/app/services/llm_usage_service.py`
- `backend/app/services/browser_executor.py`
- `backend/app/services/checkpoint_service.py`
- `frontend/src/api.js`
- `frontend/src/pages/TaskDetail.jsx`
- `frontend/src/debugReport.js`

## Scope

Add workflow trace persistence and a read-only API. Start writing spans from the existing form-fill workflow.

## Out Of Scope

- Do not replace action logs.
- Do not delete `TaskActionTrace`.
- Do not build OpenTelemetry integration.
- Do not add external observability services.
- Do not add a complex visual trace graph yet. A simple timeline is enough.

## Data Model

Add model `WorkflowSpan` in `backend/app/models.py`.

Fields:

```python
class WorkflowSpan(Base):
    __tablename__ = "workflow_spans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    parent_span_id: Mapped[Optional[int]] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    input_json: Mapped[Optional[str]] = mapped_column(Text)
    output_json: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    screenshot_id: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
```

Use JSON text columns to match existing SQLite style.

## Constants

Add to `backend/app/workflow_constants.py`:

```python
SPAN_STATUS_STARTED = "STARTED"
SPAN_STATUS_SUCCESS = "SUCCESS"
SPAN_STATUS_FAILED = "FAILED"
SPAN_STATUS_SKIPPED = "SKIPPED"

SPAN_PHASE_PLANNING = "planning"
SPAN_PHASE_POLICY = "policy"
SPAN_PHASE_APPROVAL = "approval"
SPAN_PHASE_BROWSER = "browser"
SPAN_PHASE_EXTRACTION = "extraction"
SPAN_PHASE_MAPPING = "mapping"
SPAN_PHASE_VERIFICATION = "verification"
SPAN_PHASE_EVALUATION = "evaluation"
SPAN_PHASE_MEMORY = "memory"
```

## Service Interface

Create `backend/app/services/workflow_trace_service.py`.

Required functions:

```python
def create_span(
    db: Session,
    *,
    task_id: int,
    phase: str,
    name: str,
    status: str = SPAN_STATUS_STARTED,
    parent_span_id: int | None = None,
    input: dict[str, object] | None = None,
    output: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
    provider: str | None = None,
    model: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    estimated_cost: float = 0.0,
    latency_ms: int = 0,
    screenshot_id: int | None = None,
    error_message: str | None = None,
) -> WorkflowSpan:
    ...

def finish_span(
    db: Session,
    span: WorkflowSpan,
    *,
    status: str,
    output: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
    latency_ms: int | None = None,
    screenshot_id: int | None = None,
    error_message: str | None = None,
) -> WorkflowSpan:
    ...

def list_spans_for_task(db: Session, task_id: int) -> list[WorkflowSpan]:
    ...
```

JSON serialization must use `ensure_ascii=False`.

Invalid JSON should never be returned to the API. Add safe properties on the model:

```python
input: dict[str, object]
output: dict[str, object]
metadata: dict[str, object]
```

## Schema

Add `WorkflowSpanResponse` in `backend/app/schemas.py`:

```python
class WorkflowSpanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    parent_span_id: int | None
    phase: str
    name: str
    status: str
    input: dict[str, object] = Field(default_factory=dict)
    output: dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)
    provider: str | None
    model: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    latency_ms: int
    screenshot_id: int | None
    error_message: str | None
    created_at: datetime
```

## API Contract

Create `backend/app/routers/traces.py`.

### GET `/tasks/{task_id}/trace`

Response:

```json
[
  {
    "id": 1,
    "task_id": 42,
    "parent_span_id": null,
    "phase": "extraction",
    "name": "extract_form",
    "status": "SUCCESS",
    "input": {"url": "file:///example.html"},
    "output": {"field_count": 12},
    "metadata": {},
    "provider": null,
    "model": null,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "estimated_cost": 0.0,
    "latency_ms": 317,
    "screenshot_id": null,
    "error_message": null,
    "created_at": "2026-07-05T00:00:00Z"
  }
]
```

Register the router in `backend/app/main.py`.

## Where To Write Spans

Add spans in existing code paths:

### Analyze

In `analyze_task()`:

- create started span: phase `extraction`, name `extract_form`
- on success output: `field_count`, `login_required`, `cache_hit`
- on failure status failed with error message

### Map Fields

In `map_task_fields()`:

- started span: phase `mapping`, name `map_fields_rules` or `map_fields_llm`
- output: field count, mode, provider, mapped count
- metadata: fallback used when available

If LLM usage data is available, include provider/model/tokens/cost.

### Confirm Mapping

Span:

- phase `approval`
- name `confirm_mapping`
- output: profile update count, skipped count

### Fill

Span:

- phase `browser`
- name `fill_form`
- output: filled count, verification summary
- screenshot id if known

### Confirm Submit

Span:

- phase `browser`
- name `submit_form`
- output: final status

## Frontend API

Update `frontend/src/api.js`:

```js
getTaskTrace: (taskId) => request(`/tasks/${taskId}/trace`)
```

## Frontend Presentation

Create `frontend/src/workflowTracePresentation.js`.

Required functions:

```js
export function phaseLabel(phase) { ... }
export function spanStatusLabel(status) { ... }
export function summarizeSpan(span) { ... }
export function sortSpans(spans) { ... }
```

Expected labels:

- `extraction` -> `Extraction`
- `mapping` -> `Mapping`
- `approval` -> `Approval`
- `browser` -> `Browser`
- `verification` -> `Verification`
- unknown -> original string

## Frontend UI

In `TaskDetail.jsx`:

- fetch `api.getTaskTrace(taskId).catch(() => [])`
- display a `Workflow Trace` card
- render spans newest or chronological; chronological preferred
- each row shows:
  - phase
  - name
  - status
  - latency
  - provider/model if present
  - error if present

Keep the UI compact.

## Tests Required

### Backend

Create `backend/tests/test_workflow_trace_service.py`:

- create span with dict input/output/metadata.
- response properties return parsed JSON.
- invalid JSON returns empty dict.
- finish span updates status/output/latency/error.

Create `backend/tests/test_workflow_trace_endpoint.py`:

- GET trace for missing task returns 404.
- GET trace for task returns ordered spans.

### Frontend

Create `frontend/src/workflowTracePresentation.test.js`:

- phase label fallback works.
- status label fallback works.
- sort order is chronological by created_at then id.
- summarize includes provider/model when present.

## Acceptance Criteria

- Trace spans are persisted in SQLite.
- `/tasks/{task_id}/trace` returns spans.
- Task Detail shows a compact trace timeline.
- Existing logs and screenshots still work.
- Existing tests pass.
- No external observability dependency is added.

## Implementation Order

1. Add `WorkflowSpan` model and safe JSON properties.
2. Add database migration helper for `workflow_spans`.
3. Add constants.
4. Add trace service.
5. Add schemas and router.
6. Register router.
7. Add trace writes to main task route operations.
8. Add frontend API and presentation helper.
9. Render trace card in Task Detail.
10. Add tests.

## Trae Prompt

Implement Phase 02. Add a workflow span trace system with SQLite persistence, service helpers, a read-only `/tasks/{task_id}/trace` endpoint, trace writes in existing analyze/map/confirm/fill/submit operations, and a compact frontend trace card. Do not remove existing logs or action traces. Keep the implementation dependency-free.
