# Benchmark Runner And Action Trace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reproducible benchmark metrics plus admin-only browser action traces without exposing trace details to normal users.

**Architecture:** Benchmark execution lives in a backend service that reads the existing benchmark fixtures, computes metrics, persists run/case results, and exposes a `/benchmarks` API consumed by a frontend panel. Action tracing is a separate persistence path from user-facing `ActionLog`, written by browser execution and exposed only through `/admin` APIs guarded by an optional `ADMIN_API_TOKEN`.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite JSON-in-Text fields, Playwright, React, Vite, node:test.

## Global Constraints

- Keep the project MVP-focused.
- Do not add login or user management.
- Do not auto-submit forms without user approval.
- Keep code beginner-friendly.
- Add comments when logic is not obvious.
- Prefer small functions and simple file structure.
- Action trace is admin/developer observability and must not be shown in the normal user task UI.

---

### Task 1: Benchmark Metrics Core

**Files:**
- Create: `backend/app/services/benchmark_runner.py`
- Test: `backend/tests/test_benchmark_runner.py`

**Interfaces:**
- Produces: `load_benchmark_cases() -> list[BenchmarkCase]`, `score_case(expected: dict, actual: dict) -> dict[str, object]`, `run_benchmarks(mode: str = "rules", provider: str | None = None, db: Session | None = None) -> BenchmarkRunSummary`

- [ ] **Step 1: Write failing tests** for loading 10 cases and scoring extraction/mapping metrics.
- [ ] **Step 2: Run `pytest backend/tests/test_benchmark_runner.py -q`** and verify failures are missing module/functions.
- [ ] **Step 3: Implement benchmark case loading and deterministic metric scoring.**
- [ ] **Step 4: Run the focused tests until green.**

### Task 2: Benchmark Persistence And API

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/database.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/app/routers/benchmarks.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_benchmark_endpoint.py`

**Interfaces:**
- Consumes: `run_benchmarks(...)`
- Produces: `POST /benchmarks/run`, `GET /benchmarks/runs`, `GET /benchmarks/runs/{run_id}`

- [ ] **Step 1: Write failing endpoint tests** for creating and reading a benchmark run.
- [ ] **Step 2: Add `BenchmarkRun` and `BenchmarkCaseResult` models plus SQLite auto-migration helpers.**
- [ ] **Step 3: Add response schemas and router.**
- [ ] **Step 4: Include router in `main.py` and verify endpoint tests pass.**

### Task 3: Benchmark Frontend Panel

**Files:**
- Modify: `frontend/src/api.js`
- Create: `frontend/src/benchmarkPresentation.js`
- Create: `frontend/src/benchmarkPresentation.test.js`
- Create: `frontend/src/pages/Benchmarks.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/Layout.jsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `/benchmarks/run`, `/benchmarks/runs`, `/benchmarks/runs/{run_id}`
- Produces: `/benchmarks` page with summary cards, case table, and failure details.

- [ ] **Step 1: Write presentation tests** for percentage formatting and case summaries.
- [ ] **Step 2: Implement API helpers and presentation helpers.**
- [ ] **Step 3: Add Benchmarks page and route/navigation.**
- [ ] **Step 4: Run frontend tests, lint, and build.**

### Task 4: Admin Action Trace Backend

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/database.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/app/services/action_trace_service.py`
- Create: `backend/app/routers/admin.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/services/browser_executor.py`
- Test: `backend/tests/test_action_trace.py`
- Test: `backend/tests/test_admin_trace_endpoint.py`

**Interfaces:**
- Produces: `record_action_trace(db, task_id, phase, action, result, selector=None, field_id=None, input_value=None, error_message=None, screenshot_id=None) -> TaskActionTrace`
- Produces: `GET /admin/tasks/{task_id}/traces`

- [ ] **Step 1: Write failing service and admin endpoint tests.**
- [ ] **Step 2: Add `TaskActionTrace` model and SQLite auto-migration helper.**
- [ ] **Step 3: Implement trace service and optional `X-Admin-Token` guard.**
- [ ] **Step 4: Instrument browser fill actions with trace records.**
- [ ] **Step 5: Run backend tests until green.**

### Task 5: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run `pytest backend/tests -q`.**
- [ ] **Step 2: Run `npm test` in `frontend`.**
- [ ] **Step 3: Run `npm run lint` in `frontend`.**
- [ ] **Step 4: Run `npm run build` in `frontend`.**

