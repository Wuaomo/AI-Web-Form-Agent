# Phase 4 Benchmark Regression Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing benchmark suite into an engineering governance harness that detects quality regressions, tracks workflow latency, compares cache behavior, and supports stress testing.

**Architecture:** Extend benchmark runs with baseline comparison, per-metric deltas, execution duration, stress modes, and copyable reports. Keep local HTML fixtures as the source of truth.

**Tech Stack:** Python, FastAPI, SQLAlchemy, SQLite, pytest, React, Vite, Node test runner, Playwright.

## Global Constraints

- Benchmarks must be reproducible locally.
- Do not depend on external websites for benchmark correctness.
- LLM benchmark mode must still fail gracefully when provider credentials are missing.
- All benchmark labels and reports must be English.

---

## File Structure

- Modify: `backend/app/models.py`
- Modify: `backend/app/services/benchmark_runner.py`
- Create: `backend/app/services/benchmark_report_service.py`
- Modify: `backend/app/routers/benchmarks.py`
- Modify: `frontend/src/benchmarkPresentation.js`
- Modify: `frontend/src/pages/Benchmarks.jsx`
- Add/modify benchmark tests.

---

### Task 1: Extend Benchmark Run Persistence

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/tests/test_database_migrations.py`

**Fields To Add To `BenchmarkRun`:**

```text
baseline_run_id: int | None
duration_ms: int
regression_count: int
improvement_count: int
mode_detail: str | None
```

**Steps:**
- [ ] Write database test creating benchmark run with baseline id and duration.
- [ ] Add model fields with safe defaults.
- [ ] Add fields to `BenchmarkRunResponse`.
- [ ] Run: `cd backend; pytest tests/test_database_migrations.py -v`

**Acceptance Criteria:**
- Existing benchmark run listing still works.
- New runs can reference a baseline run.

---

### Task 2: Add Benchmark Comparison Service

**Files:**
- Create: `backend/app/services/benchmark_comparison_service.py`
- Create: `backend/tests/test_benchmark_comparison_service.py`

**Interfaces:**

```python
def compare_summary_metrics(current: dict[str, float], baseline: dict[str, float], tolerance: float = 0.001) -> dict[str, dict[str, float | str]]:
    """Compare metric dictionaries and classify each metric."""
