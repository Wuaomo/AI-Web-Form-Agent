# Phase 7 Optional Go Metrics Sidecar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight Go sidecar for task/job metrics and worker heartbeat aggregation without rewriting the Python FastAPI backend.

**Architecture:** FastAPI remains the source of truth for tasks, jobs, browser execution, and LLM mapping. The Go sidecar receives event notifications, aggregates operational metrics in memory, and exposes `/health` and `/metrics` endpoints. The sidecar is optional and must not break local development if it is not running.

**Tech Stack:** Go, net/http, Python FastAPI, pytest for Python client behavior, Go test for sidecar.

## Global Constraints

- Do not rewrite Playwright logic in Go.
- Do not move LLM mapping to Go.
- Do not introduce split database ownership.
- The Python app must continue working when the Go sidecar is unavailable.
- All API responses and logs must use English labels.

---

## File Structure

- Create: `sidecars/metrics-go/go.mod`
- Create: `sidecars/metrics-go/main.go`
- Create: `sidecars/metrics-go/metrics/aggregator.go`
- Create: `sidecars/metrics-go/metrics/aggregator_test.go`
- Create: `backend/app/services/metrics_sidecar_client.py`
- Create: `backend/tests/test_metrics_sidecar_client.py`
- Modify job/checkpoint services to emit optional events.
- Modify README or docs only after sidecar works locally.

---

### Task 1: Create Go Sidecar Skeleton

**Files:**
- Create: `sidecars/metrics-go/go.mod`
- Create: `sidecars/metrics-go/main.go`

**Endpoints:**

```text
GET /health
GET /metrics
POST /events
```

**Steps:**
- [ ] Create Go module named `ai-web-form-agent-metrics`.
- [ ] Implement `/health` returning `{"status":"ok"}`.
- [ ] Implement `/metrics` returning an initially empty JSON metrics object.
- [ ] Implement `/events` accepting JSON and returning `202`.
- [ ] Run: `cd sidecars/metrics-go; go test ./...`
- [ ] Run sidecar manually with `go run .`.

**Acceptance Criteria:**
- Go sidecar starts locally and answers health checks.

---

### Task 2: Implement Metrics Aggregator

**Files:**
- Create: `sidecars/metrics-go/metrics/aggregator.go`
- Create: `sidecars/metrics-go/metrics/aggregator_test.go`
- Modify: `sidecars/metrics-go/main.go`

**Event Shape:**

```json
{
  "event_type": "job_succeeded",
  "task_id": 55,
  "job_id": 101,
  "job_type": "MAP_FIELDS",
  "duration_ms": 1200,
  "worker_id": "worker-local-1",
  "created_at": "2026-07-03T10:00:00Z"
}
```

**Metrics To Aggregate:**
- [ ] Total events.
- [ ] Jobs by status.
- [ ] Jobs by type.
- [ ] Average duration by job type.
- [ ] Worker last seen timestamp.
- [ ] Retry count.

**Tests:**
- [ ] Recording one event increments total events.
- [ ] Job type counts increment.
- [ ] Average duration is computed correctly.
- [ ] Worker last seen is updated.
- [ ] Run: `cd sidecars/metrics-go; go test ./...`

**Acceptance Criteria:**
- Sidecar exposes useful operational metrics from events.

---

### Task 3: Add Python Sidecar Client

**Files:**
- Create: `backend/app/services/metrics_sidecar_client.py`
- Create: `backend/tests/test_metrics_sidecar_client.py`
- Modify: `backend/app/config.py`

**Interfaces:**

```python
def emit_metrics_event(event: dict[str, object]) -> bool:
    """Send an operational event to the optional Go metrics sidecar."""
```

**Rules:**
- [ ] Use environment variable `METRICS_SIDECAR_URL`.
- [ ] If URL is empty, return `False` without error.
- [ ] If sidecar request fails, log warning and return `False`.
- [ ] Do not block task execution on sidecar failure.
- [ ] Use short timeout such as 500ms.

**Tests:**
- [ ] No URL returns `False`.
- [ ] Failed request returns `False`.
- [ ] Successful mocked request returns `True`.
- [ ] Run: `cd backend; pytest tests/test_metrics_sidecar_client.py -v`

**Acceptance Criteria:**
- Python app can emit events without depending on sidecar availability.

---

### Task 4: Emit Job And Workflow Events

**Files:**
- Modify: `backend/app/services/job_queue.py`
- Modify: `backend/app/services/job_worker.py`
- Modify: `backend/app/services/checkpoint_service.py`
- Modify: `backend/tests/test_metrics_sidecar_client.py` or create `backend/tests/test_metrics_events.py`

**Events:**

```text
job_enqueued
job_started
job_succeeded
job_failed
job_retry_scheduled
checkpoint_written
```

**Rules:**
- [ ] Events must include task id when available.
- [ ] Events must include job id when available.
- [ ] Events must include duration when known.
- [ ] Event emission failure must not fail the main workflow.

**Tests:**
- [ ] Successful job emits started and succeeded events.
- [ ] Failed job emits failed event.
- [ ] Checkpoint write emits checkpoint event.
- [ ] Sidecar failure does not fail job.
- [ ] Run: `cd backend; pytest tests/test_metrics_events.py -v`

**Acceptance Criteria:**
- Operational events are emitted at important workflow boundaries.

---

### Task 5: Add Local Run Documentation

**Files:**
- Create: `docs/go-metrics-sidecar.md`
- Modify: `README.md`

**Content:**
- [ ] Explain that sidecar is optional.
- [ ] Include startup command:

```powershell
cd sidecars/metrics-go
go run .
```

- [ ] Include backend env var:

```powershell
$env:METRICS_SIDECAR_URL="http://localhost:9100"
```

- [ ] Explain metrics available.
- [ ] Explain that FastAPI remains source of truth.

**Acceptance Criteria:**
- Reviewer can run the sidecar without guessing.

---

### Task 6: End-To-End Verification

**Commands:**
- [ ] Run: `cd sidecars/metrics-go; go test ./...`
- [ ] Run: `cd backend; pytest -v`
- [ ] Run: `cd frontend; npm run lint`
- [ ] Run: `cd frontend; npm test`
- [ ] Run: `cd frontend; npm run build`

**Manual Verification:**
- [ ] Start Go sidecar.
- [ ] Start FastAPI with `METRICS_SIDECAR_URL`.
- [ ] Run one queued job.
- [ ] Open `http://localhost:9100/metrics`.
- [ ] Confirm job event counts increased.
- [ ] Stop sidecar and confirm FastAPI still works.

**Done Criteria:**
- Go sidecar demonstrates backend infrastructure awareness without destabilizing the core app.

