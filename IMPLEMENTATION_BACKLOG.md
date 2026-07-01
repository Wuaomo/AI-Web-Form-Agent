# Internal Implementation Backlog

This file is an internal implementation backlog for splitting upcoming work
into small, reviewable tasks.

Use one task at a time. Do not implement the whole file in one run.
Each task has its own scope, files, acceptance criteria, and tests.

Project goal:
Turn the AI Web Form Agent from a working demo into a more complete,
interview-ready agent system with evaluation, human review, observability,
LLM cost/cache visibility, and clear safety boundaries.

Recommended order:

1. Epic 1, Task 1.1A
2. Epic 1, Task 1.1B
3. Epic 1, Task 1.1C
4. Epic 1, Task 1.2
5. Epic 1, Task 1.3
6. Epic 2, Task 2.1
7. Epic 2, Task 2.2
8. Epic 3, Task 3.1
9. Epic 3, Task 3.2
10. Epic 4, Task 4.1
11. Epic 5 docs tasks

Important global rules:

- Keep safety boundaries unchanged.
- Do not auto-submit forms without explicit user approval.
- Do not solve CAPTCHA.
- Do not bypass login.
- Do not automate payments, purchases, deletes, or destructive actions.
- LLMs may propose mappings only. They must not directly control Playwright.
- Do not call real LLM APIs in automated tests.
- Prefer small, focused changes.
- Add tests for backend or frontend logic when the task changes behavior.
- Preserve existing rules-mode behavior unless the task explicitly changes it.

---

## Epic 1: Benchmark Evaluation System

Goal:
Upgrade benchmarks from a rules-only demo into a selectable evaluation system
that can compare rules and LLM mapping quality, show failure reasons, and later
explain cache/cost behavior.

---

## Task 1.1A: Benchmark Page Mode and Provider UI

### Goal

Add frontend controls so the user can choose benchmark mode:

- `rules`
- `llm`

When mode is `llm`, show a provider selector populated from backend provider
configuration.

### Scope

Frontend only.

Do not change benchmark runner logic in this task.
Do not add new metrics in this task.
Do not add cache hit display in this task.

### Files

- `frontend/src/pages/Benchmarks.jsx`
- `frontend/src/api.js`
- `frontend/src/benchmarkPresentation.js` only if helper functions are useful
- Add or update frontend tests if there are existing helpers to test

### Existing APIs

Use:

```http
GET /llm/providers
POST /benchmarks/run
GET /benchmarks/runs
```

Provider response contains:

```text
id
display_name
model
api_key_env
configured
selected
setup_hint
```

### UI Requirements

Add controls near the existing `Run benchmarks` button.

Mode selector:

```text
Mode: [rules | llm]
```

Provider selector appears only when mode is `llm`:

```text
Provider: [OpenAI | Gemini | DeepSeek]
```

Provider selector rules:

- Load providers from `GET /llm/providers`.
- Show all providers.
- Mark unconfigured providers clearly in the option label, for example:
  - `DeepSeek`
  - `OpenAI - not configured`
- Default selected provider:
  - Prefer a provider where `selected === true`.
  - If none selected, prefer the first configured provider.
  - If none configured, use the first provider.

Run button rules:

- If mode is `rules`, button is enabled as before.
- If mode is `llm` and selected provider is configured, button is enabled.
- If mode is `llm` and selected provider is not configured, button is disabled
  and the page shows the selected provider's `setup_hint`.

Request body:

Rules:

```json
{
  "mode": "rules"
}
```

LLM:

```json
{
  "mode": "llm",
  "provider": "deepseek"
}
```

### Display Requirements

For the selected benchmark run, show:

```text
Mode: rules
```

or:

```text
Mode: llm
Provider: deepseek
```

The run list should still show average score.

### Error Handling

Any backend error from `POST /benchmarks/run` must be shown using the existing
`<Message type="error">`.

The page must not crash if:

- Provider list fails to load.
- Provider list is empty.
- Backend returns a 409 setup error.

### Acceptance Criteria

