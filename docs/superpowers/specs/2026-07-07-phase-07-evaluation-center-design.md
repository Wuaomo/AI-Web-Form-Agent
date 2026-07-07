# Phase 07 - Evaluation Center (Design)

## Goal

Upgrade the existing benchmark system into an “Evaluation Center” that:

- runs multiple evaluation modes on local HTML fixtures
- supports baseline deltas (same configuration only) to detect regressions/improvements
- supports cross-mode comparison (rules vs llm, memory off vs on) as a frontend-only workflow
- produces copyable Markdown reports that include configuration, metrics, failures, and deltas

## Non-Goals / Hard Constraints

- Do not require real external websites for eval.
- Do not require paid LLM keys for rules-mode eval.
- Do not add a hosted eval service.
- Do not delete or break existing `/benchmarks` endpoints.
- Do not introduce new database tables for eval runs (reuse existing `BenchmarkRun` + `BenchmarkCaseResult`).
- Mode baseline deltas are only for “same configuration vs baseline”. Cross-mode/cross-config comparisons belong to “mode comparison”.

## Existing Code Surfaces

- API: [benchmarks.py](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/backend/app/routers/benchmarks.py)
- Runner: [benchmark_runner.py](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/backend/app/services/benchmark_runner.py)
- Report: [benchmark_report_service.py](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/backend/app/services/benchmark_report_service.py)
- Metric delta classifier: [benchmark_comparison_service.py](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/backend/app/services/benchmark_comparison_service.py)
- Frontend page: [Benchmarks.jsx](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/pages/Benchmarks.jsx)
- Frontend presentation helpers: [benchmarkPresentation.js](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/benchmarkPresentation.js)
- Phase 07 upgrade doc: [07-evaluation-center.md](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/docs/trae-upgrade/07-evaluation-center.md)

## Terminology

- **Evaluation run**: one persisted `BenchmarkRun` record plus many `BenchmarkCaseResult` rows.
- **Evaluation mode**: what we evaluate (rules / llm / rag_llm / full_workflow).
- **Execution mode**: which code path runs during `_run_case` (rules execution vs LLM execution).
- **Baseline delta**: comparing a run against a baseline run with the same configuration.
- **Mode comparison**: comparing any two runs in the UI (may be different configurations).

## Data Model

Reuse existing:

- `BenchmarkRun`
- `BenchmarkCaseResult`

### BenchmarkRun fields (no new table)

- `mode: str`
  - accepted values expanded to: `rules`, `llm`, `rag_llm`, `full_workflow`
  - `BenchmarkRun.mode` stores the evaluation mode name (e.g. `rag_llm`), not the internal execution mode string.
- `provider: str | None`
  - required for `llm` and `rag_llm`
  - must be `None` for `rules`
- `mode_detail: str | None`
  - continues to store `stress_mode=...;memory_mode=...`
  - must be normalized for rules mode so baseline matching does not split on meaningless memory toggles
- `baseline_run_id: int | None`
  - persisted baseline chosen (explicit or auto)
- `summary_metrics_json`
  - keep using JSON to extend metrics
- `duration_ms`, `regression_count`, `improvement_count`
  - reused as-is

## Evaluation Modes and Execution Mapping

Supported evaluation modes (API-level):

- `rules`
- `llm`
- `rag_llm`
- `full_workflow` (not implemented; only validated)

### rag_llm execution boundary (required)

- `rag_llm` is an evaluation mode name.
- The actual mapping execution must reuse the existing LLM execution path (the same code used by `llm`).
- `rag_llm` must force `memory_mode=on`.
- Persisted `BenchmarkRun.mode` must be `rag_llm`.
- `_run_case` / `run_benchmarks` must treat `rag_llm` as an LLM execution mode, not as `rules`.

Practical mapping:

- evaluation mode `rules` → execution mode `rules`
- evaluation mode `llm` → execution mode `llm` (provider required)
- evaluation mode `rag_llm` → execution mode `llm` (provider required, `memory_mode=on`)
- evaluation mode `full_workflow` → return clear error: `full_workflow evaluation is not implemented yet`

## Request Normalization Rules

### rules mode provider normalization (required)

- rules mode ignores any incoming `provider` value.
- Backend must normalize `provider=None` before persisting the run.
- `BenchmarkRun.provider` must be stored as `None` for rules runs.

### rules mode memory_mode normalization (required)

- rules mode does not use workflow memory.
- Even if the client sends `memory_mode=on`, the backend must normalize it to `off` (preferred over rejecting).
- Persist `mode_detail` as `stress_mode=...;memory_mode=off` for rules runs.
- This prevents baseline candidates from being split by a meaningless memory toggle.

### rag_llm mode memory enforcement

- `mode="rag_llm"` must force `memory_mode="on"` regardless of user input.
- If the request explicitly sets `memory_mode="off"`, the backend may normalize to `on` (preferred) or reject; for consistency with rules-mode leniency, normalize to `on`.

## Baseline Delta (Same-Configuration Only)

### API Contract

Extend `BenchmarkRunRequest` with:

