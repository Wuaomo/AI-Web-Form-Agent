# Agent Runtime Optimization Guide

## Purpose

This guide explains how to evolve AI Web Form Agent from a review-first form
workflow demo into a cleaner, more professional browser workflow agent system.

The goal is not to add a large AI framework first. The goal is to make the
current stack look and behave like a small agent runtime:

```text
read browser state
  -> plan a safe workflow
  -> select an inspectable tool
  -> apply policy and approval gates
  -> execute in the browser
  -> verify the result
  -> record evidence
  -> improve future runs through reviewed memory
```

## Positioning

Use this project story:

```text
A full-stack, review-first browser workflow assistant that safely reads pages,
suggests actions with evidence, requires human approval, executes browser
steps, verifies results, and measures reliability.
```

Do not reposition the project as:

- a generic autonomous browser agent;
- a bulk form submission system;
- a scraping platform;
- a chatbot;
- a cloud browser fleet;
- a LangChain or LangGraph demo.

Frameworks can be added later as adapters. The project should first own its
core safety, review, trace, verification, and benchmark model.

## Current Stack Decision

Keep the current stack:

- FastAPI for backend APIs and workflow orchestration.
- Pydantic-style schemas for data contracts.
- SQLAlchemy and SQLite for local persistence.
- Playwright for browser execution.
- React and Vite for the frontend.
- Local benchmark fixtures for evaluation.

Avoid adding these until there is a concrete trigger:

- LangChain or LangGraph as a core runtime.
- browser-use as a production dependency.
- vector databases.
- distributed queues.
- multi-user auth.
- cloud browser infrastructure.
- broad scraping or CAPTCHA handling.

## Near-Term Optimization Guide

Timeframe: 1-2 weeks.

Goal: make the current codebase more schema-driven, inspectable, and reliable
without changing the product surface too much.

### 1. Finish Tool Registry Metadata

Current direction:

- `ToolDefinition` has `params_schema`, `preconditions`, and `produces`.
- Serialized workflow plans include tool runtime metadata.

Next metadata to add:

```text
failure_modes
recovery_hint
evidence_required
approval_reason
```

Example:

```python
ToolDefinition(
    name="fill_form",
    description="Fill mapped values into the extracted form.",
    risk_level="medium",
    requires_approval=False,
    implemented=True,
    params_schema={...},
    preconditions=["mapping_confirmed", "policy_passed"],
    produces=["filled_fields", "verification_candidates"],
    failure_modes=["selector_missing", "option_value_mismatch", "timeout"],
    recovery_hint="Return to review if fields cannot be filled or verified.",
    evidence_required=["action_trace", "field_verification"],
    approval_reason=None,
)
```

Implementation notes:

- Keep metadata in `backend/app/services/tool_registry.py`.
- Keep `planner_service.py` as a reader of registry metadata, not a second
  source of truth.
- Do not add dynamic tool execution yet.
- Do not add decorators until there are enough executable tools to justify
  them.

Acceptance criteria:

- Every implemented tool has runtime metadata.
- Unimplemented tools remain visible but do not pretend to be executable.
- Tests assert implemented tools expose required metadata.
- Planner output remains deterministic.

Suggested tests:

- `backend/tests/test_tool_registry.py`
- `backend/tests/test_planner_service.py`
- `backend/tests/test_workflow_plan_endpoint.py`

### 2. Add an AgentStep Presentation Model

Create a unified presentation model for the frontend timeline. Start in the
service or presentation layer before changing database tables.

Target fields:

```text
step_id
goal
tool
status
input_summary
output_summary
error
recovery_hint
evidence
screenshot_id
started_at
finished_at
```

Data sources:

- workflow plan steps;
- workflow spans;
- action traces;
- screenshots;
- field verification results;
- approval requests;
- agent reviews.

Implementation notes:

- Prefer a pure function that assembles timeline items for a task.
- Keep sensitive raw values out of summaries.
- Treat this as a view model, not a new workflow engine.

Acceptance criteria:

- A task can expose a step-by-step agent timeline.
- Each step explains what happened and what evidence exists.
- Failed steps show a practical recovery hint.
- Debug details remain collapsed by default.

Suggested tests:

- backend timeline assembly test;
- frontend presentation helper test;
- endpoint test if a new API is added.

### 3. Build the Agent Step Timeline UI

The UI should make the agent understandable without turning the app into a
dashboard.

Each timeline row should show:

- step goal;
- tool/action name;
- status;
- short result;
- screenshot or evidence link when available;
- failure or recovery hint when relevant.

Design constraints:

- Keep advanced trace JSON collapsed.
- Do not duplicate the whole benchmark or admin trace UI.
- Prioritize task review and task recovery.

