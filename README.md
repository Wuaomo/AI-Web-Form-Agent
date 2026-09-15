# AI Web Form Agent

AI Web Form Agent is a review-first AI browser workflow assistant. It reads a web page, extracts fields or questionnaire items, suggests answers from profile data, reviewed memory, or local policy fixtures, requires human review, fills approved values in the browser, verifies the result, and stops before final submission.

## Primary Demo: Security Questionnaire Assistant

The main demo shows a safe browser workflow for security and compliance questionnaires:

1. Open a local security questionnaire fixture.
2. Extract questionnaire items and form fields.
3. Retrieve source-backed suggestions from reviewed memory or local policy documents.
4. Show answer suggestions with evidence and safety flags.
5. Let the user approve, edit, or reject each value.
6. Fill only approved values in the browser.
7. Verify the filled DOM values.
8. Stop before final submission.

The local demo works without LLM API keys. Optional LLM providers can improve suggestions, but rules-mode behavior remains available.

## Technical Architecture

```text
React UI
  -> FastAPI API
    -> AgentRun facade + governed runtime state
    -> LangGraph durable runtime orchestration
    -> LangChain structured suggestions and retrieval
    -> PolicyEngine + ApprovalGateService safety boundaries
    -> Playwright browser execution (approved only)
    -> SQLite persistent state (profiles, tasks, traces, approvals, memory)
    -> Benchmark runner with rules/memory/LLM/runtime comparison
```

**Key Components:**

- **Agent Runtime**: Compact AgentRun state, internal legacy read/write tool calls, governance decisions, review counts, and verification summaries exposed through Run Cockpit and legacy task facades.
- **LangGraph**: Durable, human-reviewed runtime orchestration with interrupt points before sensitive actions. The generic governed graph is the primary demo preparation path; the old questionnaire graph remains for compatibility.
- **LangChain**: Structured suggestions and retrieval for enhanced mapping and questionnaire answers. Optional - the system works without LLMs.
- **PolicyEngine**: Safety decision owner that blocks sensitive fields, refuses unsupported answers, and enforces action controls.
- **ApprovalGateService**: Human-in-the-loop approval workflow for risky operations like form filling and submission.
- **Playwright**: Approved browser execution that fills only reviewed values and verifies results in the DOM.
- **SQLite**: Reproducible local state for profiles, tasks, traces, approvals, reviewed memory, and benchmark runs.

## Safety Boundaries

The assistant never auto-submits forms, bypasses login or CAPTCHA, handles payments or OTPs, or stores passwords, payment data, OTPs, CAPTCHA values, or one-time consent values.

## What It Is

This project demonstrates safe, inspectable AI workflow automation. It combines a FastAPI backend, SQLite persistence, Playwright execution, workflow templates, reviewed memory, local policy retrieval, policy/approval gates, workflow traces, local evaluation runs, and a React/Vite console.

## Current App Surface

- Workflow console for runs, templates, approvals, traces, and evaluation.
- Run Cockpit on Task Detail for compact AgentRun plan, tool, governance, and verification state.
- Review Queue summary and proposal-backed review mapping flow before browser execution.
- Deterministic governed graph path for security questionnaire, vendor onboarding, and generic form-fill demo preparation.
- Deterministic planner and tool registry for enabled workflow templates.
- Policy engine and persisted approval requests for risky steps.
- SQLite-backed workflow memory for reviewed reusable values.
- Memory management page for reviewing stale saved mappings and deleting them.
- Source-backed questionnaire suggestions from local mock policy documents.
- Trace spans, screenshots, action logs, verification evidence, and usage/cost summaries.
- Local benchmark/evaluation center with comparison reports and browser replay mode.

## Supported Workflows

- **Security Questionnaire**: Primary demo. Uses the generic governed graph for no-key preparation while keeping the old questionnaire graph as fallback. Extract questionnaire items, suggest answers from reviewed memory or local policy docs, show evidence, require review, then fill approved values in the browser.
- **Vendor Onboarding**: Uses the generic governed graph to reuse reviewed company profile data for vendor onboarding forms with approval gates before browser execution.
- **Generic Form Fill**: Uses the generic governed graph to map profile values to ordinary web forms, review every value, fill the browser, and stop before submit.
- Web Data Extraction Workflow: Open pages, extract structured data, capture screenshots, and save results.
- Job Research Summary Workflow: Extract job page content, summarize, and save research results.
- Data Entry Workflow: Registered but disabled.
- Job Application Workflow: Registered but disabled.

