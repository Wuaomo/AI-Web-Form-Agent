# Phase 1 Reliability Foundation

> For agentic workers: implement task-by-task. Keep commits small. Use tests as the gate, not optimism.

## Background

AI Web Form Agent already has the core review-first loop:

```text
Create Profile -> Create Task -> Analyze Form -> Generate Mapping -> Review -> Fill -> Pause Before Submit
```

The weak point is not missing ambition. It is evidence quality. When extraction,
mapping, validation, or browser execution fails, the product must explain why in
stable terms that both users and future agents can act on. Phase 1 turns the
existing workflow into a reliable, measurable baseline without changing the
architecture or introducing autonomous behavior.

## Goals

- Make benchmark and task failures diagnosable through stable reason codes.
- Surface review attention clearly before users confirm mappings.
- Preserve the existing safety model: no automatic final submission.
- Improve Task Detail evidence so debugging does not require database access.
- Add enough project documentation for a reviewer to understand architecture,
  safety boundaries, benchmarks, and a safe demo path.

## Non-Goals

- Do not add multi-agent runtime behavior.
- Do not add generalized page actions. That belongs to Phase 2.
- Do not rename existing public routes.
- Do not change database schema unless a task explicitly needs it.
- Do not add charts, analytics frameworks, telemetry vendors, or new UI systems.
- Do not claim benchmark scores unless they were actually run and recorded.

## Ponytail Scope Controls

| Temptation | Do instead | Add later only when |
| --- | --- | --- |
| New error framework | Shared string constants in one backend module plus frontend labels | Multiple APIs need versioned error contracts |
| New task state machine library | Keep existing status strings and add tests around transitions | Status transitions become hard to reason about |
| New logging service | Reuse existing task logs and debug report generation | Logs need cross-process aggregation |
| New charting dependency | Show compact benchmark metadata and tables | Reviewers need visual trend analysis across many runs |
| New documentation site | Add focused Markdown docs linked from README | The docs become too large for README navigation |

The smallest useful implementation is one canonical failure vocabulary, a few
presentation helpers, focused tests, and Markdown docs. Anything beyond that is
Phase 2+ or evidence-driven follow-up.

## Design

### Architecture

Keep the current stack:

```text
React/Vite UI
  -> FastAPI API
    -> SQLAlchemy + SQLite
    -> FormExtractor
    -> FieldMapper
    -> BrowserExecutor
    -> BenchmarkRunner
    -> Action logs, screenshots, and LLM usage evidence
```

Phase 1 adds a quality layer around this flow. It does not replace the flow.

### Failure Reason Contract

Backend reason codes must be lowercase `snake_case` strings on the wire.
Frontend presentation should map those stable codes to English labels. Legacy
failure strings may still appear in old benchmark results, so the frontend
keeps a compatibility map.

Initial shared codes:

```text
field_not_extracted
label_not_found
wrong_profile_key
required_field_unmapped
low_confidence_mapping
option_value_mismatch
unsupported_field_type
action_field_skipped
action_field_should_skip
unexpected_extra_mapping
login_required
browser_fill_failed
submission_requires_approval
```

### Review Attention Model

Review Mapping should separate fields that block progress from fields that only
need awareness:

- `requiredMissing`: required fillable fields without values.
- `lowConfidence`: mapped fields below the confidence threshold.
- `optionalUnmapped`: optional fields without values.
- `skippedActionFields`: fields that are intentionally not reviewable.
- `sensitiveOrOneTime`: password, OTP, payment, consent, submit, and similar
  fields that should not become reusable profile memory.

Optional unmapped fields must not block confirmation.

### Evidence Model

Task Detail should answer three questions without raw database inspection:

1. What state is the task in?
2. What happened during extraction, mapping, confirmation, and fill?
3. What evidence can a developer copy into a bug report?

Use existing logs, screenshots, profile update results, skipped fields, and LLM
usage records. Do not create a second event store.

## Implementation Plan

### Task 1: Shared Failure Reason Codes

Files:

- Create `backend/app/failure_reasons.py`.
- Modify `backend/app/services/benchmark_runner.py`.
- Modify `frontend/src/benchmarkPresentation.js`.
- Test with `backend/tests/test_benchmark_runner.py` and
  `frontend/src/benchmarkPresentation.test.js`.

Implementation:

- Add a short module docstring:

```python
"""Shared failure reason codes returned by quality and task evidence APIs."""
```

- Export constants using lowercase `snake_case` values.
- Export `BENCHMARK_FAILURE_REASONS` as `set[str]`.
- Replace touched raw benchmark reason strings with constants.
- Preserve `legacyFailureReasonMap` in the frontend.
- Add labels for every reason code.
- Do not change the database schema.

Validation:

```powershell
cd backend
pytest tests/test_benchmark_runner.py -v
```

