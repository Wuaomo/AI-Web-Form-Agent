# Phase 07 - Evaluation Center (Implementation Plan)

**Goal:** Extend the existing benchmark system into an Evaluation Center with eval modes (`rules/llm/rag_llm/full_workflow`), same-config baseline deltas, frontend-only cross-run comparison, and richer Markdown reporting—without new tables or new compare APIs.

**Hard boundaries:**
- No new database tables (reuse `BenchmarkRun` + `BenchmarkCaseResult`).
- No compare API endpoint (mode comparison is frontend-only).
- Do not implement `full_workflow` execution (only validate + return a clear API error).
- Normalization must be centralized (avoid scattering `rules/rag_llm` normalization between router and runner).

## Step 1 - Extend Request Schema (Mode + Baseline)

**Files**
- Modify: `backend/app/schemas.py`
- Update tests: `backend/tests/test_benchmark_endpoint.py`

**Work**
- Extend `BenchmarkRunRequest`:
  - `mode: Literal["rules","llm","rag_llm","full_workflow"] = "rules"`
  - `baseline_run_id: int | None = None`
  - keep existing `provider/stress_mode/memory_mode`
- Ensure response models remain compatible (no response schema breaking changes).

## Step 2 - Centralize Normalization: normalize_benchmark_request()

**Files**
- Create: `backend/app/services/benchmark_request_service.py` (or similarly named service module)
- Modify: `backend/app/routers/benchmarks.py`
- Modify: `backend/app/services/benchmark_runner.py`
- Update tests: `backend/tests/test_benchmark_endpoint.py`, `backend/tests/test_benchmark_runner.py`

**Work**
- Add a small normalization helper, e.g.:
  - `normalize_benchmark_request(options: BenchmarkRunRequest) -> NormalizedBenchmarkOptions`
  - `NormalizedBenchmarkOptions` contains:
    - `eval_mode` (`rules/llm/rag_llm/full_workflow`) for storage
    - `execution_mode` (`rules` or `llm`) for `_run_case` branching
    - `provider: str | None` (already resolved for LLM providers when applicable)
    - `stress_mode`
    - `memory_mode` normalized
    - `mode_detail` string (e.g. `stress_mode=...;memory_mode=...`)
    - `baseline_run_id`
- Normalization rules (must be applied consistently before any validation/execution):
  - **rules**
    - `provider -> None` (ignore incoming provider; persist `BenchmarkRun.provider=None`)
    - `memory_mode -> "off"` (ignore incoming; persist `mode_detail` with `memory_mode=off`)
    - `execution_mode="rules"`
  - **llm**
    - provider required (validated in router), execution_mode="llm"
    - memory_mode preserved (off/on)
  - **rag_llm**
    - provider required (validated in router)
    - force `memory_mode="on"`
    - `eval_mode="rag_llm"` persisted, but `execution_mode="llm"` for runner branching
  - **full_workflow**
    - normalized output still available for consistent error messages
    - router returns `"full_workflow evaluation is not implemented yet"` without executing
- Keep provider setup validation in router (configured keys check), but use normalized provider value.

## Step 3 - Explicit Baseline Validation Before Execution

**Files**
- Modify: `backend/app/routers/benchmarks.py`
- Modify: `backend/app/services/benchmark_runner.py` (only if baseline selection logic needs refactor)
- Update tests: `backend/tests/test_benchmark_endpoint.py`, `backend/tests/test_benchmark_runner.py`

**Work**
- Enforce validation order:
  1. Normalize request (`mode/provider/stress_mode/memory_mode/mode_detail`)
  2. If `baseline_run_id` provided:
     - load baseline run (404 if missing)
     - validate compatibility (400 if incompatible):
       - same `mode` (eval mode)
       - same `provider`
       - same `mode_detail`
     - only then run the benchmark suite
  3. If `baseline_run_id` omitted:
     - run benchmark suite
     - runner picks latest compatible baseline automatically (same mode/provider/mode_detail), and persists `baseline_run_id` when found
- Keep baseline semantics strict:
  - baseline delta is only for same configuration
  - cross-mode comparisons are frontend-only