## Architecture

```text
React UI
  -> FastAPI API
    -> SQLite profiles, tasks, jobs, approvals, traces
    -> Workflow templates, planner, and tool registry
    -> Form extraction and field mapping services
    -> Policy and approval gates
    -> Workflow memory and source-backed retrieval examples
    -> Playwright browser execution
    -> Benchmark runner and reports
```

See [docs/architecture.md](docs/architecture.md) for the module map, workflow loop, trace model, and evaluation model.

## Safety Model

- Final submit always waits for user approval.
- Passwords, OTPs, payment data, CAPTCHA, and destructive actions are blocked.
- Low-confidence mappings require review.
- One-time or sensitive values are not saved as reusable profile memory.
- Unsupported questionnaire answers are left empty instead of guessed.

See [docs/safety-model.md](docs/safety-model.md).

## Memory And Retrieval

The project uses two deliberately small retrieval paths:

- Reviewed workflow memory stores confirmed, reusable, non-sensitive field mappings.
- Local mock policy documents provide source-backed answers for security questionnaires.

Questionnaire suggestions carry source evidence such as document name, matched section, match score, and `needs_review` status. The user still reviews values before browser execution.

## Evaluation

The benchmark suite uses local HTML fixtures and expected JSON answers to track extraction quality, mapping accuracy, required-field coverage, action rejection, login-gate handling, browser replay verification, questionnaire answer accuracy, source evidence coverage, unsupported-answer refusal, sensitive-field skip rate, and regression details.

See [docs/evaluation-report-sample.md](docs/evaluation-report-sample.md) and [backend/benchmarks/README.md](backend/benchmarks/README.md).

| Area | Evidence |
| --- | --- |
| Form mapping | 16 local benchmark fixtures and expected JSON files |
| Retrieval | reviewed memory mode with source/stale governance, admin delete, and source-backed questionnaire suggestions |
| Safety | action-control rejection, login-gate detection, sensitive skip rules |
| Observability | workflow spans, screenshots, verification results, debug reports |
| Reliability | full-workflow benchmark mode, workflow success, safety pass, verification pass, failure rate |
| Regression tracking | stored benchmark runs, comparison metrics, Markdown export with reliability summary |

## Observability

Task Detail keeps advanced evidence collapsed by default while preserving the data needed to explain failures:

- workflow trace spans with phase, status, latency, provider/model, token, and cost fields;
- screenshots and field verification results after browser execution;
- action logs, background jobs, LLM usage summaries, and agent reviews;
- copyable debug reports that include source evidence without copying raw suggested values.

## Quick Start

The fastest demo path is Docker:

```powershell
docker compose up --build -d
python scripts/seed_demo.py
```

Open `http://localhost:5173`.

Stop the demo:

```powershell
docker compose down
```

## Manual Local Setup

Backend:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m playwright install chromium
uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

Backend health:

```text
http://localhost:8000/health
```

## Docker Details

The Docker stack exposes:

- backend: `http://localhost:8000`
- frontend: `http://localhost:5173`

Seed demo data in another terminal:

```powershell
python scripts/seed_demo.py
```

The seed script creates `Demo Applicant` through the running API and does not require LLM credentials.

## Optional LLM Providers

Copy `.env.example` to `.env` or set variables in PowerShell before starting the backend:

```powershell
$env:LLM_PROVIDER="openai"
$env:OPENAI_API_KEY="your-key"
$env:OPENAI_MODEL="gpt-4.1-mini"
```

Supported provider settings are documented in `.env.example`. If a selected provider is unavailable, the app can continue in rules mode.

## Optional Metrics Sidecar

The Go metrics sidecar is not part of the default Docker demo. It remains optional for local experiments.

