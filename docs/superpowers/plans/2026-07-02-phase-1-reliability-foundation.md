# Phase 1 Reliability Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the current form-filling workflow into a reliable, explainable, and repeatably measurable review-first automation loop.

**Architecture:** Keep the existing React -> FastAPI -> SQLite -> Playwright architecture. Add a thin quality layer around the current pipeline: structured failure reasons, benchmark evidence, review attention summaries, task evidence summaries, and portfolio-grade documentation.

**Tech Stack:** Python, FastAPI, SQLAlchemy, pytest, React, Vite, Node test runner, Playwright.

## Global Constraints

- All user-facing page text must be English.
- All new code comments and docstrings must be English.
- Do not introduce multi-agent runtime architecture in Phase 1.
- Do not rename existing API routes unless a task explicitly says so.
- Do not remove safety boundaries: no automatic final submission, no CAPTCHA bypass, no payment automation, no destructive actions, no sensitive profile-memory write-back.
- Prefer existing modules over new abstractions unless the task explicitly creates a small helper module.
- Every task must include tests before implementation changes where practical.
- Every task should be committed independently.

---

## File Structure

- `backend/app/failure_reasons.py`: new shared constants and labels for structured backend failure reasons.
- `backend/app/services/benchmark_runner.py`: normalize benchmark failure reason codes and make failure details more diagnostic.
- `backend/app/routers/tasks.py`: attach structured failure details to task logs and expose consistent validation messages.
- `backend/app/schemas.py`: add response models only if a task needs new API shape.
- `backend/tests/test_benchmark_runner.py`: benchmark scoring and failure reason tests.
- `backend/tests/test_confirm_submit.py`: approval and required-field guard tests.
- `backend/tests/test_task_mapping_endpoint.py`: mapping confirmation and validation tests.
- `frontend/src/benchmarkPresentation.js`: benchmark metric and failure label presentation.
- `frontend/src/reviewMappingPresentation.js`: review grouping, attention summary, and safety presentation helpers.
- `frontend/src/agentTimeline.js`: workflow timeline and evidence timeline presentation helpers.
- `frontend/src/debugReport.js`: copyable debug report content.
- `frontend/src/pages/Benchmarks.jsx`: benchmark evidence page.
- `frontend/src/pages/ReviewMapping.jsx`: mapping review page.
- `frontend/src/pages/TaskDetail.jsx`: task execution evidence page.
- `frontend/src/*.test.js`: focused unit tests for presentation helpers.
- `README.md`: concise positioning and demo path.
- `docs/architecture.md`: system architecture.
- `docs/safety-boundaries.md`: safety and approval model.
- `docs/benchmark-methodology.md`: benchmark scoring method.
- `docs/demo-walkthrough.md`: reproducible demo flow.

---

### Task 1: Define Shared Failure Reason Codes

**Purpose:** Give backend and frontend agents one canonical vocabulary for why extraction, mapping, validation, or execution failed.

**Files:**
- Create: `backend/app/failure_reasons.py`
- Modify: `backend/app/services/benchmark_runner.py`
- Modify: `frontend/src/benchmarkPresentation.js`
- Test: `backend/tests/test_benchmark_runner.py`
- Test: `frontend/src/benchmarkPresentation.test.js`

**Interfaces:**
- Produces Python constants:
  - `FIELD_NOT_EXTRACTED`
  - `LABEL_NOT_FOUND`
  - `WRONG_PROFILE_KEY`
  - `REQUIRED_FIELD_UNMAPPED`
  - `LOW_CONFIDENCE_MAPPING`
  - `OPTION_VALUE_MISMATCH`
  - `UNSUPPORTED_FIELD_TYPE`
  - `ACTION_FIELD_SKIPPED`
  - `ACTION_FIELD_SHOULD_SKIP`
  - `UNEXPECTED_EXTRA_MAPPING`
  - `LOGIN_REQUIRED`
  - `BROWSER_FILL_FAILED`
  - `SUBMISSION_REQUIRES_APPROVAL`
- Produces JS label support for the snake_case wire values, for example `field_not_extracted -> "Field not extracted"`.