- Benchmark page loads providers from backend.
- Default mode is `rules`.
- User can switch to `llm`.
- Provider selector appears only in LLM mode.
- Unconfigured provider displays setup hint and disables run button.
- Rules benchmark request sends `{ "mode": "rules" }`.
- LLM benchmark request sends `{ "mode": "llm", "provider": "<provider>" }`.
- Selected run detail shows mode and provider.
- Existing benchmark run list still works.

### Tests

If there are existing frontend helper tests:

- Add helper tests for provider selection logic.
- Add helper tests for whether run button should be disabled.

Manual verification is acceptable for page rendering if there is no current
React component test setup.

---

## Task 1.1B: Backend Provider Validation for Benchmark Runs

### Goal

Validate benchmark run requests on the backend so LLM benchmarks cannot be run
without a valid configured provider.

### Scope

Backend API validation only.

Do not change true LLM benchmark execution in this task.
Do not add new benchmark metrics in this task.

### Files

- `backend/app/routers/benchmarks.py`
- `backend/app/schemas.py` only if request schema needs tightening
- `backend/tests/test_benchmark_endpoint.py`

### Backend Requirements

In `POST /benchmarks/run`:

Rules mode:

- Request `{ "mode": "rules" }` succeeds.
- Provider must be persisted as `None` for rules runs.
- If caller sends provider with rules mode, ignore it or normalize it to `None`.

LLM mode:

- Provider is required.
- Invalid provider returns `400`.
- Unconfigured provider returns `409`.
- 409 detail must use existing setup hint from provider config helper.

Use existing helpers from:

```python
app.services.llm_provider_config
```

Expected helpers:

```python
resolve_llm_provider
is_provider_configured
get_provider_setup_hint
```

Runner call:

```python
run_benchmarks(mode=options.mode, provider=selected_provider, db=db)
```

For rules:

```python
run_benchmarks(mode="rules", provider=None, db=db)
```

### Acceptance Criteria

- Rules benchmark still succeeds with empty body or `{ "mode": "rules" }`.
- LLM benchmark without provider returns `400` or `422`.
- LLM benchmark with invalid provider returns `400`.
- LLM benchmark with missing API key returns `409`.
- Successful rules run persists `mode="rules"` and `provider=null`.
- Successful LLM run persists `mode="llm"` and selected provider.

### Tests

Add tests in `backend/tests/test_benchmark_endpoint.py`:

1. Rules mode succeeds.
2. Empty request body defaults to rules.
3. LLM mode without provider fails.
4. LLM mode with unconfigured provider returns 409.
5. LLM mode with configured provider calls `run_benchmarks` with mode/provider.

Tests must mock provider configuration and benchmark runner where appropriate.
Tests must not call real LLM APIs.

---

## Task 1.1C: True LLM Benchmark Runner

### Goal

Make `mode="llm"` benchmark runs actually use LLM mapping behavior instead of
being mislabeled rules runs.

### Scope

Backend benchmark runner.

Do not change frontend UI in this task.
Do not add cache hit summary in this task.
Do not add new benchmark cases in this task.

### Files

- `backend/app/services/benchmark_runner.py`
- `backend/app/services/field_mapper.py` only if a small public helper is needed
- `backend/tests/test_benchmark_runner.py`

### Current Behavior

`benchmark_runner.py` currently:

1. Opens each local benchmark HTML file.
2. Extracts raw fields with Playwright.
3. Converts raw fields to temporary `FormField` objects.
4. Uses `_match_profile_key` directly.
5. Scores actual profile keys against expected JSON.

This means `mode="llm"` would currently be mislabeled unless the runner changes.

### Required Design

Split mapping paths:

```python
def _actual_fields_from_rules(raw_fields):
    ...

def _actual_fields_from_llm(raw_fields, provider, db):
    ...
```

Then:

```python
def _run_case(case, mode="rules", provider=None, db=None):
    ...
    if mode == "llm":
        fields = _actual_fields_from_llm(raw_fields, provider, db)
    else:
        fields = _actual_fields_from_rules(raw_fields)
```

### LLM Mapping Strategy

Preferred implementation:

Use existing database-backed mapper:

```python
map_fields_with_llm(task.id, db, provider=provider)
```

For each benchmark case in LLM mode:

1. Create a benchmark `Profile`.
2. Create a benchmark `Task`.
3. Insert extracted `FormField` rows for the task.
4. Call `map_fields_with_llm`.
5. Convert returned fields into benchmark actual fields:

```json
{
  "selector": "#email",
  "profile_key": "email",
  "required": true
}
```

### Temporary Data Handling

Avoid polluting normal user task lists.

Preferred:

- Use a transaction/savepoint and roll back benchmark task/profile rows after
  scoring the case.

If this is difficult because mapper functions commit internally:

- Use clear benchmark markers:

```text
profile_name = "__benchmark_profile__"
task.description = "__benchmark_run__"
```

- Delete benchmark rows after each case.

Do not leave benchmark tasks visible in the normal Dashboard.

### Benchmark Profile

Use this profile data for both rules and LLM benchmark paths:

```python
profile_name="Benchmark profile"
full_name="Ada Lovelace"
email="ada@example.com"
phone="555-0100"
university="Analytical University"
major="Computer Science"
linkedin="https://linkedin.example/ada"
github="https://github.example/ada"
self_intro="I build reliable analytical engines."
```

### LLM Fallback Count

If `map_fields_with_llm` falls back to rules internally, record:

```json
"llm_fallback_count": 1
```

If fallback detection is hard without larger refactor, leave this metric as `0`
and add a TODO comment. Do not block Task 1.1C on fallback-count perfection.

### Acceptance Criteria

- `run_benchmarks(mode="rules")` keeps current deterministic rules behavior.
- `run_benchmarks(mode="llm", provider="deepseek", db=db)` uses LLM mapping path.
- LLM output is validated by the existing mapper.
- Tests mock LLM mapping and do not call external APIs.
- Temporary benchmark tasks/profiles do not remain visible after a benchmark run.
- Persisted benchmark run stores `mode="llm"` and selected provider.

### Tests

Add tests in `backend/tests/test_benchmark_runner.py`:

1. Rules mode still produces expected metrics.
2. LLM mode calls `map_fields_with_llm`.
3. LLM mode converts mapped fields to expected actual field shape.
4. LLM mode does not call a real provider in tests.

---

## Task 1.2: Benchmark Summary Metrics

### Goal

Make benchmark output more professional by showing quality metrics, not just an
average score.

### Scope

Backend metric calculation and frontend display.

Do not add cache hit rate in this task unless the data is already available in
the benchmark summary without new persistence work.

### Files

- `backend/app/services/benchmark_runner.py`
- `backend/app/schemas.py` only if response typing needs changes
- `frontend/src/benchmarkPresentation.js`
- `frontend/src/pages/Benchmarks.jsx`
- `backend/tests/test_benchmark_runner.py`
- `frontend/src/benchmarkPresentation.test.js`

### Required Metrics

Ensure benchmark summary includes:

```text
field_extraction_recall
field_extraction_precision
mapping_accuracy
required_field_coverage
non_fillable_rejection_rate
login_detection_accuracy
fill_success_rate
llm_fallback_count
```

Frontend display labels:

```text
Extraction recall
Extraction precision
Mapping accuracy
Required coverage
Non-fillable rejection
Login detection
Fill success
LLM fallback count
```

### UI Requirements

In Benchmarks page summary:

- Show average score.
- Show all summary metrics.
- Percent metrics display as percentages.
- Count metrics display as numbers.
- Missing metric displays `N/A`.

### Acceptance Criteria

- Benchmark summary clearly shows quality metrics.
- Case detail still shows per-case metrics.
- Old benchmark runs with missing metrics do not crash the UI.
- Backend tests cover average metric calculation.
- Frontend tests cover metric formatting.

---

## Task 1.3: Benchmark Failure Reason Taxonomy

### Goal

Make benchmark failures explainable with stable reason codes.

### Scope

Backend scoring and frontend display.

### Files

