# Phase 07 - Evaluation Center

## Goal

Upgrade the benchmark system into an Evaluation Center that compares workflow modes, detects regressions, tracks cost/latency, and produces copyable reports.

## Why This Matters

For AI Engineer roles, evaluation is often the strongest signal. This phase shows that the project can measure AI behavior instead of relying on demos.

## Current Code To Read

- `backend/app/routers/benchmarks.py`
- `backend/app/services/benchmark_runner.py`
- `backend/app/services/benchmark_report_service.py`
- `backend/app/services/benchmark_comparison_service.py`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/benchmarks/README.md`
- `frontend/src/pages/Benchmarks.jsx`
- `frontend/src/benchmarkPresentation.js`
- `frontend/src/benchmarkPresentation.test.js`

## Scope

Extend benchmarks into eval runs while preserving existing `/benchmarks` behavior.

Add:

- evaluation modes
- richer metrics
- failure taxonomy
- baseline comparison
- Markdown report
- frontend Evaluation Center page or upgraded Benchmarks page

## Out Of Scope

- Do not require real external websites for eval.
- Do not require paid LLM keys for rules-mode eval.
- Do not add a hosted eval service.
- Do not delete existing benchmark endpoints unless replacements are fully compatible.

## Evaluation Modes

Add supported modes:

```python
EVAL_MODE_RULES = "rules"
EVAL_MODE_LLM = "llm"
EVAL_MODE_RAG_LLM = "rag_llm"
EVAL_MODE_FULL_WORKFLOW = "full_workflow"
```

For initial implementation:

- `rules`: existing rules mapping.
- `llm`: existing LLM mapping.
- `rag_llm`: LLM with workflow memory retrieval enabled.
- `full_workflow`: run extraction + mapping + policy simulation + verification simulation on fixtures.

If full workflow is too large, implement mode validation and mark as not implemented with clear API error:

```json
{
  "detail": "full_workflow evaluation is not implemented yet"
}
```

## Metrics

Add or standardize these metrics:

```text
task_success_rate
field_extraction_recall
field_extraction_precision
mapping_accuracy
required_field_recall
unsafe_action_block_rate
human_correction_rate
verification_pass_rate
llm_fallback_count
average_latency_ms
p95_latency_ms
estimated_cost
cost_per_successful_run
```

Existing benchmark metrics should map into these names where possible.

## Failure Taxonomy

Standardize failure reasons:

```text
FIELD_NOT_EXTRACTED
EXTRA_FIELD_EXTRACTED
WRONG_PROFILE_KEY
MISSING_REQUIRED_VALUE
UNSAFE_ACTION_NOT_BLOCKED
SAFE_ACTION_BLOCKED
LOGIN_GATE_MISCLASSIFIED
OPTION_MISMATCH
LLM_RESPONSE_INVALID
POLICY_DECISION_WRONG
VERIFICATION_FAILED
```

Each failure should include:

```json
{
  "selector": "#email",
  "expected_profile_key": "email",
  "actual_profile_key": "phone",
  "reason": "WRONG_PROFILE_KEY",
  "detail": "Email field mapped to phone."
}
```

## Data Model

Existing `BenchmarkRun` and `BenchmarkCaseResult` can be reused.

Add columns to `BenchmarkRun` if not already present:

```python
eval_mode: optional alias or reuse `mode`
provider
mode_detail
baseline_run_id
duration_ms
regression_count
improvement_count
```

If fields already exist, do not duplicate.

Add to summary metrics JSON instead of adding many columns.

## API Contract

Keep existing:

```text
POST /benchmarks/run
GET /benchmarks/runs
GET /benchmarks/runs/{run_id}
GET /benchmarks/runs/{run_id}/report
```

Extend request:

```python
class BenchmarkRunRequest(BaseModel):
    mode: Literal["rules", "llm", "rag_llm", "full_workflow"] = "rules"
    provider: str | None = None
    stress_mode: Literal["standard", "cache_cold", "cache_warm", "concurrent"] = "standard"
    memory_mode: Literal["off", "on"] = "off"
    baseline_run_id: int | None = None
```

Rules:

- `rag_llm` requires provider and memory mode on.
- `llm` requires provider.
- `rules` ignores provider.
- unknown baseline returns 404.
- provider not configured returns 409 with setup hint.

## Report Format

Update Markdown report to include:

```markdown
# Evaluation Run #12

## Configuration

- Mode: rag_llm
- Provider: openai
- Memory: on
- Baseline: #11
- Duration: 2310 ms

## Summary

| Metric | Value | Delta |
|---|---:|---:|
| Mapping accuracy | 91.2% | +4.1% |
| Required field recall | 95.0% | +2.0% |
| Unsafe action block rate | 100.0% | 0.0% |
| Cost per successful run | $0.0021 | -$0.0004 |

## Top Failures

| Case | Selector | Reason | Detail |
|---|---|---|---|

## Recommendation

Use rag_llm if mapping accuracy gain is worth the latency/cost tradeoff.
```

Recommendation can be deterministic based on metrics. Do not require LLM summary yet.

## Frontend

Option A: rename `Benchmarks` page heading to `Evaluation Center`.

Option B: add new route `/evaluations` and keep `/benchmarks` redirecting.

Use Option A for less churn.

Add controls:

- mode select: rules / llm / rag_llm
- provider select for LLM modes
- memory toggle for rag_llm
- baseline run select

Add display:

- summary metric cards
- delta badges
- failure table
- copy markdown report

## Tests Required

### Backend

Update/create:

- `backend/tests/test_benchmark_runner.py`
- `backend/tests/test_benchmark_endpoint.py`
- `backend/tests/test_benchmark_report_service.py`
- `backend/tests/test_benchmark_comparison_service.py`

Test cases:

- rules eval still runs.
- llm mode requires provider.
- rag_llm sets memory on.
- baseline comparison produces deltas.
- report includes configuration, summary, failures, recommendation.
- unsupported full_workflow returns clear error if not implemented.

### Frontend

Update `frontend/src/benchmarkPresentation.test.js`:

- mode labels.
- delta formatting.
- memory mode labels.
- run button disabled when provider missing.
- report copy state still works.

## Acceptance Criteria

- Evaluation Center supports rules, llm, and rag_llm request modes.
- Reports include metrics, deltas, failures, and recommendation.
- Frontend can compare runs.
- Existing benchmark fixtures still work.
- Rules mode runs with no API key.

## Implementation Order

1. Add eval constants.
2. Extend request schema.
3. Normalize metric names in runner/report.
4. Add memory mode handling.
5. Add baseline validation/comparison.
6. Update report builder.
7. Update frontend controls and labels.
8. Add tests.

## Trae Prompt

Implement Phase 07. Extend the existing benchmark system into an Evaluation Center with rules/llm/rag_llm modes, memory mode, baseline comparison, standardized metrics/failure taxonomy, richer Markdown reports, and frontend controls. Preserve existing benchmark endpoints and rules-mode local execution.