**Implementation Instructions:**
- [ ] Create `backend/app/failure_reasons.py`.
- [ ] Use lowercase snake_case string values on the wire. Do not use uppercase strings in JSON responses.
- [ ] Include a short English docstring at the top: `"""Shared failure reason codes returned by quality and task evidence APIs."""`
- [ ] Export `BENCHMARK_FAILURE_REASONS` as a `set[str]` containing the benchmark-related values.
- [ ] In `benchmark_runner.py`, import constants instead of writing raw strings for new or touched failure records.
- [ ] Keep backward compatibility in `frontend/src/benchmarkPresentation.js` by preserving `legacyFailureReasonMap`.
- [ ] Add labels for every new reason code in `failureReasonLabels`.
- [ ] Do not change database schema in this task.

**Suggested Backend Constant Shape:**

```python
"""Shared failure reason codes returned by quality and task evidence APIs."""

FIELD_NOT_EXTRACTED = "field_not_extracted"
LABEL_NOT_FOUND = "label_not_found"
WRONG_PROFILE_KEY = "wrong_profile_key"
REQUIRED_FIELD_UNMAPPED = "required_field_unmapped"
LOW_CONFIDENCE_MAPPING = "low_confidence_mapping"
OPTION_VALUE_MISMATCH = "option_value_mismatch"
UNSUPPORTED_FIELD_TYPE = "unsupported_field_type"
ACTION_FIELD_SKIPPED = "action_field_skipped"
ACTION_FIELD_SHOULD_SKIP = "action_field_should_skip"
UNEXPECTED_EXTRA_MAPPING = "unexpected_extra_mapping"
LOGIN_REQUIRED = "login_required"
BROWSER_FILL_FAILED = "browser_fill_failed"
SUBMISSION_REQUIRES_APPROVAL = "submission_requires_approval"

BENCHMARK_FAILURE_REASONS = {
    FIELD_NOT_EXTRACTED,
    WRONG_PROFILE_KEY,
    REQUIRED_FIELD_UNMAPPED,
    LOW_CONFIDENCE_MAPPING,
    OPTION_VALUE_MISMATCH,
    ACTION_FIELD_SHOULD_SKIP,
    UNEXPECTED_EXTRA_MAPPING,
    LOGIN_REQUIRED,
}
```

**Tests:**
- [ ] Add a backend test that all benchmark failure records from a simple scoring example use reason codes in `BENCHMARK_FAILURE_REASONS`.
- [ ] Add a frontend test that `failureReasonLabel("required_field_unmapped")` returns `"Required field unmapped"`.
- [ ] Run: `cd backend; pytest tests/test_benchmark_runner.py -v`
- [ ] Run: `cd frontend; npm test -- benchmarkPresentation.test.js`

**Acceptance Criteria:**
- All new reason codes are English, stable, and snake_case.
- Existing benchmark runs still render legacy failure reasons.
- No page text is Chinese.

---

### Task 2: Harden Benchmark Scoring Details

**Purpose:** Make benchmark failures directly actionable for extraction and mapping work.

**Files:**
- Modify: `backend/app/services/benchmark_runner.py`
- Modify: `backend/tests/test_benchmark_runner.py`
- Modify: `frontend/src/benchmarkPresentation.js`
- Modify: `frontend/src/benchmarkPresentation.test.js`

**Interfaces:**
- Keeps existing `BenchmarkRunResponse` shape.
- Each failure object must include:
  - `selector: str`
  - `expected_profile_key: str | None`
  - `actual_profile_key: str | None`
  - `reason: str`
  - `detail: str`

**Implementation Instructions:**
- [ ] Update `score_case()` to use the shared reason constants.
- [ ] For expected required fields that are extracted but have no mapping, emit `required_field_unmapped`.
- [ ] For expected action/non-fillable fields that receive a mapping, emit `action_field_should_skip`.
- [ ] For ignored selectors that receive a mapping, emit `unexpected_extra_mapping`.
- [ ] Keep `mapping_accuracy` denominator limited to extracted fields with expected profile keys, as the current code does.
- [ ] Do not make `fill_success_rate` depend on live browser execution in this task; keep it deterministic for local fixtures.
- [ ] Make all `detail` strings precise and English. Include selector and expected/actual values where useful.

