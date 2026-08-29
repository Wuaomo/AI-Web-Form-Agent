# Agent Rules

Project:
AI Web Form Agent

Purpose:
Maintain a review-first AI browser workflow assistant. Form filling remains the
first concrete workflow, but the project should grow toward reading pages,
extracting structured information, using reviewed memory, taking reviewed
browser actions, measuring behavior, and explaining failures.

Primary instruction entry point:
Read `AGENTS.md` first. This file provides the longer project boundary and
architecture notes.

---

## Current Roadmap

Use `docs/roadmap/` as the source of truth for future development.

The new JD-aligned project direction is:

1. Browser Workflow Assistant
2. Retrieval Memory Layer
3. Evaluation Workbench
4. Agent Observability
5. Portfolio Packaging

Post-portfolio extension order:

6. Domain Workflow Templates
7. Retrieval Quality and Memory Governance
8. Agent Reliability Benchmark Suite

Do not resurrect the old `docs/trae-upgrade`, `docs/superpowers/plans`, or
`docs/superpowers/specs` phase systems.

---

## Product Boundaries

The project is a controlled local browser workflow assistant, not a bulk
submission, scraping, or production browser-fleet platform.

The current concrete workflow is:

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

The target runtime direction is more general:

```text
user goal
  -> agent planner
  -> typed tool calls
  -> governance decision per tool call or proposed action
  -> review queue for proposals that need human judgment
  -> approved browser execution
  -> verification, traces, and benchmark evidence
```

Workflow templates should provide planning hints, default tool sets, demo
presets, and policy defaults. They should not force every future task into a
hardcoded end-to-end workflow.

The system should remain focused on:

- clear user workflows before diagnostic panels;
- dynamic form discovery;
- page extraction and structured summaries;
- security/compliance-style questionnaire workflows;
- reusable profile data;
- user-reviewed mappings;
- retrieval-backed memory from reviewed corrections;
- source-backed suggestions from reviewed memory or local policy fixtures;
- deterministic planning and tool selection;
- policy and approval gates;
- safe browser execution;
- screenshots, logs, verification evidence, and traces;
- benchmark-based evaluation;
- portfolio-ready explanation, demo, and limitations.

---

## Architecture

Current architecture:

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

Target architecture:

```text
React Frontend
  -> FastAPI Backend
    -> Agent Runtime API
    -> Agent Planner
    -> Tool Registry
    -> Tool Runtime
    -> Governance Engine
    -> Review Queue
    -> Browser Executor
    -> Evidence Retrieval
    -> Verification Service
    -> Trace Store
    -> Evaluation Harness
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

Target runtime concepts:

- `AgentRun`: the user goal, target URL, context, plan, status, and result.
- `AgentPlan`: an inspectable list of planned tool calls, not a hardcoded workflow script.
- `ToolCall` and `ToolResult`: the typed execution contract for internal,
  browser, MCP, and OpenAPI tools.
- `Proposal`: an agent suggestion that may need review, such as a field value,
  answer, memory write, browser click, or submit action.
- `EvidenceItem`: source-backed support for a proposal.
- `ReviewDecision`: the user's approve, edit, reject, or needs-more-evidence
  decision.
- `GovernanceDecision`: action-level allow, review, approval, verify, or block
  classification.
- `VerificationResult`: evidence that an approved action changed the browser or
  external state as expected.

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
- Prefer user-path clarity before adding more observability UI.
- Keep advanced/debug evidence collapsed by default unless it explains a failure.
- Keep optional LLM providers optional; the local demo must work without API
  keys.
- Add tests when changing behavior.

---

## Preferred Expansion Order

1. Agent Runtime Schemas: introduce shared Pydantic models for runs, plans,
   tool calls, proposals, evidence, review decisions, governance decisions, and
   verification results.
2. Executable Tool Runtime: wrap existing services as typed tools before adding
   new agent behavior.
3. Action-Level Governance: evaluate each tool call or proposed action before
   execution.
4. Proposal Review Queue: generalize field mapping review into reviewable
   proposals with evidence.
5. Governed Agent Graph: move from single-scenario LangGraph paths toward a
   reusable pause/resume runtime.
6. Optional LLM Planner: add structured model-driven planning without breaking
   deterministic no-key mode.
7. External Tool Adapters: add MCP and OpenAPI tools through the same Tool
   Runtime and governance path, starting with read-only tools.
8. Run Cockpit UI: replace workflow-specific surfaces gradually with run, plan,
   tool call, proposal, evidence, and verification views.