Acceptance criteria:

- The user can understand the workflow path from Task Detail.
- A failed run has enough context to explain the failure.
- Successful runs show verification evidence before final approval.
- The local demo still fits a 3-5 minute walkthrough.

Suggested tests:

- `frontend/src/agentTimeline.test.js`
- `frontend/src/workflowTracePresentation.test.js`
- `frontend/src/taskRunState.test.js`
- `cd frontend && npm test && npm run build`

### 4. Add Lightweight Reliability Detection

Start with deterministic checks. Do not add an AI recovery agent yet.

Signals to detect:

```text
same selector failed repeatedly
same action repeated without progress
page URL unchanged after navigation/click
field value unchanged after fill
Playwright timeout
verification mismatch
missing approval gate
```

Output:

```text
failure_reason
recovery_hint
recommended_next_state
evidence
```

Recommended behavior:

- Do not auto-recover by clicking more things.
- Move risky or repeated failures to human review.
- Record the signal in trace data and benchmark reports.

Acceptance criteria:

- Repeated browser failures become visible in Task Detail.
- Reliability signals do not bypass approval gates.
- Benchmark reports can count common failure reasons.

Suggested tests:

- browser executor failure tests;
- workflow state transition tests;
- benchmark failure taxonomy tests.

### 5. Add an LLM Client Boundary

Keep optional LLM behavior, but prevent provider calls from leaking through the
business logic.

Target interface:

```text
complete_json
summarize
classify
suggest_mapping
```

Implementation notes:

- Start as a thin wrapper around existing provider config and services.
- Keep rules-mode behavior independent of LLM availability.
- Capture provider, model, latency, token usage, and cost when available.
- Validate JSON at the boundary.

Acceptance criteria:

- Business services do not need to know provider-specific SDK details.
- LLM failures degrade to review-required behavior.
- Local demo still works without API keys.

## Medium-Term Direction

Timeframe: 3-8 weeks.

Goal: make the product a complete review-first browser workflow assistant, not
just a safer form filler.

### 1. Complete Page Workflow Support

Move beyond form fill while keeping the same controlled flow:

```text
open page
extract structured content
identify required information
suggest action or answer
show evidence
request review
execute safe browser step
verify or save result
```

Priority workflows:

1. Security questionnaire.
2. Vendor onboarding.
3. Job or research summary.
4. Web data extraction.

Avoid many shallow templates. Two polished workflows are better than six
partial ones.

### 2. Make Reviewed Memory a First-Class Feature

Memory should prove learning from reviewed corrections, not store everything.

Expand memory around:

- reviewed field mappings;
- reviewed questionnaire answers;
- source evidence;
- stale status;
- last used timestamp;
- disable/delete controls;
- refusal history for unsupported questions.

Rules:

- Never store passwords, payment data, OTPs, CAPTCHA values, or one-time
  consent values.
- Stale memory can be shown as evidence but should not auto-fill.
- Every reused suggestion needs source context.

Acceptance criteria:

- A correction improves a later run.
- The UI shows where a memory suggestion came from.
- The benchmark can compare rules-only and memory-assisted behavior.

### 3. Add Workflow Replay

Replay should reuse a reviewed workflow trace with new safe inputs.

Replay scope:

- local fixtures first;
- successful reviewed form/questionnaire flows;
- variable substitution for safe profile values;
- field verification after replay.

Do not replay:

- login flows;
- CAPTCHA;
- payment;
- destructive actions;
- final submission without explicit approval.

Acceptance criteria:

- A saved successful workflow can be replayed against a fixture.
- Replay output links to trace and verification evidence.
- Replay failures produce a failure reason and recovery hint.

### 4. Strengthen the Evaluation Workbench

Benchmark modes should compare system behavior, not just model output.

Modes:

```text
rules
rules + memory
LLM
LLM + memory
replay
```

Metrics:

- workflow success rate;
- safety pass rate;
- verification pass rate;
- approval-gate coverage;
- memory hit rate;
- source evidence coverage;
- unsupported-answer refusal rate;
- failure reason distribution;
- latency and estimated cost.

Acceptance criteria:

- Benchmarks run without LLM API keys.
- Reports show top failures and recommended fixes.
- Memory-assisted runs can be compared to rules-only runs.
- Safety regressions are visible.

### 5. Tighten Frontend Information Architecture

Recommended pages:

```text
Create Task
Review Mapping
Task Detail / Agent Timeline
Approval Center
Memory
Benchmarks
Workflow Templates
```

Rules:

- Keep debug data collapsed.
- Do not add more panels unless they improve the user path.
- Make failure explanation and human review easier than raw observability.