**Test Cases To Add:**
- [ ] Missing selector produces `field_not_extracted`.
- [ ] Wrong mapping produces `wrong_profile_key`.
- [ ] Required extracted selector with no mapped key produces `required_field_unmapped`.
- [ ] Submit/button/action field with a mapped key produces `action_field_should_skip`.
- [ ] Ignored selector with a mapped key produces `unexpected_extra_mapping`.

**Commands:**
- [ ] Run: `cd backend; pytest tests/test_benchmark_runner.py -v`
- [ ] Run: `cd frontend; npm test -- benchmarkPresentation.test.js`

**Acceptance Criteria:**
- The Benchmarks page can show a useful reason for every failed benchmark row.
- No benchmark failure row shows a vague `"unknown"` reason unless old persisted data lacks a reason.

---

### Task 3: Add Benchmark Baseline Documentation And Demo Cases

**Purpose:** Make the current reliability level reproducible before future feature expansion.

**Files:**
- Modify: `backend/benchmarks/README.md`
- Modify: `README.md`
- Create: `docs/benchmark-methodology.md`

**Implementation Instructions:**
- [ ] Document the current benchmark mode choices: `rules` and `llm`.
- [ ] Explain each metric in English:
  - `field_extraction_recall`
  - `field_extraction_precision`
  - `mapping_accuracy`
  - `required_field_coverage`
  - `non_fillable_rejection_rate`
  - `login_detection_accuracy`
  - `fill_success_rate`
  - `llm_fallback_count`
- [ ] Add a "Recommended baseline run" section with exact commands:

```powershell
cd backend
pytest tests/test_benchmark_runner.py -v
```

```powershell
cd frontend
npm test -- benchmarkPresentation.test.js
```

- [ ] In `README.md`, link to `docs/benchmark-methodology.md`.
- [ ] Do not claim a specific score unless the implementer runs the benchmark and records the actual number.

**Acceptance Criteria:**
- A reviewer understands what each metric means without reading source code.
- Documentation does not overclaim reliability.
- All documentation text is English.

---

### Task 4: Create Review Attention Categories

**Purpose:** Let users know exactly what requires attention before confirming mappings.

**Files:**
- Modify: `frontend/src/reviewMappingPresentation.js`
- Modify: `frontend/src/reviewMappingPresentation.test.js`
- Modify: `frontend/src/pages/ReviewMapping.jsx`

**Interfaces:**
- `computeAttentionSummary(fields)` should return:
  - `requiredMissing`
  - `lowConfidence`
  - `optionalUnmapped`
  - `skippedActionFields`
  - `sensitiveOrOneTime`

**Implementation Instructions:**
- [ ] Keep existing `requiredMissing` and `lowConfidence` behavior.
- [ ] Rename `unmapped` to `optionalUnmapped`, but preserve a compatibility alias if existing tests expect `unmapped`.
- [ ] Add `skippedActionFields`: fields where `isReviewableField(field) === false`.
- [ ] Add `sensitiveOrOneTime`: fields whose label/name/placeholder/selector contains tokens:
  - `password`
  - `otp`
  - `verification`
  - `payment`
  - `card`
  - `billing`
  - `consent`
  - `terms`
  - `privacy`
  - `submit`
- [ ] Ensure matching is case-insensitive.
- [ ] Do not block confirmation for optional unmapped fields.
- [ ] In `ReviewMapping.jsx`, render attention section headings in English:
  - `"Required missing"`
  - `"Low confidence"`
  - `"Optional unmapped"`
  - `"Skipped action fields"`
  - `"Sensitive or one-time fields"`
- [ ] Keep button text English: `"Generate mappings"`, `"Confirm mapping"`.

**Tests:**
- [ ] Required empty input appears under `requiredMissing`.
- [ ] Confidence below `0.75` appears under `lowConfidence`.
- [ ] Optional field without mapping appears under `optionalUnmapped`.
- [ ] Submit/file/button fields appear under `skippedActionFields`.
- [ ] Password/OTP/payment-like fields appear under `sensitiveOrOneTime`.
- [ ] Run: `cd frontend; npm test -- reviewMappingPresentation.test.js`

**Acceptance Criteria:**
- The Review Mapping page tells users what needs action and what was intentionally skipped.
- No Chinese UI text is introduced.

---

### Task 5: Make Mapping Confirmation Errors Structured And Friendly