```powershell
cd sidecars/metrics-go
go run .
```

Then point the backend at it:

```powershell
$env:METRICS_SIDECAR_URL="http://localhost:9100"
```

See [docs/go-metrics-sidecar.md](docs/go-metrics-sidecar.md).

## Demo Walkthrough

Use [docs/demo-script.md](docs/demo-script.md) for a 3 to 5 minute reviewer demo.

### Security Questionnaire (Primary Demo)

1. Start Docker compose.
2. Seed `Demo Applicant`.
3. Open Profiles and Workflows.
4. Create a **Security Questionnaire** run with the Docker demo URL.
5. Let the deterministic governed graph prepare mappings (no LLM API key required).
6. Open Review Mapping and inspect answers suggested from `mock-security-policy.md` with source evidence.
7. Confirm mappings only after reviewing the source evidence.
8. Inspect screenshot and verification evidence after browser execution.
9. Stop at final submit approval.
10. Show Evaluation for repeatable benchmark evidence.

### Vendor Onboarding

1. Create a **Vendor Onboarding** run with the Docker demo URL.
2. Review safe contact mappings and leave unsupported vendor-specific fields for manual review.
3. Confirm mappings, fill, verify, and stop before final submit approval.

### Generic Form Fill

1. Create a **Generic Form Fill** run with a test form URL.
2. Review mappings before execution.
3. Inspect screenshot and verification evidence.
4. Stop at final submit approval.

## Latest Local Verification

Last checked on this branch:

```text
backend:  python -m pytest       -> 808 passed, 2 warnings
frontend: npm test               -> 278 passed
frontend: npm run build          -> passed
```

## Test Commands

Backend:

```powershell
cd backend
python -m pytest
```

Frontend:

```powershell
cd frontend
npm test
npm run build
```

Docker package:

```powershell
docker compose build
```

CI runs backend tests and frontend tests/build through `.github/workflows/ci.yml`.

## Current Boundaries

This repository is intended to show a review-first agent architecture: AgentRun facades, workflow templates as planning hints, policy gates, approval center, profile memory, source-backed retrieval, trace evidence, evaluation runs, and a runnable local demo. Review Queue primary contract now covers field, memory, submit, browser-action visibility, unknown proposal fallback, and external-write display guards through AgentProposal / AgentReviewDecision where applicable. Current status: section 21 validation audit completed; remaining gaps documented in [docs/section-21-validation-audit.md](docs/section-21-validation-audit.md). Phase 11 Agent Runtime API primary boundary audit completed; remaining migration gaps documented. Phase 12 Agent Runtime API read boundary thin slice completed; remaining migration gaps documented. Review Queue primary AgentRun API boundary thin slice completed; remaining migration gaps documented. Review Mapping AgentRun Review Queue client helper thin slice completed; remaining migration gaps documented. Run Cockpit AgentRun read helper thin slice completed; remaining migration gaps documented. Phase B backend AgentRun/review boundary evidence sweep completed; remaining migration gaps documented. Stage 6 Compatibility Runtime Boundary Retirement Sweep is closed for boundary classification: primary AgentRun/governed endpoints, legacy facades, compatibility fallbacks, workflow-specific runtime paths, old graph fallback, frontend fallbacks, and benchmark/test helpers are now explicitly separated. The new `/agent-runs/{run_id}` read boundary returns compact AgentRun state without raw tool output. Run Cockpit now reads AgentRun compact state first when `agent_run_id` or `agent_runtime.run_id` is present, then uses the governed workflow fallback, then the task facade fallback. `/agent-runs/{run_id}/review-items` plus `/agent-runs/{run_id}/review-items/{item_id}/decision` expose proposal-backed review read/write, strip nested raw tool payloads from review item values, and keep FormField sync limited to field proposals. Review Mapping now requires `agent_run_id` or `agent_runtime.run_id` and surfaces AgentRun review read/write failures instead of falling back to legacy `/tasks/{task_id}/review-items`. Remaining gaps include the legacy `/tasks` facade, workflow-specific endpoints, old security questionnaire graph fallback, backend legacy review endpoint preservation tests, external consumer confirmation, and removal tests before backend deletion. FormField sync, fill fallback, and explicit submit approval endpoints remain compatibility paths. It does not claim the full runtime refactor is complete, nor production deployment, production authentication, cloud hosting, broad scraping, or CAPTCHA bypass.