```powershell
cd frontend
npm test -- benchmarkPresentation.test.js
```

### Task 2: Actionable Benchmark Failures

Files:

- Modify `backend/app/services/benchmark_runner.py`.
- Modify `frontend/src/benchmarkPresentation.js`.
- Update existing benchmark presentation tests.

Failure objects should include:

```text
selector
expected_profile_key
actual_profile_key
reason
detail
```

Implementation:

- Emit `field_not_extracted` for missing expected selectors.
- Emit `wrong_profile_key` for incorrect mappings.
- Emit `required_field_unmapped` for extracted required fields without mapped
  values.
- Emit `action_field_should_skip` for action/non-fillable fields that receive a
  mapping.
- Emit `unexpected_extra_mapping` for ignored selectors that receive mappings.
- Keep `mapping_accuracy` denominator limited to extracted expected profile-key
  fields.
- Keep `fill_success_rate` deterministic for local fixtures.

Validation:

```powershell
cd backend
pytest tests/test_benchmark_runner.py -v
```

```powershell
cd frontend
npm test -- benchmarkPresentation.test.js
```

### Task 3: Benchmark Baseline Documentation

Files:

- Modify `backend/benchmarks/README.md`.
- Create `docs/benchmark-methodology.md`.
- Link the methodology from `README.md`.

Content requirements:

- Explain `rules` and `llm` modes.
- Define:
  - `field_extraction_recall`
  - `field_extraction_precision`
  - `mapping_accuracy`
  - `required_field_coverage`
  - `non_fillable_rejection_rate`
  - `login_detection_accuracy`
  - `fill_success_rate`
  - `llm_fallback_count`
- Include exact baseline commands.
- Avoid unverified reliability claims.

### Task 4: Review Attention Categories

Files:

- Modify `frontend/src/reviewMappingPresentation.js`.
- Modify `frontend/src/pages/ReviewMapping.jsx`.
- Test with `frontend/src/reviewMappingPresentation.test.js`.

Implementation:

- Keep existing `requiredMissing` and `lowConfidence` behavior.
- Rename `unmapped` to `optionalUnmapped`; keep a compatibility alias if needed.
- Add `skippedActionFields`.
- Add `sensitiveOrOneTime` using case-insensitive tokens:

```text
password, otp, verification, payment, card, billing, consent, terms, privacy, submit
```

- Render headings:
  - `Required missing`
  - `Low confidence`
  - `Optional unmapped`
  - `Skipped action fields`
  - `Sensitive or one-time fields`

Validation:

```powershell
cd frontend
npm test -- reviewMappingPresentation.test.js
```

### Task 5: Structured Mapping Confirmation Errors

Files:

- Modify `backend/app/routers/tasks.py`.
- Modify `backend/app/schemas.py` only if a response model is needed.
- Modify `frontend/src/api.js` only if nested error detail parsing is needed.
- Test with `backend/tests/test_task_mapping_endpoint.py`.

Preferred error detail:

```json
{
  "message": "Required fields need values before filling.",
  "reason": "required_field_unmapped",
  "fields": [
    {"field_id": 123, "label": "Email"}
  ]
}
```

Implementation:

- Keep HTTP status `409`.
- Keep an English message for current UI behavior.
- Do not set `READY_TO_FILL` when required fillable fields are missing.
- If `api.js` receives an object `detail`, show `detail.message` first.

Validation:

```powershell
cd backend
pytest tests/test_task_mapping_endpoint.py -v
```

### Task 6: Profile Memory Safety Evidence

Files:

- Modify `backend/app/routers/tasks.py`.
- Modify `backend/app/schemas.py`.
- Modify `frontend/src/pages/TaskDetail.jsx`.
- Test with `backend/tests/test_task_mapping_endpoint.py`.

Implementation:

- Do not save one-time or sensitive fields as reusable profile memory.
- Ensure `force_save` cannot override password, OTP, payment, billing, card,
  terms, privacy, consent, submit, login, or upload-like fields.
- Keep `profile_updates` and `profile_skipped`.
- Keep existing skip reasons.
- Add useful English `detail` values.
- Do not display sensitive skipped values.

Validation:

```powershell
cd backend
pytest tests/test_task_mapping_endpoint.py -v
```

### Task 7: Task Evidence Timeline

Files:

- Modify `frontend/src/agentTimeline.js`.
- Modify `frontend/src/pages/TaskDetail.jsx`.
- Modify `frontend/src/styles.css` only for minimal layout support.
- Test with `frontend/src/agentTimeline.test.js`.

Implementation:

- Keep `getWorkflowTimeline(task, logs)`.
- Keep `buildAgentTimeline(logs, fields)`.
- Map every supported task status to exactly one active, failed, or blocked step.
- Show failed mapping logs for `map_fields` and `llm_map_fields`.
- Show skipped field summary after extraction.
- Render an `Execution evidence` section with title, status, timestamp, and
  expandable details.