**Purpose:** Make required-field blocking predictable for both API clients and the UI.

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/app/schemas.py` if needed
- Modify: `backend/tests/test_task_mapping_endpoint.py`
- Modify: `frontend/src/api.js` only if the response parser needs nested detail support
- Modify: `frontend/src/pages/ReviewMapping.jsx`

**Interfaces:**
- Prefer keeping the HTTP status as `409`.
- If changing error detail shape, use:

```json
{
  "message": "Required fields need values before filling.",
  "reason": "required_field_unmapped",
  "fields": [
    {"field_id": 123, "label": "Email"}
  ]
}
```

**Implementation Instructions:**
- [ ] In `confirm_task_mapping()`, when required fields are missing, return `409`.
- [ ] Preserve a readable English error for existing frontend behavior.
- [ ] If `api.js` receives an object `detail`, display `detail.message` first.
- [ ] Do not allow `READY_TO_FILL` when any required fillable field has no `mapped_value`.
- [ ] Add or update tests to verify status remains unchanged after the failed confirmation.

**Tests:**
- [ ] Missing required field returns `409`.
- [ ] Response contains `required_field_unmapped` if structured detail is implemented.
- [ ] Task remains in previous status after failed confirmation.
- [ ] Run: `cd backend; pytest tests/test_task_mapping_endpoint.py -v`

**Acceptance Criteria:**
- Users get a clear English message.
- Agents can programmatically identify the reason.

---

### Task 6: Strengthen Profile Memory Safety Evidence

**Purpose:** Make profile write-back behavior auditable and safe.

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/tests/test_task_mapping_endpoint.py`
- Modify: `frontend/src/pages/TaskDetail.jsx`

**Interfaces:**
- Existing `MappingConfirmationResponse.profile_updates` and `profile_skipped` remain.
- Existing skip reasons remain valid:
  - `empty_value`
  - `non_fillable_type`
  - `one_time_field`
  - `unchanged`
  - `do_not_save`
  - `force_save_blocked`

**Implementation Instructions:**
- [ ] Do not save values from fields detected by `is_one_time_field()`.
- [ ] Ensure `force_save` cannot override password, OTP, payment, billing, card, terms, privacy, consent, submit, login, or upload-like fields.
- [ ] Ensure each skipped field has a useful English `detail`, preferably the field display name.
- [ ] In `TaskDetail.jsx`, keep the section title `"Skipped fields"`.
- [ ] Add visible English reasons:
  - `"One-time or sensitive field"`
  - `"Blocked because this field looks sensitive"`
  - `"Do not save (user preference)"`
- [ ] Do not show sensitive field values in the skipped list.

**Tests:**
- [ ] Password-like field with `force_save` returns `force_save_blocked`.
- [ ] Terms/privacy checkbox is skipped as one-time unless explicitly mapped only for filling.
- [ ] Normal custom field can still be saved.
- [ ] Run: `cd backend; pytest tests/test_task_mapping_endpoint.py -v`

**Acceptance Criteria:**
- The system can explain which fields were not saved and why.
- Sensitive values are not persisted as reusable profile data.

---

### Task 7: Improve Task Evidence Timeline

**Purpose:** Make task execution explainable from Task Detail without opening logs manually.