## Long-Term Direction

Timeframe: 2-4 months and beyond.

Goal: add external agent frameworks only when the system needs them, and keep
the project's safety model as the source of truth.

### 1. Add a LangGraph Runtime Adapter When Needed

Prefer LangGraph over plain LangChain when these triggers appear:

- workflows have many branches;
- tool selection is no longer fixed;
- tasks need checkpoint and resume;
- human review happens at multiple graph nodes;
- agent recovery becomes stateful;
- multiple specialist agents share workflow state.

Target shape:

```text
WorkflowRuntime
  -> DeterministicRuntime
  -> LangGraphRuntime
```

The LangGraph adapter should reuse:

- ToolRegistry;
- PolicyEngine;
- ApprovalGateService;
- BrowserExecutor;
- WorkflowTraceService;
- WorkflowMemory;
- BenchmarkRunner.

Do not let LangGraph own safety policy or browser execution directly.

### 2. Upgrade Memory into a RAG Layer

Add embeddings only after text search and deterministic retrieval are visibly
insufficient.

Trigger conditions:

- policy documents grow beyond local fixtures;
- questionnaire answer retrieval needs semantic matching;
- source snippets and citations become central to the demo;
- retrieval quality needs its own benchmark.

Possible additions:

- embedding generation;
- reranking;
- source snippets;
- retrieval confidence explanation;
- retrieval benchmark fixtures.

Keep SQLite as the source of truth unless scale forces a vector database.

### 3. Expand Domain Workflow Templates

Long-term templates should be narrow and portfolio-friendly:

- security questionnaire;
- vendor onboarding;
- compliance intake;
- job application review;
- research summary extraction.

Each template must define:

- enabled status;
- workflow plan;
- safety gates;
- expected inputs;
- verification rules;
- benchmark fixtures.

Do not add a template unless it has a safety model, UI review path, and tests.

### 4. Build an Agent Reliability Suite

Reliability should become the project's strongest proof point.

Suite contents:

- local HTML fixtures;
- expected extraction and mapping outputs;
- replay scenarios;
- failure taxonomy;
- screenshot evidence;
- benchmark reports;
- regression comparison.

Long-term metrics:

- task completion rate;
- refusal correctness;
- unsafe action block rate;
- review-required accuracy;
- recovery success rate;
- memory improvement rate;
- trace coverage.

### 5. Package the Portfolio Story

Final portfolio narrative:

```text
I built a review-first browser workflow assistant with deterministic planning,
schema-driven tools, policy gates, reviewed memory, Playwright execution,
verification evidence, timeline observability, and reliability benchmarks.
```

Required artifacts:

- README positioning;
- architecture diagram;
- safety model;
- demo script;
- screenshots or GIF;
- benchmark report;
- memory improvement example;
- known limitations;
- future LangGraph adapter plan.

## Dependency Policy

Add a dependency only when it removes more complexity than it adds.

Good reasons:

- the dependency replaces fragile custom infrastructure;
- the need appears in at least two workflows;
- tests prove the integration;
- local no-key demo still works;
- failure modes remain review-first.

Bad reasons:

- it looks good on a resume;
- it may be useful later;
- it hides unclear architecture;
- it turns deterministic workflow into uncontrolled tool loops.

## Suggested Branch Sequence

Use small branches:

```text
codex/tool-registry-runtime-metadata
codex/agent-step-timeline
codex/reliability-detector
codex/llm-client-adapter
codex/workflow-replay
codex/memory-evidence-upgrade
codex/benchmark-reliability-reporting
```

Each branch should include:

- focused code changes;
- tests for changed behavior;
- no new dependencies unless justified;
- updated docs only when behavior or positioning changes.

## Definition of Done

A feature is done only when:

- the user path works locally;
- rules-mode still works without LLM API keys;
- safety gates are preserved;
- screenshots, trace, or verification evidence exist when relevant;
- backend tests pass for backend changes;
- frontend tests and build pass for frontend changes;
- documentation reflects the real behavior.

## Recommended Next Step

Build `AgentStep` timeline aggregation next.

Why:

- it reuses existing plan, trace, screenshot, approval, and verification data;
- it improves the user path immediately;
- it makes future replay and benchmarks easier;
- it shows the project as an agent workflow system without adding a framework.

Minimum implementation:

```text
backend timeline assembler
Task Detail timeline response
frontend timeline presentation helper
Task Detail timeline UI
tests for success and failure cases
```

Skipped for now: dynamic LangGraph runtime, vector database, browser-use
dependency, and autonomous click recovery. Add them only when fixed workflows,
review gates, and local benchmarks are no longer enough.