- Use `formatChinaTime()` for timestamps.

Validation:

```powershell
cd frontend
npm test -- agentTimeline.test.js
```

### Task 8: Debug Report

Files:

- Modify `frontend/src/debugReport.js`.
- Modify `frontend/src/pages/TaskDetail.jsx` only if placement needs adjustment.
- Test with `frontend/src/debugReport.test.js`.

Implementation:

- Keep `generateDebugReport(task, profiles, screenshots, llmUsage, logs)`.
- Include task id, URL, status, profile, description, field counts, latest failed
  log, latest screenshot URL, LLM usage, and last 10 logs.
- Count required missing fields when `mapped_value` is `null` or `""`.
- Do not include full sensitive mapped values.

Validation:

```powershell
cd frontend
npm test -- debugReport.test.js
```

### Task 9: Benchmarks Page Evidence

Files:

- Modify `frontend/src/pages/Benchmarks.jsx`.
- Modify `frontend/src/benchmarkPresentation.js`.
- Modify `frontend/src/styles.css` only if the existing layout cannot support
  the metadata.
- Test with `frontend/src/benchmarkPresentation.test.js`.

Implementation:

- Keep modes `rules` and `llm`.
- Keep provider selection disabled unless mode is `llm`.
- Show run id, mode, provider when applicable, created time, total cases, and
  total failures.
- Sort failed cases before passing cases.
- Show `Passing` or `Needs attention`.
- Keep failure table columns: `Selector`, `Expected`, `Actual`, `Reason`,
  `Detail`.
- Do not add charts.

Validation:

```powershell
cd frontend
npm test -- benchmarkPresentation.test.js
```

### Task 10: Safe Demo Walkthrough

Files:

- Create `docs/demo-walkthrough.md`.
- Link it from `README.md`.

Content requirements:

- Use local fixtures first.
- Include backend and frontend setup commands.
- Walk through profile creation, task creation, form analysis, mapping, review,
  fill, screenshot inspection, and stopping before final submission.
- Do not imply CAPTCHA, login, or bot-check bypass.

### Task 11: Architecture Documentation

Files:

- Create `docs/architecture.md`.
- Link it from `README.md`.

Required positioning:

```text
AI Web Form Agent is a review-first browser automation system for safe web form filling.
```

Include this diagram:

```text
React UI
  -> FastAPI API
    -> FormExtractor
    -> FieldMapper
    -> Review and Confirmation
    -> BrowserExecutor
    -> Evidence and Benchmarking
    -> SQLite Persistence
```

Explain `FormExtractor`, `FieldMapper`, `BrowserExecutor`,
`BenchmarkRunner`, `ActionTraceService`, and LLM usage logging in 2-4 sentences
each. Add `Why not multi-agent in Phase 1?`.

### Task 12: Safety Boundary Documentation

Files:

- Create `docs/safety-boundaries.md`.
- Link it from `README.md`.

Required loop:

```text
Extract -> Map -> Review -> Confirm -> Fill -> Pause -> Submit only after approval
```

Document:

- No final submission without explicit approval.
- No CAPTCHA solving.
- No anti-bot bypass.
- No payment, purchase, delete, or destructive action automation.
- No password, OTP, payment card, or one-time consent values saved as reusable
  profile memory.
- Manual login is user-controlled.

### Task 13: End-to-End Verification

Run:

```powershell
cd backend
pytest -v
```

```powershell
cd frontend
npm test
npm run build
```

Manual checks:

- Run the demo walkthrough.
- Confirm all new UI text is English.
- Confirm final submission still requires explicit user action.

## Risks

- **Reason-code drift:** Backend and frontend labels can diverge. Keep constants
  small and test labels.
- **Overblocking:** Sensitive-field detection may flag benign fields. Prefer
  explainable skip evidence over silent saves.
- **UI clutter:** Evidence can become noisy. Group summaries first, details on
  expansion.
- **Overclaiming:** Documentation can outrun the product. Only document tested
  behavior as supported.

## Follow-Up

- Add trend charts only after benchmark history becomes large enough to compare.
- Add richer failure taxonomy only when current reason codes cannot diagnose real
  failures.
- Move to generalized page actions in Phase 2 after Phase 1 evidence is stable.

## Acceptance Criteria

- Backend and frontend focused tests pass for all touched behavior.
- Benchmark failures use stable reason codes and precise English details.
- Review Mapping separates blockers from awareness-only items.
- Task Detail shows useful execution evidence and safe debug reports.
- README links to benchmark, architecture, demo, and safety documentation.
- No new autonomous execution path is introduced.

## Self-Review

- This phase strengthens the existing reviewed form-fill product.
- It avoids multi-agent architecture, new UI systems, and speculative telemetry.
- It gives future phases a reliable evidence baseline instead of a larger bug
  surface.