**Files:**
- Modify: `frontend/src/agentTimeline.js`
- Modify: `frontend/src/agentTimeline.test.js`
- Modify: `frontend/src/pages/TaskDetail.jsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Keep `getWorkflowTimeline(task, logs)` as the workflow-state helper.
- Keep `buildAgentTimeline(logs, fields)` as the detailed evidence helper.

**Implementation Instructions:**
- [ ] In `agentTimeline.js`, ensure every supported task status maps to exactly one active/failed/blocked step.
- [ ] Add display support for failed mapping logs if action is `"map_fields"` or `"llm_map_fields"`.
- [ ] Add display support for skipped field summary after extraction.
- [ ] In `TaskDetail.jsx`, render a detailed `"Execution evidence"` section using `buildAgentTimeline(taskLogs, task.form_fields)`.
- [ ] For each evidence item, show:
  - title
  - status
  - timestamp
  - expandable details
- [ ] Use existing `formatChinaTime()` for timestamps.
- [ ] Keep all headings and labels English.

**Tests:**
- [ ] `FAILED` with latest `fill_form` log marks fill as failed.
- [ ] `LOGIN_REQUIRED` marks analyze as blocked.
- [ ] `WAITING_APPROVAL` marks approval as active.
- [ ] `buildAgentTimeline()` creates mapped, missing, and skipped summary entries after extraction.
- [ ] Run: `cd frontend; npm test -- agentTimeline.test.js`

**Acceptance Criteria:**
- A reviewer can understand what happened during a task from Task Detail alone.
- The page does not require inspecting raw database rows.

---

### Task 8: Expand Debug Report

**Purpose:** Make copied debug reports useful for fixing failed runs.

**Files:**
- Modify: `frontend/src/debugReport.js`
- Modify: `frontend/src/debugReport.test.js`
- Modify: `frontend/src/pages/TaskDetail.jsx` only if button placement needs adjustment

**Interfaces:**
- Keep `generateDebugReport(task, profiles, screenshots, llmUsage, logs)`.
- Output remains plain text.

**Implementation Instructions:**
- [ ] Include task id, URL, status, profile, and description.
- [ ] Include counts:
  - total fields
  - mapped fields
  - required missing fields
  - skipped/non-fillable fields
- [ ] Include latest failed log if any:
  - action
  - status
  - message
  - created_at
- [ ] Include latest screenshot URL if present.
- [ ] Include LLM usage summary if available.
- [ ] Include the last 10 logs.
- [ ] Fix missing required calculation so it treats both `null` and empty string as missing.
- [ ] Do not include full sensitive mapped values in the report. If values are shown at all, mask them.

**Tests:**
- [ ] Required field with `mapped_value: null` is counted as missing.
- [ ] Required field with `mapped_value: ""` is counted as missing.
- [ ] Latest failed log is included.
- [ ] LLM usage appears when provided.
- [ ] Run: `cd frontend; npm test -- debugReport.test.js`

**Acceptance Criteria:**
- The copied report is enough to diagnose a failed task at a high level.
- The report avoids leaking sensitive mapped values.

---

### Task 9: Improve Benchmarks Page Evidence

**Purpose:** Make benchmark results easier to read and compare.

**Files:**
- Modify: `frontend/src/pages/Benchmarks.jsx`
- Modify: `frontend/src/benchmarkPresentation.js`
- Modify: `frontend/src/benchmarkPresentation.test.js`
- Modify: `frontend/src/styles.css`

**Implementation Instructions:**
- [ ] Keep the mode selector with values `"rules"` and `"llm"`.
- [ ] Keep provider selection disabled unless mode is `"llm"`.
- [ ] Add run metadata display:
  - run id
  - mode
  - provider if applicable
  - created time if available
  - total cases
  - total failures
- [ ] In case result rows, sort failed cases before passing cases.
- [ ] For each case, show a compact status label:
  - `"Passing"` if zero failures
  - `"Needs attention"` if one or more failures
- [ ] Keep table columns English: `"Selector"`, `"Expected"`, `"Actual"`, `"Reason"`, `"Detail"`.
- [ ] Do not add charts in this task.

**Tests:**
- [ ] Presentation helper returns correct total failures.
- [ ] Failure labels remain stable.
- [ ] Run: `cd frontend; npm test -- benchmarkPresentation.test.js`

**Acceptance Criteria:**
- The benchmark page clearly communicates quality and failure hotspots.
- The page remains useful without LLM provider credentials.

---

### Task 10: Add Safe Demo Walkthrough

**Purpose:** Give reviewers one complete path to exercise the product.

**Files:**
- Create: `docs/demo-walkthrough.md`
- Modify: `README.md`

**Implementation Instructions:**
- [ ] Write the walkthrough in English.
- [ ] Use local fixtures first, not external sites.
- [ ] Include backend setup:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m playwright install chromium
uvicorn app.main:app --reload
```

- [ ] Include frontend setup:

```powershell
cd frontend
npm install
npm run dev
```

- [ ] Include a safe demo flow:
  - create a profile
  - create a task with a local benchmark fixture URL if supported by the UI
  - analyze form
  - generate mappings
  - review mapping
  - confirm mapping
  - fill form
  - inspect screenshot
  - stop before final submission unless explicitly approved
- [ ] Add a README link to the walkthrough.
- [ ] Do not imply that the app bypasses login, CAPTCHA, or bot checks.