- `backend/app/services/benchmark_runner.py`
- `backend/tests/test_benchmark_runner.py`
- `frontend/src/pages/Benchmarks.jsx`
- `frontend/src/benchmarkPresentation.js`
- `frontend/src/benchmarkPresentation.test.js`

### Required Failure Reasons

Use these stable reason strings:

```text
field_not_extracted
wrong_profile_key
missing_required_value
action_field_should_skip
option_value_mismatch
low_confidence_mapping
unexpected_extra_mapping
```

If current implementation uses older names, migrate display logic but do not
break old persisted runs. For old names, map them to display text gracefully.

Suggested mapping from old to new:

```text
missing_extraction -> field_not_extracted
profile_key_mismatch -> wrong_profile_key
should_not_map -> action_field_should_skip
```

### Failure Object Shape

Each failure should include:

```json
{
  "selector": "#email",
  "expected_profile_key": "email",
  "actual_profile_key": "phone",
  "reason": "wrong_profile_key",
  "detail": "Expected email but mapped to phone"
}
```

`detail` is optional but recommended.

### UI Requirements

Benchmark case failure table should show:

- Selector
- Expected
- Actual
- Reason
- Detail if available

Reason should be human-readable, for example:

```text
wrong_profile_key -> Wrong profile key
field_not_extracted -> Field was not extracted
```

### Acceptance Criteria

- Every failure has a `reason`.
- Reason strings are stable.
- UI displays reason and does not expose raw ugly enum names as the only text.
- Tests cover at least:
  - field not extracted
  - wrong profile key
  - action field should skip

---

## Task 1.4: Add Realistic Benchmark Cases

### Goal

Add more benchmark fixtures that represent real-world form patterns.

### Scope

Benchmark fixture files only, plus tests that count/load cases.

### Files

Add:

- `backend/benchmarks/forms/11_multi_section_application.html`
- `backend/benchmarks/forms/12_select_option_mismatch.html`
- `backend/benchmarks/forms/13_radio_group_preferences.html`
- `backend/benchmarks/forms/14_checkbox_group_interests.html`
- `backend/benchmarks/forms/15_address_and_date_fields.html`
- Matching JSON files under `backend/benchmarks/expected/`

Update:

- `backend/tests/test_benchmark_samples.py`
- `backend/benchmarks/README.md`

### Case Requirements

Case 11: Multi-section application

- Personal info section
- Education section
- Links section
- Expected fields include full name, email, university, major, GitHub/LinkedIn

Case 12: Select option mismatch

- Select option labels differ from profile values.
- Example: profile has `Computer Science`, option says `CS / Computing`.
- Expected JSON should clarify intended profile key.

Case 13: Radio group preferences

- Radio inputs sharing same name.
- Include at least one radio group that maps to a profile/custom value later.
- Include at least one radio/action-like option that should not map.

Case 14: Checkbox group interests

- Multiple checkboxes.
- Include one consent/terms checkbox that should not map.
- Include interest/skill checkboxes that expose current rules limitations.

Case 15: Address and date fields

- Address line, city, state, zip, country.
- Graduation month/year or date field.
- Some may not map with current built-in profile keys. That is acceptable if
  expected JSON marks them clearly.

### Acceptance Criteria

- Benchmark loader discovers 15 cases.
- Tests updated from 10 to 15 cases.
- Rules benchmark still runs.
- Cases are useful even if current rules fail some mappings.
- README explains what the new cases cover.

---

## Task 1.5: Benchmark Regression Smoke Test

### Goal

Prevent future changes from silently breaking benchmark loading and summary
shape.

### Scope

Tests only.

### Files

- `backend/tests/test_benchmark_runner.py`
- `backend/tests/test_benchmark_samples.py`

### Requirements

Add tests that verify:

- Benchmark case count is expected.
- Every expected JSON file has required fields:
  - `case_id`
  - `title`
  - `html_file`
  - `expected`
- Every expected field has:
  - `selector`
  - `profile_key`
  - `required`
- `run_benchmarks(mode="rules")` returns:
  - total case count
  - average score
  - summary metrics
  - case results
  - failures list for each case