Stage 7 Workflow-Specific Read Runtime Migration is closed for the audited read-only product paths. `/workflows/{task_id}/governed/start` now admits `web_data_extract` and `job_research_summary`, plans `extract_page`, `capture_screenshot`, and deterministic `generate_job_summary` as AgentRun tool steps, and keeps legacy `/tasks/{task_id}/extract-page` and `/tasks/{task_id}/job-summary` as compatibility facades. Evidence: `test_governed_start_web_data_extract_runs_read_only_page_plan` and `test_governed_start_job_summary_runs_read_only_summary_plan`. This is not an overall runtime refactor completion claim.

Stage 8 Browser-Write Compatibility Runtime Migration Audit is closed as an audit only. No unsafe product runtime bypass was found for sync fill, async fill, or final submit: they still pass through Tool Runtime plus review/approval, stale, policy, and verification gates. Browser-write migration is not closed because `/tasks/{task_id}/fill`, async fill jobs, and `/tasks/{task_id}/confirm-submit` remain compatibility runtime centers until a primary AgentRun continue boundary owns that execution.

Stage 9 Primary AgentRun Browser-Write Continue Boundary Thin Slice is closed for reviewed fill execution only. Task Detail now uses `/agent-runs/{run_id}/continue` when an AgentRun id exists, and that endpoint delegates to the same reviewed fill path covered by `test_continue_agent_run_delegates_reviewed_fill_to_shared_task_path`; tasks without a run id still fall back to `/tasks/{task_id}/fill`. Async fill jobs and `/tasks/{task_id}/confirm-submit` remain browser-write migration gaps.

Stage 10 Primary AgentRun Submit Continue Boundary Thin Slice is closed for explicit final submit execution. Task Detail now sends `{"action":"submit_form"}` to `/agent-runs/{run_id}/continue` when an AgentRun id exists, and that boundary delegates to the shared submit helper covered by `test_continue_agent_run_delegates_submit_to_shared_task_path`; frontend evidence includes `submit run cockpit uses AgentRun continue boundary when run id exists`. Tasks without a run id still fall back to `/tasks/{task_id}/confirm-submit`. Legacy confirm-submit remains a compatibility wrapper, explicit approval is still required, and async fill jobs remain a browser-write migration gap.

Stage 11 Browser-Write Runtime Migration Closure is closed for AgentRun-backed async fill. `/agent-runs/{run_id}/continue` now tags queued fill jobs with `agent_run_id`, and the worker delegates those jobs back through the AgentRun fill continuation helper without re-enqueueing. Evidence includes `test_continue_agent_run_enqueues_async_fill_with_run_id`, `test_execute_fill_stage_delegates_agent_run_backed_job`, and `test_fill_endpoint_creates_job_when_ready`. Legacy `/tasks/{task_id}/fill` jobs still enqueue with an empty payload, `/tasks/{task_id}/confirm-submit` remains the explicit-approval compatibility wrapper, and the overall runtime refactor is not complete.

Stage 12 Review Compatibility Retirement Slice is closed for narrowing Review Queue compatibility. Field synchronization now requires a field proposal type (`field_value`, `answer`, or `open_ended_answer`), so non-field proposals do not write `FormField` even if their target shape references a form field. Review Mapping uses the same distinction: field proposals stay in proposal-backed rows, while non-field proposals stay in the compact Review Queue. Evidence includes `test_review_queue_does_not_sync_non_field_proposal_with_form_field_target` and `proposal review helpers do not treat non-field proposals as field rows`. Legacy `/tasks/{task_id}/review-items` remains a compatibility fallback, and the overall runtime refactor is not complete.

