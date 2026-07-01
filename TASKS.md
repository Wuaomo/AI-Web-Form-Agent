# Development Roadmap

This roadmap tracks the next engineering milestones for AI Web Form Agent.

Guiding principle:
keep each change focused, measurable, and aligned with the core workflow:
analyze a form, review mappings, fill safely, and evaluate results.

---

## Current Baseline

The project already includes the core end-to-end workflow:

- [x] FastAPI backend
- [x] React/Vite frontend
- [x] SQLite persistence with SQLAlchemy
- [x] Profile CRUD
- [x] Task creation, listing, and detail views
- [x] Dynamic form field extraction
- [x] Rule-based field mapping
- [x] Optional provider-assisted field mapping
- [x] Provider setup hints and fallback behavior
- [x] Review Mapping page
- [x] Manual mapping correction
- [x] Profile write-back after mapping confirmation
- [x] Custom profile values
- [x] Mapping cache
- [x] User mapping override cache
- [x] Form analysis cache
- [x] Playwright browser filling
- [x] Final submission approval checkpoint
- [x] Manual login recovery flow
- [x] Action logs
- [x] Screenshots
- [x] Admin action traces
- [x] Benchmark runner
- [x] Benchmark results page
- [x] Backend pytest coverage
- [x] Frontend Node test coverage

---

## Core Workflow

```text
Profile
  -> Create Task
  -> Analyze Form
  -> Generate Mapping
  -> Review Mapping
  -> Confirm Mapping
  -> Fill Form
  -> Wait for Approval
  -> Submit after explicit approval
```

Task states:

- `CREATED`: task has been created.
- `ANALYZING`: the backend is opening the page and extracting fields.
- `LOGIN_REQUIRED`: the page requires user-controlled login before analysis.
- `LOGIN_IN_PROGRESS`: the user login browser is open.
- `MAPPING_READY`: fields are extracted and ready for mapping review.
- `READY_TO_FILL`: mappings were confirmed by the user.
- `FILLING`: Playwright is filling mapped fields.
- `WAITING_APPROVAL`: the form is filled and waiting before final submission.
- `COMPLETED`: the user approved final submission and the task completed.
- `FAILED`: the workflow hit an unrecovered error.

---

## Milestone 1: Evaluation and Benchmarking

Goal:
make form understanding measurable and repeatable.

- [ ] Record a baseline benchmark score for rules mode.
- [ ] Add benchmark mode selection: rules vs semantic mapping.
- [ ] Add provider selection for semantic benchmark runs.
- [ ] Display summary metrics:
  - [ ] extraction recall
  - [ ] extraction precision
  - [ ] mapping accuracy
  - [ ] required-field coverage
  - [ ] non-fillable rejection rate
  - [ ] login-gate detection
- [ ] Add stable failure reason codes.
- [ ] Show human-readable failure diagnoses in the benchmark UI.
- [ ] Add at least five realistic benchmark fixtures:
  - [ ] multi-section application form
  - [ ] select option mismatch
  - [ ] radio group
  - [ ] checkbox group
  - [ ] address and date fields
- [ ] Add benchmark regression tests.

Deliverable:
a benchmark page that can explain both score and failure reasons.

---

## Milestone 2: Review Mapping Improvements

Goal:
make user review faster, safer, and easier to understand.

- [ ] Add an attention summary at the top of Review Mapping.
- [ ] Highlight required fields that are missing values.
- [ ] Highlight low-confidence mappings.
- [ ] Show optional unmapped fields without blocking confirmation.
- [ ] Display profile updates after mapping confirmation.
- [ ] Display skipped fields and skip reasons.
- [ ] Add per-field profile memory policy:
  - [ ] auto
  - [ ] do not save
  - [ ] force save when safe
- [ ] Prevent sensitive or one-time fields from being saved even when forced.
- [ ] Add frontend tests for review summary logic.
- [ ] Add backend tests for profile memory policy.

Deliverable:
a review screen that clearly shows what needs attention and what will be saved.

---

## Milestone 3: Form Understanding

Goal:
handle more realistic form structures without weakening safety boundaries.

- [ ] Improve select option matching by label and value.
- [ ] Improve radio group extraction and mapping.
- [ ] Improve checkbox group handling.
- [ ] Distinguish consent/action checkboxes from reusable profile fields.
- [ ] Support common address fields:
  - [ ] address line
  - [ ] city
  - [ ] state
  - [ ] zip/postal code
  - [ ] country
- [ ] Support date-like fields:
  - [ ] date
  - [ ] month
  - [ ] year
  - [ ] graduation date
- [ ] Validate that filled values were actually written to the page.
- [ ] Support a second extraction pass for fields that appear dynamically.

Deliverable:
better coverage for common public forms and application-style workflows.

---

## Milestone 4: Observability and Debugging

Goal:
make the workflow explainable when it succeeds or fails.

- [ ] Add an agent timeline to Task Detail.
- [ ] Show the active, completed, blocked, or failed workflow step.
- [ ] Surface action trace summaries in the UI.
- [ ] Show failed selector, field id, error message, and screenshot when
  available.
- [ ] Add a copyable debug report.
- [ ] Show usage and cache summary for semantic mapping runs.
- [ ] Link benchmark failures to fixture and expected-answer files where useful.
- [ ] Add clear next-step suggestions for failed tasks.

Deliverable:
Task Detail can explain what happened, what failed, and what the user can do.

---

## Milestone 5: Safe Real-World Readiness

Goal:
support controlled real-world testing without expanding into unsafe automation.

- [ ] Improve manual login guidance.
- [ ] Reuse Playwright storage state for user-controlled sessions.
- [ ] Add benchmark coverage for login-gate detection.
- [ ] Add optional URL allowlist/blocklist configuration.
- [ ] Hard-block payment, purchase, delete, and destructive workflows.
- [ ] Detect CAPTCHA or bot challenges and mark them unsupported.
- [ ] Document recommended low-risk test targets.

Out of scope:

- [ ] CAPTCHA solving
- [ ] bulk submissions
- [ ] payment automation
- [ ] login bypassing
- [ ] multi-user account management
- [ ] cloud browser clusters

Deliverable:
safer handling of real websites while keeping the project focused.

---

## Milestone 6: Portfolio Packaging

Goal:
make the repository easy to understand, run, and discuss.

- [ ] Add `docs/architecture.md`.
- [ ] Add `docs/demo-flow.md`.
- [ ] Add `docs/safety-boundaries.md`.
- [ ] Add `docs/benchmark-methodology.md`.
- [ ] Capture screenshots:
  - [ ] Dashboard
  - [ ] Profiles
  - [ ] Review Mapping
  - [ ] Task Detail with screenshot evidence
  - [ ] Benchmarks
- [ ] Add benchmark baseline results to README.
- [ ] Add architecture diagram to README or docs.
- [ ] Record a 1-2 minute demo video.
- [ ] Keep README focused on outcomes, architecture, safety, and evaluation.

Deliverable:
a portfolio-ready repository with clear technical depth and honest boundaries.

---

## Recommended Next Steps

Start with the smallest high-impact sequence:

1. Add benchmark mode/provider selection.
2. Add benchmark summary metrics and failure reason labels.
3. Add realistic benchmark fixtures.
4. Add Review Mapping attention summary.
5. Add Task Detail timeline and usage summary.
6. Write architecture and demo documentation.