### Acceptance Criteria

- Tests pass without LLM API keys.
- Tests do not depend on external network.
- Test failure messages make it easy to fix bad benchmark fixture JSON.

---

## Epic 2: Review Mapping and Profile Memory

Goal:
Make human-in-the-loop review more visible, safer, and easier to explain in
interviews.

---

## Task 2.1: Review Mapping Attention Summary

### Goal

At the top of Review Mapping, show what the user should pay attention to before
confirming mapping.

### Scope

Frontend review page and presentation helpers.

### Files

- `frontend/src/pages/ReviewMapping.jsx`
- `frontend/src/reviewMappingPresentation.js`
- `frontend/src/reviewMappingPresentation.test.js`

### Summary Categories

Show three categories:

1. Required missing
2. Low confidence
3. Not mapped / skipped-like fields

Definitions:

Required missing:

```text
field.required === true
field is fillable
field.mapped_value is empty
```

Low confidence:

```text
field.confidence is not null
field.confidence < 0.75
```

Not mapped:

```text
field is fillable
field.required is false
field.mapped_profile_key is empty
field.mapped_value is empty
```

### UI Requirements

At top of page, show a compact summary:

```text
Needs attention
Required missing: 2
Low confidence: 3
Not mapped: 5
```

Show field names under each category or in expandable details.

Do not block Confirm Mapping for low confidence or optional unmapped fields.
Only required missing fields should block confirmation as they already do.

### Acceptance Criteria

- Required missing fields are visible near the top.
- Low confidence fields are visible near the top.
- Optional unmapped fields are visible but not alarming.
- Existing review field editing still works.
- Tests cover summary calculation.

---

## Task 2.2: Profile Updates and Skipped Summary UI

### Goal

After Confirm Mapping, show both what was saved to profile and what was skipped.

### Scope

Frontend UI. Backend already returns:

```text
profile_updates
profile_skipped
```

### Files

- `frontend/src/pages/ReviewMapping.jsx`
- `frontend/src/pages/TaskDetail.jsx`
- `frontend/src/reviewMappingPresentation.js` if helper text is useful

### Requirements

When `api.confirmMapping(taskId)` succeeds:

- Navigate back to Task Detail.
- Pass both:
  - `profileUpdates`
  - `profileSkipped`

Task Detail should display:

Profile updates:

```text
email: old@example.com -> ada@example.com
custom:portfolio: (empty) -> https://github.example/ada
```

Skipped summary:

```text
Skipped 3 fields
- Terms agreement: one-time or sensitive field
- Submit button: non-fillable field
- Password: one-time or sensitive field
```

### Reason Display Mapping

```text
empty_value -> Empty value
non_fillable_type -> Not fillable
one_time_field -> One-time or sensitive field
unchanged -> Already saved
```

### Acceptance Criteria

- Confirm Mapping success shows update summary.
- Confirm Mapping success shows skipped summary.
- If there are no updates, page does not show an empty card.
- If there are no skipped fields, page does not show an empty skipped section.
- Existing notice still appears.

---

## Task 2.3: Per-field Profile Memory Policy

### Goal

Allow the user to control whether a field should be written back to reusable
profile memory.

### Scope

Backend schema/model plus Review Mapping UI.

Do this after Tasks 2.1 and 2.2.

