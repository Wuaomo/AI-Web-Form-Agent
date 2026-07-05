# Phase 00 - Product Positioning And Target Architecture

## Goal

Reposition the project from an "AI web form filler" into a **review-first AI workflow automation platform for structured web tasks**.

The existing form-filling flow remains the first production workflow, but the target architecture must support additional structured browser workflows such as web data extraction, job applications, and admin/data-entry operations.

## Why This Matters

For an AI Engineer internship portfolio, "calls an LLM to fill forms" is too narrow. The professional signal should be:

- goal-to-workflow decomposition
- tool-based browser automation
- human approval checkpoints
- deterministic policy enforcement
- traceable execution
- measurable evaluation
- reusable workflow memory

The project should demonstrate that AI is used inside a controlled system, not trusted blindly.

## Target Product Statement

Use this wording in README and portfolio materials:

> A review-first AI workflow automation platform for structured web tasks. It turns user goals into auditable browser workflows, combines LLM reasoning with deterministic policy checks, pauses for human approval on risky actions, executes through Playwright, verifies outcomes, and evaluates every run through trace-based benchmarks.

Short version:

> Review-first AI browser workflow automation.

## Current Code To Read

Before implementing later phases, read these files:

- `README.md`
- `backend/app/main.py`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/routers/tasks.py`
- `backend/app/services/form_extractor.py`
- `backend/app/services/field_mapper.py`
- `backend/app/services/browser_executor.py`
- `backend/app/services/agent_coordinator.py`
- `backend/app/services/job_queue.py`
- `backend/app/services/job_worker.py`
- `frontend/src/App.jsx`
- `frontend/src/api.js`
- `frontend/src/pages/TaskDetail.jsx`
- `frontend/src/pages/ReviewMapping.jsx`
- `frontend/src/pages/Benchmarks.jsx`

## Existing Strengths To Preserve

- FastAPI backend and React/Vite frontend are already clean enough to extend.
- SQLite is acceptable for portfolio/local demo. Do not add Postgres unless a later deployment phase explicitly needs it.
- Playwright is the correct automation engine.
- Human review before final submission is a major product differentiator.
- Benchmark cases already exist and should be extended, not replaced.
- Existing task statuses and pages should keep working while the new workflow vocabulary is introduced.

## Target Architecture

```text
User Goal
  -> Workflow Template Selection
  -> Planner
  -> Policy Engine
  -> Approval Gate
  -> Tool Executor
  -> Browser / LLM / Retrieval Tools
  -> Verification
  -> Trace + Logs + Screenshots
  -> Evaluation
  -> Workflow Memory
```

## Core Concepts

### WorkflowTemplate

A reusable definition of a workflow type.

Examples:

- `form_fill`
- `web_data_extract`
- `data_entry`
- `job_application`

Each template defines:

- name
- description
- ordered step ids
- default approval policy
- supported tools
- expected inputs
- expected outputs

### WorkflowRun

One execution instance of a workflow template.

In the current project, `Task` is the closest existing concept. Early phases should extend `Task` instead of replacing it. A later cleanup may rename or split it only when the project is stable.

### WorkflowStep

A planned unit of work within a run.

Example:

```json
{
  "step_id": "map_fields",
  "tool": "map_fields",
  "reason": "Map extracted form fields to profile values",
  "requires_approval": false,
  "status": "PENDING"
}
```

### WorkflowTrace

The audit trail for a run.

Every meaningful operation should write a trace span:

- planner call
- policy check
- LLM call
- retrieval call
- browser action
- screenshot capture
- verification result
- user approval decision

## Target Workflow Loop

```text
Goal
  -> Plan
  -> Check Policy
  -> Request Approval if needed
  -> Execute Tool
  -> Verify Result
  -> Write Trace
  -> Continue or Stop
```

## Workflow Types

### Form Fill Workflow

This is the current core flow:

```text
open_url
extract_form
map_fields
review_mapping
confirm_mapping
fill_form
verify_fields
wait_for_submit_approval
submit_form
```

### Web Data Extraction Workflow

New future workflow:

```text
open_url
extract_dom
identify_target_data
extract_structured_json
review_extraction
save_result
```

### Data Entry Workflow

New future workflow:

```text
open_url
extract_form
map_structured_record
review_mapping
fill_form
verify_fields
save_or_submit_after_approval
```

### Job Application Workflow

Specialized extension of form fill:

```text
open_url
detect_login_gate
extract_job_context
extract_application_form
map_profile_and_resume_context
review_mapping
fill_form
verify_fields
wait_for_submit_approval
submit_form
```

## System Boundaries

### AI May Do

- propose plans
- map fields
- classify risk
- summarize traces
- suggest fixes
- generate evaluation reports
- retrieve and reuse historical examples

### AI Must Not Do

- submit forms without approval
- bypass CAPTCHA or anti-bot systems
- store passwords, OTPs, payment details, or one-time consent as reusable memory
- execute destructive actions without deterministic policy checks
- directly call browser tools outside the registered tool executor

## Out Of Scope For All Phases Unless Explicitly Requested

- CAPTCHA solving
- stealth browser or anti-bot bypass
- payment automation
- password manager functionality
- autonomous purchase/delete workflows
- multi-tenant authentication
- cloud deployment with real secrets
- replacing SQLite with a production database

## Naming Direction

Use these names in new code:

- `workflow_type`
- `workflow_status`
- `WorkflowTemplate`
- `WorkflowStep`
- `WorkflowTrace`
- `WorkflowSpan`
- `ApprovalRequest`
- `PolicyDecision`
- `ToolCall`
- `WorkflowMemory`

Keep existing `Task` naming where replacing it would cause unnecessary churn.

## Global Engineering Constraints

- Prefer extending existing services before adding new frameworks.
- Do not add LangChain/LangGraph in early phases. The project can express workflow concepts with small local services first.
- Use deterministic Python services for policy and approval checks.
- Keep browser execution behind Playwright.
- Keep LLM providers optional. Rules mode must continue to work without API keys.
- Keep each phase independently testable.
- Each new backend service needs pytest coverage.
- Each new frontend presentation helper needs Node test coverage if it contains non-trivial logic.

## Target Final README Sections

The final README should include:

- What this project is
- Why review-first automation matters
- Architecture diagram
- Supported workflow templates
- Human approval and policy model
- Trace and observability
- Evaluation center
- RAG workflow memory
- Local setup
- Demo script
- Safety boundaries

## Acceptance Criteria For This Phase

This phase is documentation only.

- `docs/trae-upgrade/00-product-positioning-and-target-architecture.md` exists.
- Later phase files reference this positioning.
- No code changes are required in this phase.

## Trae Prompt

Do not implement code for this phase. Read this document and use it as the architectural north star for phases 01-09. Preserve the existing form-filling product flow while gradually introducing general workflow concepts.
