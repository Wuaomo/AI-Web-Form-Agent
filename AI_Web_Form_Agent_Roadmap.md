# AI Web Form Agent Roadmap

This roadmap describes how the project evolves from a working browser
automation demo into a more complete, measurable, and review-first form
automation system.

The main focus is not adding broad product surface area. The focus is improving
reliability, explainability, safety, and presentation.

---

## 1. Project Positioning

AI Web Form Agent is a local browser automation system for controlled form
filling workflows.

The system:

- discovers form fields dynamically instead of relying on hard-coded selectors;
- maps reusable profile data to extracted fields;
- gives the user a review step before execution;
- fills the page through a real Playwright browser session;
- records screenshots, logs, traces, and benchmark results;
- pauses before final submission.

The project is intentionally scoped. It does not attempt to bypass login,
solve CAPTCHA, automate payments, or submit forms without approval.

---

## 2. Completed Foundation

### Backend

- FastAPI application
- SQLAlchemy and SQLite persistence
- Profile, Task, FormField, Screenshot, ActionLog, and benchmark models
- Dynamic form extraction
- Rule-based field mapping
- Optional provider-assisted semantic mapping
- Provider configuration detection and setup hints
- Mapping cache
- User mapping override cache
- Form analysis cache
- Safe profile write-back after mapping confirmation
- Playwright browser execution
- Manual login recovery flow
- Benchmark runner
- Admin action trace endpoint

### Frontend

- Dashboard
- Profiles
- Create Task
- Task Detail
- Review Mapping
- Benchmarks
- Provider selection for mapping
- Mapping review and manual correction
- Profile update summary
- Screenshot display
- Status-based task action flow

### Testing and Evaluation

- Backend pytest coverage
- Frontend Node test coverage
- Local benchmark fixtures
- Expected benchmark answers
- Persisted benchmark run history

---

## 3. Recommended Development Sequence

The strongest next sequence is:

```text
Benchmark Evaluation
  -> Mapping Accuracy
  -> Review Experience
  -> Observability
  -> Documentation and Demo Packaging
```

This keeps development grounded in measurable improvements instead of expanding
into unrelated features.

---

## Phase A: Benchmark Evaluation

### Goal

Measure whether form discovery and field mapping are improving over time.

### Planned Work

- Add benchmark mode selection:
  - rules
  - semantic mapping
- Add provider selection for semantic benchmark runs.
- Display summary metrics:
  - extraction recall
  - extraction precision
  - mapping accuracy
  - required-field coverage
  - non-fillable rejection
  - login-gate detection
- Add stable failure reason codes.
- Add realistic benchmark cases:
  - multi-section forms
  - select option mismatch
  - radio groups
  - checkbox groups
  - address and date fields
- Add regression tests for benchmark loading and scoring.

### Outcome

The project can show repeatable quality metrics rather than relying on a single
demo path.

---

## Phase B: Review Mapping Experience

### Goal

Make the human review step faster and more transparent.

### Planned Work

- Add an attention summary for required missing fields.
- Highlight low-confidence mappings.
- Show optional unmapped fields without blocking confirmation.
- Display profile updates after confirmation.
- Display skipped fields and clear skip reasons.
- Add per-field profile memory policy:
  - auto
  - do not save
  - force save when safe
- Ensure sensitive fields are never saved as reusable profile data.

### Outcome

Users can quickly understand what needs review and what will be saved for reuse.

---

## Phase C: Form Understanding

### Goal

Improve coverage for realistic public forms and application-style workflows.

### Planned Work

- Improve select option matching by label, value, and partial match.
- Improve radio group extraction and mapping.
- Improve checkbox group handling.
- Distinguish consent/action checkboxes from reusable fields.
- Add common address field support.
- Add date and graduation-date field support.
- Verify that values were actually written after browser execution.
- Support a second extraction pass for dynamic follow-up fields.

### Outcome

The agent handles a wider range of real form patterns while keeping the same
review and safety model.

---

## Phase D: Observability and Debugging

### Goal

Make task execution understandable when it succeeds and diagnosable when it
fails.

### Planned Work

- Add a timeline to Task Detail.
- Show current, completed, blocked, and failed workflow steps.
- Surface action trace summaries.
- Show failed selector, field id, error message, and screenshot when available.
- Add a copyable debug report.
- Show usage and cache summary for semantic mapping runs.
- Link benchmark failures to fixture and expected-answer data where useful.

### Outcome

The application can explain what happened during a run instead of only showing a
final status.

---

## Phase E: Portfolio Packaging

### Goal

Make the repository easy to evaluate quickly.

### Planned Work

- Add architecture documentation.
- Add demo-flow documentation.
- Add safety-boundary documentation.
- Add benchmark-methodology documentation.
- Add screenshots or a short demo video.
- Keep README concise and outcome-focused.

### Outcome

The repository communicates its engineering value without requiring a long live
walkthrough.

---

## Out of Scope

The project intentionally avoids:

- CAPTCHA solving
- anti-bot bypassing
- bulk submissions
- payment or purchase automation
- destructive action automation
- multi-user account management
- cloud browser orchestration
- broad scraping workflows

These boundaries keep the project focused on safe, review-first form
automation.