**Acceptance Criteria:**
- A reviewer can run the main demo without guessing the sequence.
- The safety boundary is obvious in the demo.

---

### Task 11: Add Architecture Documentation

**Purpose:** Explain the system as a review-first workflow, not a generic multi-agent app.

**Files:**
- Create: `docs/architecture.md`
- Modify: `README.md`

**Implementation Instructions:**
- [ ] Use this English positioning:

```text
AI Web Form Agent is a review-first browser automation system for safe web form filling.
```

- [ ] Include this architecture diagram in text form:

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

- [ ] Explain each module in 2-4 sentences:
  - `FormExtractor`
  - `FieldMapper`
  - `BrowserExecutor`
  - `BenchmarkRunner`
  - `ActionTraceService`
  - `LLM usage logging`
- [ ] Add a short section named `"Why not multi-agent in Phase 1?"`.
- [ ] State that Phase 1 uses modular workflow components, not multiple autonomous agents.
- [ ] Link the document from `README.md`.

**Acceptance Criteria:**
- The project sounds intentional and scoped.
- The documentation does not oversell multi-agent behavior.

---

### Task 12: Add Safety Boundary Documentation

**Purpose:** Make the approval model and prohibited actions explicit.

**Files:**
- Create: `docs/safety-boundaries.md`
- Modify: `README.md`

**Implementation Instructions:**
- [ ] Write all content in English.
- [ ] Include required boundaries:
  - no final submission without explicit approval
  - no CAPTCHA solving
  - no anti-bot bypass
  - no payment, purchase, delete, or destructive action automation
  - no password, OTP, payment card, or one-time consent values saved as reusable profile memory
  - manual login must be user-controlled
- [ ] Include a short explanation of the review-first loop:

```text
Extract -> Map -> Review -> Confirm -> Fill -> Pause -> Submit only after approval
```

- [ ] Explain how skipped fields and debug evidence support safety.
- [ ] Link from README.

**Acceptance Criteria:**
- A reviewer can quickly see that the project is safe by design.
- The app is positioned as controlled automation, not scraping or abuse tooling.

---

### Task 13: End-to-End Verification Pass

**Purpose:** Confirm Phase 1 is stable after the tasks above.

**Files:**
- No feature files unless a verification failure requires a fix.

**Commands:**
- [ ] Run backend tests:

```powershell
cd backend
pytest -v
```

- [ ] Run frontend tests:

```powershell
cd frontend
npm test
```

- [ ] Run frontend build:

```powershell
cd frontend
npm run build
```

- [ ] Start backend and frontend manually and run the demo walkthrough.
- [ ] Verify these pages contain English text only:
  - Dashboard
  - Profiles
  - Create Task
  - Task Detail
  - Review Mapping
  - Benchmarks
- [ ] Verify final submission still requires explicit user action.

**Acceptance Criteria:**
- All tests pass.
- The app builds.
- The demo walkthrough is reproducible.
- The UI and new code comments are English.

---

## Recommended Execution Order

1. Task 1: Define Shared Failure Reason Codes
2. Task 2: Harden Benchmark Scoring Details
3. Task 4: Create Review Attention Categories
4. Task 5: Make Mapping Confirmation Errors Structured And Friendly
5. Task 6: Strengthen Profile Memory Safety Evidence
6. Task 7: Improve Task Evidence Timeline
7. Task 8: Expand Debug Report
8. Task 9: Improve Benchmarks Page Evidence
9. Task 3: Add Benchmark Baseline Documentation And Demo Cases
10. Task 10: Add Safe Demo Walkthrough
11. Task 11: Add Architecture Documentation
12. Task 12: Add Safety Boundary Documentation
13. Task 13: End-to-End Verification Pass

## Self-Review

- Spec coverage: The plan covers benchmark reliability, failure reason codes, Review Mapping attention summary, Task Detail timeline, debug report, README/docs packaging, and safety boundaries.
- Placeholder scan: No task contains `TBD`, `TODO`, or unspecified implementation placeholders.
- Type consistency: The plan preserves existing API route names and existing frontend helper names unless a task explicitly extends return values.
- Scope check: This plan stays within Phase 1 and does not introduce multi-step workflow planning or multi-agent execution.