### Files

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/routers/tasks.py`
- `backend/tests/test_task_mapping_endpoint.py`
- `frontend/src/pages/ReviewMapping.jsx`
- `frontend/src/reviewMappingPresentation.js`

### Data Model

Add to `FormField`:

```text
profile_memory_policy
```

Allowed values:

```text
auto
do_not_save
force_save
```

Default:

```text
auto
```

### API Requirements

Allow `PUT /tasks/{task_id}/fields/{field_id}` to update
`profile_memory_policy`.

Validation:

- Unknown value returns 422 or 400.
- `None` should normalize to `auto`.

### Confirm Mapping Behavior

If policy is `do_not_save`:

- Do not write field to profile.
- Add `profile_skipped` item with reason `do_not_save`.

If policy is `force_save`:

- Save field if:
  - field has mapped value
  - field is fillable
  - field is not one-time/sensitive
- If field is one-time/sensitive, do not save even with `force_save`.
- Add skipped reason if force-save is blocked.

If policy is `auto`:

- Keep current behavior.

### UI Requirements

On Review Mapping field rows, add a compact control:

```text
Memory: Auto | Do not save | Force save
```

Do not show this control for obvious non-fillable fields unless they are already
shown in review.

### Acceptance Criteria

- User can set memory policy per field.
- `do_not_save` prevents profile writeback.
- `force_save` saves safe fillable fields.
- Sensitive fields are never saved even with force-save.
- Backend tests cover all three policies.

---

## Epic 3: Task Observability

Goal:
Make the agent workflow explainable: what happened, what is next, why did it
fail, and what did the LLM cost/cache behavior look like.

---

## Task 3.1: Task Detail Agent Timeline

### Goal

Show the full agent workflow as a timeline on Task Detail.

### Scope

Frontend state presentation.

### Files

- `frontend/src/pages/TaskDetail.jsx`
- `frontend/src/agentTimeline.js`
- `frontend/src/agentTimeline.test.js`

### Timeline Nodes

```text
Created
Analyze
Map Fields
Review Mapping
Confirm Mapping
Fill Form
Waiting Approval
Submit
Completed
```

### Node Statuses

```text
pending
active
success
failed
blocked
```

Mapping from task status:

```text
CREATED -> Created success, Analyze pending
ANALYZING -> Analyze active
LOGIN_REQUIRED -> Analyze blocked
LOGIN_IN_PROGRESS -> Analyze active or blocked with login message
MAPPING_READY -> Analyze success, Map/Review active
READY_TO_FILL -> Confirm Mapping success, Fill pending
FILLING -> Fill active
WAITING_APPROVAL -> Fill success, Waiting Approval active
COMPLETED -> all success
FAILED -> latest known phase failed
```

If exact failed phase cannot be derived, show generic failed at current/last
known step.

### UI Requirements

Task Detail should show:

- Timeline nodes in order.
- Current active step.
- Failed or blocked status if applicable.
- Short helper text for `LOGIN_REQUIRED` and `WAITING_APPROVAL`.

### Acceptance Criteria

- Timeline appears on Task Detail.
- Timeline does not break existing primary action panel.
- Tests cover at least:
  - CREATED
  - LOGIN_REQUIRED
  - READY_TO_FILL
  - WAITING_APPROVAL
  - COMPLETED
  - FAILED

---

## Task 3.2: Task Detail LLM Usage and Cache Summary

### Goal

Show LLM usage and cache behavior on Task Detail so cache hit becomes a
supporting observability/cost story.

### Scope

Frontend only, using existing backend endpoint.

### Files

- `frontend/src/api.js`
- `frontend/src/pages/TaskDetail.jsx`
- Add a small helper/test file if needed

### Existing Endpoint

```http
GET /tasks/{task_id}/llm-usage
```

Response includes:

```text
summary.request_count
summary.prompt_tokens
summary.completion_tokens
summary.total_tokens
summary.cache_hit_tokens
summary.cache_miss_tokens
summary.cache_hit_rate
items[]
```

### UI Requirements

On Task Detail show a compact section:

```text
LLM usage
Requests: 2
Total tokens: 1234
Cache hit rate: 68%
Cache hit tokens: 840
Cache miss tokens: 394
```

If no LLM usage:

```text
No LLM usage yet.
```

Rules-mode tasks should not look broken.

### Acceptance Criteria

- Task Detail fetches LLM usage.
- Displays summary when usage exists.
- Displays empty state when no usage exists.
- Does not block loading task if LLM usage request fails; show a local warning
  or omit the section gracefully.

---

## Task 3.3: Copy Debug Report

### Goal

Let the user copy a concise task debug report from Task Detail.

### Scope

Frontend only unless a backend endpoint is preferred later.

### Files

- `frontend/src/pages/TaskDetail.jsx`
- `frontend/src/api.js`
- Optional helper: `frontend/src/debugReport.js`
- Optional test: `frontend/src/debugReport.test.js`

### Debug Report Contents

Include:

```text
Task ID
URL
Status
Profile ID or profile name
Description
Field counts
Required missing fields
Latest screenshots
LLM usage summary
Recent action logs if available
```

If action logs are not currently loaded on Task Detail, either:

- Fetch `GET /tasks/{task_id}/logs`, or
- Leave logs out in this task and include a TODO.

### UI Requirements

Add button:

```text
Copy debug report
```

On click:

- Build text report.
- Copy to clipboard.
- Show success notice.
- If clipboard API fails, show the report in a textarea or error message.

### Acceptance Criteria

- Button exists on Task Detail.
- Report contains task status and URL.
- Report includes screenshot links if available.
- Report includes LLM usage if available.
- Copy failure does not crash page.

---

## Epic 4: LLM Cache and Cost Story

Goal:
Make cache hit rate a visible supporting story for cost/performance, without
pretending it measures mapping quality.

---

## Task 4.1: Benchmark Run Cache Metrics

### Goal

For LLM benchmark runs, show cache hit metrics in benchmark summary.

### Scope

Backend aggregation plus frontend display.

Do this after Task 1.1C and Task 3.2.

### Files

- `backend/app/services/benchmark_runner.py`
- `backend/app/services/llm_usage_service.py` if helper reuse is needed
- `backend/app/routers/benchmarks.py`
- `frontend/src/pages/Benchmarks.jsx`
- `frontend/src/benchmarkPresentation.js`
- Tests as needed

### Requirements

For LLM benchmark runs:

- Track LLM usage generated during that benchmark run.
- Add to `summary_metrics`:

```text
llm_request_count
llm_total_tokens
llm_cache_hit_tokens
llm_cache_miss_tokens
llm_cache_hit_rate
```

For rules runs:

- Display cache metrics as `N/A`.
- Do not invent zero values that imply the cache was measured.

### Important Design Constraint

Benchmark LLM usage should be attributable to benchmark tasks or benchmark run.
If current usage logs are task-based only, document and implement the simplest
safe association:

- Use temporary benchmark task IDs and aggregate usage from those task IDs before
  cleanup, or
- Keep benchmark task records hidden/marked so usage can be aggregated.

Do not mix unrelated user task LLM usage into benchmark metrics.

### Acceptance Criteria

- LLM benchmark summary shows cache hit rate.
- Rules benchmark summary shows `N/A` for cache metrics.
- Running the same LLM benchmark twice can show higher cache hit rate on the
  second run if provider reports cache hit tokens.
- Tests mock usage data. Tests do not call real LLM APIs.

---

## Task 4.2: Warm Cache Benchmark UX

### Goal

Make it easy to demonstrate cache behavior by running the same LLM benchmark
again.

### Scope

Frontend UX around benchmark runs.

### Files

- `frontend/src/pages/Benchmarks.jsx`
- `frontend/src/benchmarkPresentation.js`

### UI Requirements

After an LLM benchmark run completes, show a small hint:

```text
Run the same LLM benchmark again to measure cache reuse.
```

Optional button:

```text
Run again to test cache
```

If implemented, the button should rerun with the same mode/provider.

### Acceptance Criteria

- User can easily rerun the same LLM benchmark.
- UI compares current selected run to previous run when both have cache metrics.
- If comparison is not implemented, at least show the hint and latest cache
  metrics clearly.

---

## Epic 5: Documentation and Portfolio Packaging

Goal:
Make the project easy to understand, run, demo, and discuss in interviews.

---

## Task 5.1: Architecture Documentation

### Goal

Create a professional architecture document.

### Files

- `docs/architecture.md`
- Update `README.md` to link to it

### Required Sections

```text
Overview
System architecture
Data model
Task workflow
Field extraction flow
Rules mapping flow
LLM mapping flow
Cache layers
Human review and safety boundaries
Benchmark/evaluation system
Failure handling
Known limitations
```

### Mermaid Diagram

Include one Mermaid diagram:

```text
React UI -> FastAPI -> Services -> Playwright
                      -> SQLite
                      -> LLM Provider
