# Project Guardrails

Project:
AI Web Form Agent

Purpose:
Build a review-first browser automation system that can analyze web forms,
map reusable profile data to fields, fill the page in a real browser, and pause
before final submission.

---

## Product Boundaries

The project is a controlled local automation workflow, not a bulk submission or
web scraping platform.

The core workflow is:

```text
discover fields
  -> map profile data
  -> review and correct values
  -> fill in browser
  -> wait for explicit approval
```

The system should remain focused on:

- dynamic form discovery;
- reusable profile data;
- user-reviewed mappings;
- safe browser execution;
- screenshots, logs, and traces;
- benchmark-based evaluation.

---

## Architecture

```text
React Frontend
  -> FastAPI Backend
    -> Form Extraction
    -> Field Mapping
    -> Browser Execution
    -> SQLite Persistence
```

Primary backend modules:

- `FormExtractor`: extracts fields, labels, hints, options, and login gates.
- `FieldMapper`: maps extracted fields to supported profile keys.
- `BrowserExecutor`: fills mapped fields and captures screenshots.
- `BenchmarkRunner`: evaluates extraction and mapping quality.
- `MappingCache`: reuses stable mapping results.
- `ActionTraceService`: records detailed browser execution traces.

Persistent data:

- profiles
- tasks
- form fields
- screenshots
- action logs
- mapping caches
- benchmark runs
- admin action traces

---

## Task Workflow

Supported task states:

- `CREATED`
- `ANALYZING`
- `LOGIN_REQUIRED`
- `LOGIN_IN_PROGRESS`
- `MAPPING_READY`
- `READY_TO_FILL`
- `FILLING`
- `WAITING_APPROVAL`
- `COMPLETED`
- `FAILED`

Expected flow:

1. User creates or selects a profile.
2. User creates a task with a target URL.
3. Backend analyzes the page and extracts fields.
4. Mapping is generated through rules or an optional semantic provider.
5. User reviews and confirms mappings.
6. Safe reusable values may be written back to the profile.
7. Browser execution fills the page.
8. The task stops before final submission.
9. User explicitly confirms final submission if appropriate.

---

## Safety Rules

Required behavior:

- Never auto-submit a form without explicit user approval.
- Never automate payments, purchases, deletes, or destructive actions.
- Never solve CAPTCHA or bypass anti-bot controls.
- Never bypass login or guess credentials.
- Never save passwords, OTPs, payment card values, or one-time consent values as
  reusable profile data.
- Manual login support must be user-controlled.
- Provider-assisted mapping may suggest field matches, but backend validation
  and user review remain required before browser execution.

---

## Scope Rules

Keep the project focused and portfolio-ready:

- Prefer one complete workflow over many partial features.
- Keep changes small and testable.
- Preserve existing safety boundaries.
- Keep code readable for a reviewer who has not seen the project before.
- Avoid unrelated infrastructure such as multi-user account systems, cloud
  browser fleets, RAG pipelines, or broad scraping features.
- Add tests when changing behavior.

---

## Preferred Expansion Order

1. Benchmark reliability and failure diagnosis.
2. Review Mapping clarity and profile-memory controls.
3. Select, radio, checkbox, address, and date-field support.
4. Task timeline, usage summary, and debug report.
5. Architecture, demo, benchmark, and safety documentation.