- `baseline_run_id?: int`

### Auto baseline selection

When `baseline_run_id` is not provided:

- pick the latest run with the same:
  - `mode`
  - `provider`
  - `mode_detail` (must include `stress_mode` and normalized `memory_mode`)
- exclude the current run itself
- if no baseline exists, baseline is treated as missing (no deltas)

### Explicit baseline validation

When `baseline_run_id` is provided:

- Validation order (required):
  - First normalize `mode`, `provider`, `stress_mode`, `memory_mode`, and the derived `mode_detail`.
  - Then validate `baseline_run_id` exists and is compatible.
  - Only after validation succeeds, run the benchmark execution (avoid running an expensive LLM call and failing with `400` afterwards).
- baseline run must exist; otherwise return `404`
- baseline must be compatible with the current run:
  - same `mode`
  - same `provider`
  - same `mode_detail`
- if incompatible: return `400` with a message that cross-mode comparison belongs to “mode comparison”

### Delta computation

- compute per-metric deltas using `compare_summary_metrics(current, baseline)`
- `regression_count` / `improvement_count` reflect deltas vs baseline only (same configuration)
- do not persist per-metric comparison results as new DB columns; keep it report/UI-level output

## Mode Comparison (Cross-Mode / Cross-Config)

Mode comparison is a frontend-only workflow:

- user selects run A and run B from the run list
- frontend computes summary metric deltas (A - B) and displays them
- backend does not add a new compare endpoint in Phase 07 (minimal churn)

Rules:

- mode comparison may compare different `mode`, `provider`, and `mode_detail`
- UI must clearly label it as a cross-run comparison (not “baseline delta”)

## API Surface (Backwards-Compatible)

Keep existing endpoints:

- `POST /benchmarks/run`
- `GET /benchmarks/runs`
- `GET /benchmarks/runs/{run_id}`
- `GET /benchmarks/runs/{run_id}/report`

Extend request schema:

```python
class BenchmarkRunRequest(BaseModel):
    mode: Literal["rules", "llm", "rag_llm", "full_workflow"] = "rules"
    provider: str | None = None
    stress_mode: Literal["standard", "cache_cold", "cache_warm", "concurrent"] = "standard"
    memory_mode: Literal["off", "on"] = "off"
    baseline_run_id: int | None = None
```

Validation rules:

- `rules` ignores provider and normalizes memory_mode to `off`
- `llm` requires provider
- `rag_llm` requires provider and forces memory_mode to `on`
- `full_workflow` returns clear error (not implemented)
- provider not configured returns `409` with setup hint

## Report Format (Markdown)

Extend the existing report to include:

- configuration summary (mode, provider, stress_mode, memory_mode, baseline)
- summary metrics table with an optional Delta column when a baseline is present
- regression/improvement counts (already available)
- failures table (already available)
- deterministic recommendation section (optional, no LLM)

Notes:

- baseline delta is only shown when baseline exists and is compatible
- mode comparison is not embedded into the per-run report (it lives in UI)

### Delta data source (required)

- The report builder must load the baseline run based on `run.baseline_run_id`.
- The Delta column is computed at report-generation time from `current.summary_metrics` and `baseline.summary_metrics`.
- Do not add DB columns and do not persist per-metric deltas.

## Frontend Scope (Evaluation Center as Benchmarks Page Upgrade)

Goal: minimal churn, reuse the existing `Benchmarks` page but treat it as “Evaluation Center”.

Required changes:

- Mode selector: add `rag_llm` (and optionally show `full_workflow` as disabled with help text)
- When `rag_llm` is selected:
  - force memory on in request payload (or hide the memory toggle and send `memory_mode=on`)
- Add baseline selection control:
  - default: auto baseline (no `baseline_run_id` sent)
  - optional: choose a baseline run from a filtered list (compatible only)
  - if user selects an incompatible baseline, block submit client-side with explanation
- Add a “Compare runs” section:
  - select run A and run B
  - show metric deltas computed locally

## Tests Required (Design Checklist)

Backend:

- rules mode normalizes memory_mode to off and persists `mode_detail` accordingly
- rag_llm forces memory_mode on and executes via LLM branch
- baseline_run_id: 404 if missing baseline; 400 if incompatible baseline
- auto baseline selection prefers latest compatible run
- report includes baseline config and delta column when baseline exists

Frontend:

- rag_llm option present and forces memory_mode=on
- baseline selector filters to compatible runs
- compare runs UI computes deltas locally and shows them with clear labels

## Implementation Order (High-Level)

1. Extend schema `BenchmarkRunRequest` with new modes and `baseline_run_id`.
2. Normalize request: rules memory_mode → off; rag_llm memory_mode → on.
3. Update `benchmarks.py` router to route `rag_llm` into the LLM execution path.
4. Update runner to store `BenchmarkRun.mode` as the evaluation mode (including `rag_llm`).
5. Baseline selection and compatibility checks (explicit + auto).
6. Report updates to render baseline configuration and deltas.
7. Frontend updates (mode selector + baseline + compare).
8. Tests.