```

### Key Points to Explain

- LLM does not directly control the browser.
- Playwright only executes backend-validated mapped fields.
- Submit requires explicit user approval.
- Benchmark measures quality; cache metrics measure cost/performance.

### Acceptance Criteria

- Document exists.
- README links to document.
- Mermaid diagram renders as valid Markdown.
- Document matches current codebase.

---

## Task 5.2: Demo Flow Documentation

### Goal

Create a repeatable demo script for interviews.

### Files

- `docs/demo-flow.md`
- Update `README.md` to link to it

### Required Sections

```text
Prerequisites
Backend startup
Frontend startup
LLM provider setup
Demo profile
Demo task
Review Mapping walkthrough
Fill and approval walkthrough
Benchmark walkthrough
What to say in interviews
Fallback plan if API key is missing
Known limitations to mention honestly
```

### Demo Script Requirements

Include a 1-2 minute script:

1. Open Dashboard.
2. Show Profile.
3. Create Task.
4. Analyze and generate mappings.
5. Review Mapping and edit one value.
6. Confirm Mapping and show profile update summary.
7. Fill form and show screenshot.
8. Point out `WAITING_APPROVAL`.
9. Open Benchmarks and explain metrics.

### Acceptance Criteria

- A new developer can follow the document and run the demo.
- Includes commands for backend/frontend.
- Includes explanation for rules mode when no LLM key is available.
- Includes concise interview talking points.

---

## Task 5.3: Safety Boundaries Documentation

### Goal

Document what the agent intentionally does not do.

### Files

- `docs/safety-boundaries.md`
- Update `README.md` to link to it

### Required Sections

```text
Why human-in-the-loop matters
Actions the agent may perform
Actions the agent must not perform
LLM constraints
Manual login policy
CAPTCHA policy
Payment/destructive action policy
Profile memory safety
Submission approval flow
```

### Acceptance Criteria

- Document clearly states no CAPTCHA solving.
- Document clearly states no payment automation.
- Document clearly states no final submit without user approval.
- Document explains why LLM outputs are validated.

---

## Task 5.4: README Portfolio Upgrade

### Goal

Make README presentation stronger after core tasks are complete.

### Files

- `README.md`
- Optional images under `docs/images/`

### Requirements

Add:

- Architecture doc link.
- Demo flow doc link.
- Safety boundaries doc link.
- Benchmark methodology or benchmark results section.
- Screenshots or GIF placeholders.
- Resume bullets.

### README Sections

```text
Project overview
Why this is not a hard-coded script
Features
Architecture
Demo flow
Benchmark/evaluation
Safety boundaries
Local setup
LLM provider setup
Limitations
Resume bullets
```

### Acceptance Criteria

- README looks portfolio-ready.
- README does not overclaim capabilities.
- README makes safety boundaries clear.
- README tells the reader where to start.

---

## How to Use These Tasks

Use this format:

```text
Implement only Task X from IMPLEMENTATION_BACKLOG.md.

Do not implement later tasks.
Follow the files, requirements, acceptance criteria, and tests listed there.
Before coding, inspect the current files mentioned in the task.
After coding, run the relevant tests.
Do not call real LLM APIs in tests.
```

Recommended first implementation request:

```text
Implement Task 1.1A from IMPLEMENTATION_BACKLOG.md.
Only modify the frontend Benchmark page/API helpers as needed.
Do not change backend benchmark runner logic yet.
Run frontend tests if available.
```

Second implementation request:

```text
Implement Task 1.1B from IMPLEMENTATION_BACKLOG.md.
Only modify backend benchmark request validation and endpoint tests.
Do not implement true LLM benchmark execution yet.
Run backend benchmark endpoint tests.
```

Third implementation request:

```text
Implement Task 1.1C from IMPLEMENTATION_BACKLOG.md.
Make LLM benchmark mode use the real LLM mapping path, but mock LLM calls in tests.
Do not add cache hit metrics yet.
Run benchmark runner tests.
```
