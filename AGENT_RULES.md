# Agent Rules

Project:
AI Web Form Agent

Purpose:
Maintain a review-first AI workflow automation app that can analyze web forms,
map reusable profile data to fields, plan safe tool use, fill the page in a real
browser, record evidence, and pause before final submission.

---

## Product Boundaries

The project is a controlled local workflow automation demo, not a bulk
submission, scraping, or production browser-fleet platform.

The core workflow is:

```text
discover fields
  -> plan workflow
  -> map profile data
  -> review and correct values
  -> apply policy gates
  -> fill in browser
  -> verify fields and record traces
  -> wait for explicit approval
```

The system should remain focused on:

- dynamic form discovery;
- reusable profile data;
- user-reviewed mappings;
- deterministic planning and tool selection;
- policy and approval gates;
- safe browser execution;
- screenshots, logs, verification evidence, and traces;
- workflow memory for reviewed reusable values;
- benchmark-based evaluation.

---

## Architecture

```text
React Frontend
  -> FastAPI Backend
    -> Workflow Templates
    -> Planner + Tool Registry
    -> Form Extraction
    -> Field Mapping
    -> Policy Engine + Approval Gates
    -> Browser Execution
    -> Verification + Trace Recording
    -> SQLite Persistence
```

Primary backend modules:

- `workflow_templates`: declares workflow types; only `form_fill` should be enabled by default.
- `PlannerService` and `ToolRegistry`: build deterministic, inspectable workflow plans.
- `PolicyEngine` and `ApprovalGateService`: block unsafe actions and persist required review gates.
- `FormExtractor`: extracts fields, labels, hints, options, and login gates.
- `FieldMapper`: maps extracted fields to supported profile keys.
- `BrowserExecutor`: fills mapped fields and captures screenshots.
- `BenchmarkRunner`: evaluates extraction and mapping quality.
- `MappingCache`: reuses stable mapping results.
- `ActionTraceService`: records detailed browser execution traces.
- `WorkflowTraceService`: records workflow-level spans and evidence.
- `WorkflowMemory`: stores only reviewed, reusable, non-sensitive memory.

Persistent data:

- profiles
- tasks
- jobs
- workflow plans
- workflow traces
- approval requests
- form fields
- screenshots
- action logs
- mapping caches
- benchmark runs
- admin action traces
- workflow memory

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
4. Planner creates an inspectable plan for the enabled workflow.
5. Mapping is generated through rules or an optional semantic provider.
6. Policy checks classify blocked, review-required, and allowed actions.
7. User reviews and confirms mappings.
8. Safe reusable values may be written back to profile/workflow memory.
9. Browser execution fills the page.
10. Verification records field-level evidence, screenshots, and trace spans.
11. The task stops before final submission.
12. User explicitly confirms final submission if appropriate.

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
- Workflow memory must not store sensitive, one-time, consent, auth, CAPTCHA, or
  payment values.
- Disabled workflow templates must stay disabled unless their safety model,
  tests, and UI review flow are implemented.

---

## Scope Rules

Keep the project focused and portfolio-ready:

- Prefer one complete workflow over many partial features.
- Keep changes small and testable.
- Preserve existing safety boundaries.
- Keep code readable for a reviewer who has not seen the project before.
- Avoid unrelated infrastructure such as multi-user account systems, cloud
  browser fleets, broad scraping features, or production auth.
- Prefer improving the enabled `form_fill` workflow before expanding disabled
  workflow templates.
- Keep optional LLM providers optional; the local demo must work without API
  keys.
- Add tests when changing behavior.

---

## Preferred Expansion Order

1. Reliability of the enabled form-fill workflow.
2. Mapping review clarity, memory controls, and approval UX.
3. Trace, usage, debug, and verification evidence.
4. Benchmark/evaluation accuracy and regression reporting.
5. Documentation, Docker demo, and CI polish.