```

**Classification Values:**

```text
improved
regressed
unchanged
new
missing
```

**Tests:**
- [ ] Higher accuracy metric is `improved`.
- [ ] Lower accuracy metric is `regressed`.
- [ ] Difference below tolerance is `unchanged`.
- [ ] Missing baseline metric is `new`.
- [ ] Missing current metric is `missing`.
- [ ] Run: `cd backend; pytest tests/test_benchmark_comparison_service.py -v`

**Acceptance Criteria:**
- Regression logic is deterministic and independent of the router.

---

### Task 3: Record Benchmark Duration And Baseline Delta

**Files:**
- Modify: `backend/app/services/benchmark_runner.py`
- Modify: `backend/tests/test_benchmark_runner.py`

**Behavior:**
- [ ] Measure total benchmark run duration in milliseconds.
- [ ] When baseline is provided, compute regression and improvement counts.
- [ ] Store comparison results in case result failures or an added summary field if schema is extended.
- [ ] Do not treat `llm_fallback_count` like an accuracy metric; lower is better for count-like metrics.

**Tests:**
- [ ] Run duration is positive.
- [ ] Baseline comparison counts one regression and one improvement.
- [ ] Count metric direction is handled correctly.
- [ ] Run: `cd backend; pytest tests/test_benchmark_runner.py -v`

**Acceptance Criteria:**
- Benchmark runs can be compared over time.

---

### Task 4: Add Stress Benchmark Mode

**Files:**
- Modify: `backend/app/services/benchmark_runner.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/tests/test_benchmark_runner.py`

**Modes:**

```text
standard
cache_cold
cache_warm
concurrent
```

**Behavior:**
- [ ] `standard` keeps current behavior.
- [ ] `cache_cold` clears app-level benchmark cache before running.
- [ ] `cache_warm` runs each case twice and scores the second run for cache behavior.
- [ ] `concurrent` runs local cases with bounded concurrency if safe; if not safe with current Playwright sync API, implement as queued simulation and label it clearly.

**Tests:**
- [ ] Request schema accepts stress mode.
- [ ] Unknown stress mode is rejected.
- [ ] Cache warm mode produces cache-related metrics.
- [ ] Run: `cd backend; pytest tests/test_benchmark_runner.py -v`

**Acceptance Criteria:**
- Benchmark harness can test normal and repeated-run behavior.

---

### Task 5: Add Workflow Performance Metrics

**Files:**
- Modify: `backend/app/services/benchmark_runner.py`
- Modify: `frontend/src/benchmarkPresentation.js`
- Modify tests.

**Metrics To Add:**

```text
average_case_duration_ms
p95_case_duration_ms
llm_cache_hit_rate
retry_success_rate
failure_rate
```

**Tests:**
- [ ] Metric list includes new performance metrics.
- [ ] Missing values render as `N/A`.
- [ ] Milliseconds render as `ms` or `s`.
- [ ] Run: `cd backend; pytest tests/test_benchmark_runner.py -v`
- [ ] Run: `cd frontend; npm test -- benchmarkPresentation.test.js`

**Acceptance Criteria:**
- Benchmarks show both quality and performance.

---

### Task 6: Create Markdown Benchmark Report Service

**Files:**
- Create: `backend/app/services/benchmark_report_service.py`
- Create: `backend/tests/test_benchmark_report_service.py`
- Modify: `backend/app/routers/benchmarks.py`

**Interface:**

```python
def build_benchmark_markdown_report(run: BenchmarkRun) -> str:
    """Return a copyable Markdown report for one benchmark run."""
```

**Report Sections:**
- [ ] Run summary
- [ ] Mode/provider/stress mode
- [ ] Summary metrics
- [ ] Regression summary
- [ ] Failed cases
- [ ] Top failure reasons

**Endpoint:**

```text
GET /benchmarks/runs/{run_id}/report
```

**Tests:**
- [ ] Report includes run id.
- [ ] Report includes failed case title.
- [ ] Missing run returns `404`.
- [ ] Run: `cd backend; pytest tests/test_benchmark_report_service.py tests/test_benchmark_endpoint.py -v`

**Acceptance Criteria:**
- Benchmark results can be pasted into README, PR notes, or resume evidence.

---

### Task 7: Update Benchmarks UI

**Files:**
- Modify: `frontend/src/pages/Benchmarks.jsx`
- Modify: `frontend/src/benchmarkPresentation.js`
- Modify: `frontend/src/benchmarkPresentation.test.js`
- Modify: `frontend/src/styles.css`

**UI Behavior:**
- [ ] Show current run vs baseline.
- [ ] Show regression/improvement counts.
- [ ] Show duration.
- [ ] Failed and regressed cases appear before passing cases.
- [ ] Add button: `Copy Markdown Report`.
- [ ] Keep provider setup warning for LLM mode.

**Tests:**
- [ ] Helper sorts regressed/failed cases first.
- [ ] Helper formats duration.
- [ ] Helper formats regression status.
- [ ] Run: `cd frontend; npm test -- benchmarkPresentation.test.js`

**Acceptance Criteria:**
- Benchmark page supports regression review, not just one-off scoring.

---

### Task 8: End-To-End Verification

**Commands:**
- [ ] Run: `cd backend; pytest -v`
- [ ] Run: `cd frontend; npm run lint`
- [ ] Run: `cd frontend; npm test`
- [ ] Run: `cd frontend; npm run build`

**Manual Verification:**
- [ ] Run a baseline benchmark.
- [ ] Run a second benchmark against the baseline.
- [ ] Confirm regression/improvement counts render.
- [ ] Copy Markdown report and verify it contains summary and failures.

**Done Criteria:**
- Benchmark harness supports quality, performance, cache, and regression governance.

