# Go Metrics Sidecar (Optional)

The Go metrics sidecar is an **optional** lightweight service that aggregates
operational metrics for tasks, jobs, and worker heartbeats. The FastAPI backend
remains the source of truth for all task, job, browser execution, and LLM
mapping state. The sidecar only receives event notifications and exposes
read-only metrics endpoints.

## When To Use It

- You want real-time operational dashboards without querying the SQLite database.
- You want to monitor worker health and job throughput during async job runs.
- You want average duration metrics per job type for performance tuning.

The sidecar is **not required** for local development. The Python backend works
normally without it.

## Architecture

```text
FastAPI backend
  -> emits events via metrics_sidecar_client.emit_metrics_event()
  -> Go sidecar receives POST /events
  -> Go sidecar aggregates in memory
  -> Go sidecar exposes GET /metrics and GET /health
```

The FastAPI backend never depends on the sidecar. If the sidecar is unavailable,
event emission silently fails and the backend continues normally.

## Startup

### 1. Start the Go sidecar

```powershell
cd sidecars/metrics-go
go run .
```

The sidecar listens on port `9100` by default.

Health check:

```text
http://localhost:9100/health
```

### 2. Configure the backend

Set the environment variable before starting the FastAPI backend:

```powershell
$env:METRICS_SIDECAR_URL="http://localhost:9100"
```

If this variable is empty or not set, the backend skips event emission silently.

### 3. Start the FastAPI backend

```powershell
cd backend
uvicorn app.main:app --reload
```

## Endpoints

### GET /health

Returns `{"status":"ok"}`.

### GET /metrics

Returns a JSON object with aggregated metrics:

```json
{
  "total_events": 42,
  "jobs_by_status": {
    "enqueued": 10,
    "started": 10,
    "succeeded": 8,
    "failed": 1,
    "retry_scheduled": 1
  },
  "jobs_by_type": {
    "ANALYZE_FORM": 4,
    "MAP_FIELDS": 3,
    "FILL_FORM": 2,
    "RUN_BENCHMARK": 1
  },
  "avg_duration_by_job_type": {
    "MAP_FIELDS": {
      "total": 3600,
      "count": 3,
      "avg": 1200
    }
  },
  "worker_last_seen": {
    "worker-local-1": "2026-07-03T10:01:00Z"
  },
  "retry_count": 1
}
```

### POST /events

Accepts a JSON event body and returns HTTP 202 (Accepted).

Event shape:

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

## Event Types

The backend emits the following events at workflow boundaries:

| Event type           | Source               | When                              |
|----------------------|----------------------|-----------------------------------|
| `job_enqueued`       | job_queue.py         | A job is created and pending      |
| `job_started`        | job_worker.py        | A worker starts executing a job   |
| `job_succeeded`      | job_worker.py        | A job completes successfully      |
| `job_failed`         | job_worker.py        | A job fails without retry         |
| `job_retry_scheduled`| job_worker.py        | A job fails and retry is scheduled|
| `checkpoint_written` | checkpoint_service.py| A workflow checkpoint is written  |

## Metrics Aggregated

- **Total events**: Count of all received events.
- **Jobs by status**: Counts per job status (enqueued, started, succeeded, failed, retry_scheduled).
- **Jobs by type**: Counts per job type (ANALYZE_FORM, MAP_FIELDS, FILL_FORM, RUN_BENCHMARK).
- **Average duration by job type**: Total/count average duration in milliseconds.
- **Worker last seen**: Last event timestamp per worker ID.
- **Retry count**: Total retry-scheduled events.

## Source Of Truth

The FastAPI backend remains the source of truth for:

- Task state and status
- Job records and attempt history
- Browser execution results
- LLM mapping outputs
- Benchmark results

The Go sidecar only holds in-memory aggregated metrics. It does not own any
database state and does not participate in workflow decisions. Restarting the
sidecar resets all aggregated metrics to zero.

## Running Tests

Go sidecar tests:

```powershell
cd sidecars/metrics-go
go test ./...
```

Python client and event emission tests:

```powershell
cd backend
python -m pytest tests/test_metrics_sidecar_client.py tests/test_metrics_events.py -v
```