## Step 4 - Runner: Persist Eval Mode but Execute rag_llm via LLM Path

**Files**
- Modify: `backend/app/services/benchmark_runner.py`
- Update tests: `backend/tests/test_benchmark_runner.py`

**Work**
- Update `run_benchmarks(...)` signature/behavior as needed to accept:
  - `eval_mode` (persisted `BenchmarkRun.mode`)
  - `execution_mode` (branching behavior)
  - normalized `provider/memory_mode/mode_detail`
  - optional `baseline_run_id` (explicit or auto)
- Ensure:
  - `BenchmarkRun.mode` stores `rag_llm` when requested
  - LLM execution branch is used for both `llm` and `rag_llm`
  - rules branch never uses memory (because memory_mode normalized to off)
- Ensure baseline matching uses normalized `mode_detail`.

## Step 5 - Report: Load Baseline by baseline_run_id and Compute Deltas On Demand

**Files**
- Modify: `backend/app/services/benchmark_report_service.py`
- Modify: `backend/app/routers/benchmarks.py`
- Update tests: `backend/tests/test_benchmark_report_service.py`

**Work**
- Update report generation flow to satisfy “delta data source” boundary:
  - report service loads baseline run using `run.baseline_run_id` (if present)
  - delta column computed at report-build time from:
    - `current.summary_metrics`
    - `baseline.summary_metrics`
  - do not add DB columns and do not persist per-metric deltas
- Report formatting changes:
  - include Baseline line in configuration when present
  - include Delta column when baseline is present
  - keep existing failures/top-failures sections

## Step 6 - Frontend: Evaluation Center Controls + Compare Runs (No Backend Compare API)

**Files**
- Modify: `frontend/src/pages/Benchmarks.jsx`
- Modify: `frontend/src/benchmarkPresentation.js`
- Update tests: `frontend/src/benchmarkPresentation.test.js`

**Work**
- Mode selector:
  - add `rag_llm`
  - optionally show `full_workflow` disabled with “not implemented” note
- Request payload rules:
  - `rag_llm`: send `{ mode: "rag_llm", provider: selectedProviderId, memory_mode: "on" }`
  - `rules`: send `{ mode: "rules" }` (do not send provider; memory toggle not shown)
  - `llm`: send `{ mode: "llm", provider: selectedProviderId }`
- Baseline selector:
  - allow optional baseline selection
  - filter candidates to compatible runs only (same mode/provider/mode_detail)
  - if user selects baseline, include `baseline_run_id`
- Compare runs section (frontend-only mode comparison):
  - select run A and run B from all runs
  - compute per-metric deltas locally (A - B)
  - clearly label as “Compare runs” (not “baseline”)

## Step 7 - Test Checklist (Backend + Frontend)

**Backend**
- `test_benchmark_endpoint.py`
  - rules ignores provider and normalizes memory_mode to off (mode_detail stable)
  - rag_llm requires provider and forces memory_mode on
  - full_workflow returns clear error without executing
  - baseline_run_id validation:
    - 404 when missing
    - 400 when incompatible (mode/provider/mode_detail mismatch)
    - validation occurs before execution (assert runner not called)
- `test_benchmark_runner.py`
  - rag_llm persists `BenchmarkRun.mode="rag_llm"` but uses LLM execution branch
  - rules persists provider None and mode_detail memory_mode off
  - baseline auto-selection uses normalized mode_detail
- `test_benchmark_report_service.py`
  - report loads baseline using baseline_run_id and prints Delta column
  - does not require persisted per-metric deltas

**Frontend**
- `benchmarkPresentation.test.js`
  - rag_llm label/memory label behavior (if exposed in UI)
  - delta formatting helpers for compare runs
  - run button disabled when provider missing in LLM/rag_llm

## Step 8 - Run Verification Commands

**Backend**
```bash
python -m pytest backend/tests -q
```

**Frontend**
```bash
npm test
```

**Done when**
- rules/llm/rag_llm are supported with consistent normalization.
- explicit baseline is validated before expensive execution.
- report computes deltas from baseline at generation time (no persisted per-metric deltas).
- frontend supports mode selection, baseline selection, and compare runs without adding new backend APIs.