Stage 13 Legacy Review Endpoint Delegate Slice is closed for audited Review Queue delegate/fallback behavior. `/agent-runs/{run_id}/review-items` stays scoped to the requested AgentRun instead of borrowing the latest task run's proposals, while legacy `/tasks/{task_id}/review-items` keeps task-level fallback behavior. Legacy review backfill now counts only field proposal types as field-row coverage, so non-field proposals with a `form_field` target do not hide the compatible field proposal row. Evidence includes `test_get_agent_run_review_items_stays_bound_to_requested_run` and `test_review_items_backfill_field_row_when_non_field_proposal_targets_form_field`. Legacy `/tasks/{task_id}/review-items` remains a compatibility fallback, and the overall runtime refactor is not complete.

Stage 15 Security Questionnaire Graph Fallback Retirement Readiness Slice is closed for classification only. The Security Questionnaire primary demo path stays on `/workflows/{task_id}/governed/start` and generic governed runtime; source-backed answers still enter the Review Queue as `answer` proposals with compact evidence; unsupported and sensitive answers remain blocked or review-gated; reviewed fill and explicit final submit still use shared runtime gates; verification trust comes from generic runtime persistence, not the old graph skeleton. The old security questionnaire graph fallback remains a compatibility fallback and is pinned by `test_old_security_graph_review_fallback_stays_non_mutating_and_compact`; primary path evidence includes `test_governed_start_security_questionnaire_uses_source_answer_proposals`. The overall runtime refactor is not complete.

Security Questionnaire Legacy Fallback Retirement Track Phase 16/17/18 is closed for deprecation contract and evidence only. Old `/workflows/{task_id}/start`, `/workflows/{task_id}`, and `/workflows/{task_id}/review` remain deprecated compatibility fallback endpoints; they are not the primary runtime path, do not create AgentRun/ToolRuntime/proposal state on start, and do not provide browser-write or verification trust evidence. Security questionnaire primary evidence stays on governed/AgentRun APIs, including compact `answer` proposals through `/agent-runs/{run_id}/review-items`. Evidence includes `test_old_security_graph_start_stays_out_of_agent_run_primary_path` and `test_security_questionnaire_agent_run_exposes_compact_answer_review_items`. The old graph is retirable when the external compatibility window ends, but it is not removed here and the overall runtime refactor is not complete.

Legacy Task / Review Compatibility Retirement Readiness Track Phase 19/20/21/22/23 is closed for contract tightening and readiness evidence. `/tasks` and `/tasks/{task_id}` remain compact compatibility facades without raw `tool_results` / `output_json`; `/agent-runs/{run_id}` remains the primary AgentRun read boundary. Legacy `/tasks/{task_id}/review-items` is now scoped to the canonical compatibility run (`task-{task_id}`), so it cannot borrow or decide arbitrary same-task AgentRun-owned proposals; Review Mapping AgentRun review writes no longer fall back to the legacy task decision endpoint. `FormField` sync remains limited to field proposals (`field_value`, `answer`, `open_ended_answer`), and `/tasks/{task_id}/extract-page` / `/tasks/{task_id}/job-summary` remain read-only compatibility facades now expressible through governed AgentRun planned tools. No compatibility API was deleted, no dashboard was added, and the overall runtime refactor is not complete.

Compatibility Removal Planning & Primary Path Consolidation Track Phase 24/25/26/27/28 is closed as planning/audit only in [docs/compatibility-removal-map.md](docs/compatibility-removal-map.md). The map identifies primary replacements, current consumers, fallback removals, removal blockers, runtime/security gaps, and the next removal order. No compatibility API was deleted, no production runtime gap was found, and the overall runtime refactor is not complete.

## Resume Bullets

- Built a **review-first AI Browser Workflow Assistant** with FastAPI, React, Playwright, SQLite, optional LLM providers, reviewed memory, policy gates, trace observability, and benchmark evaluation.
- Implemented a **Security Questionnaire Assistant** as the primary demo, suggesting answers from local policy documents with source evidence, requiring human review, blocking sensitive fields, refusing unsupported answers, and stopping before final submission.
- Designed an evaluation workbench comparing rules, LLM, and memory-assisted behavior across local fixtures with failure taxonomy, regression tracking, source evidence coverage, refusal metrics, latency, and cost signals.
