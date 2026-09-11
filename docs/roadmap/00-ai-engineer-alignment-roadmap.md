# AI Engineer Alignment Roadmap

## Target Positioning

AI Web Form Agent is a review-first AI browser workflow assistant with:

- Browser automation workflows
- Retrieval-backed reviewed memory
- Human review and approval gates
- Evaluation benchmarks
- Trace-based observability
- Reproducible AI workflow experiments

The project should not be repositioned as a chatbot. The stronger story is:

```text
read a browser page
  -> extract required information
  -> retrieve reviewed knowledge when available
  -> propose safe actions with evidence
  -> require human review
  -> execute in the browser
  -> verify and evaluate the result
```

The next architecture direction is:

```text
user goal
  -> agent planner
  -> typed tool calls
  -> action-level governance
  -> proposal review
  -> approved browser execution
  -> verification and traces
```

For the detailed refactor proposal, see
`docs/agent-runtime-refactor-rfc.zh.md`.

## Target AI Engineer Skills

This roadmap is designed to demonstrate:

- LLM workflow engineering
- RAG and memory systems
- Agent tool use and planning
- Evaluation dataset design
- Failure analysis and observability
- Full-stack AI product development

## Phases

1. Browser Workflow Assistant
2. Retrieval Memory Layer
3. Evaluation Workbench
4. Agent Observability
5. Portfolio Packaging
6. Domain Workflow Templates
7. Retrieval Quality and Memory Governance
8. Agent Reliability Benchmark Suite

## Agent Runtime Refactor Track

This track refines the architecture under the existing product story. It should
be implemented incrementally and should not break the local no-key demo,
security questionnaire demo, vendor onboarding demo, or benchmark evidence.

1. Add shared agent runtime schemas for runs, plans, tool calls, tool results,
   proposals, evidence, review decisions, governance decisions, and verification
   results.
2. Turn the existing tool registry from metadata-only into executable typed
   tools by wrapping current services first.
3. Add action-level governance before tool execution so review, approval,
   verification, and blocked decisions are made per tool call or proposed
   action.
4. Generalize Review Mapping into proposal review, where field values,
   evidence-backed answers, memory writes, browser clicks, and final submit
   actions share one review contract.
5. Introduce a reusable governed LangGraph runtime with pause/resume and
   human-in-the-loop interrupts; keep the existing security questionnaire graph
   as a compatibility path until parity tests pass.
6. Add optional structured LLM planning after the deterministic path is stable.
   Model output must be schema-valid and cannot bypass governance.
7. Add MCP and OpenAPI tools through the same Tool Runtime, allowlist, trace,
   review, and governance path. Start with read-only tools.
8. Evolve the frontend toward a Run Cockpit and Review Queue that show plan
   steps, tool calls, proposals, evidence, verification, and compact traces.

## Current Implementation Snapshot

- Phase 7C memory management: reviewed workflow memory can be listed and
  deleted through admin endpoints, and the React console has a Memory page for
  source, profile key, stale status, and deletion.
- Phase 8C browser replay benchmark: `full_workflow` benchmark mode opens local
  HTML fixtures in Playwright, maps profile values, fills the DOM, reads values
  back, and reports verification pass evidence without requiring LLM API keys.

## Current Implementation Snapshot

This branch already includes meaningful work from the earlier roadmap. Keep it
as evidence instead of replacing it with the newer JD-aligned demo direction.

Completed or mostly completed:

- Phase 1 base workflows: form fill, web data extraction, and job/research
  summary workflows exist in backend/frontend paths.
- Phase 1 security questionnaire workflow: enabled workflow template, planner
  path, local demo fixture, and review-first form execution path exist.
- Phase 2 mapping memory baseline: confirmed mappings can be saved as workflow
  memory, skipped for sensitive/one-time fields, and reused as retrieval
  fallback for future field mapping.
- Phase 2 source-backed questionnaire baseline: security questionnaire mappings
  can suggest answers from local mock policy docs, persist source evidence to the
  mapping checkpoint, and show that evidence in Review Mapping.
- Phase 3 evaluation baseline: local benchmark fixtures, rules/LLM/RAG-style
  modes, memory mode, regression comparison, and Markdown reports exist.
- Phase 3 questionnaire evaluation: source-backed answer accuracy, source
  evidence coverage, unsupported refusal, sensitive skip, and completion metrics
  are measured in the benchmark suite.
- Phase 4 observability baseline: action traces, workflow spans, screenshots,
  verification evidence, LLM usage, and debug reports exist.
- Phase 4 source evidence reporting: debug reports include source-backed
  questionnaire suggestion evidence while omitting raw suggested values.
- Phase 5 portfolio packaging: README, architecture, safety model, demo script,
  benchmark docs, test commands, verification snapshot, security questionnaire
  walkthrough, observability summary, and resume bullets exist.
- Phase 6 domain templates: Vendor Onboarding is enabled with a local fixture
  and reuses the same review-first form workflow, planner, safety gates, and UI
  creation path.
- Phase 7 retrieval governance baseline: reviewed memory retrieval includes
  source/governance metadata, stale status, and avoids automatic fallback
  mapping from stale memory; mapping review can show stale reviewed-memory
  evidence, and admin endpoints can list/delete memory items.
- Phase 8 reliability benchmark baseline: local full-workflow evaluation runs
  without LLM API keys and reports workflow success, safety pass, verification
  pass, and failure-rate metrics.
- Phase 9 runtime evaluation baseline: `runtime` benchmark mode runs without
  LLM API keys, stays on the deterministic governed runtime path, reports plan
  validity, tool success, governance/review, verification, recovery, and unsafe
  prevention metrics, and the Markdown report highlights those runtime metrics.
- Internal legacy read/write Tool Runtime convergence: legacy analyze,
  login-and-analyze, synchronous rules mapping, worker rules mapping, page
  extraction, job-summary prerequisite extraction, fill, submit, and verification
  persistence now record compact AgentToolCall/AgentToolResult state. This is a
  compatibility-layer convergence phase, not the overall runtime refactor finish.
- Generic governed graph primary demo path: Create Run, Page Intake, and Task
  Detail preparation now route generic form fill, vendor onboarding, and security
  questionnaire demos through `/workflows/{task_id}/governed/start` in
  deterministic no-key mode; runtime benchmark coverage uses the main demo
  workflow hint. The old security questionnaire graph remains as fallback.
- Review Queue primary contract coverage beyond field mapping: Review Mapping
  rows now prefer persisted `AgentProposal` values, statuses, and compact
  evidence when present; approve/edit/reject/needs-more-evidence writes
  `AgentReviewDecision` and keeps `FormField` synchronized only for field
  proposals. `memory_write` decisions stay proposal-only, `form_submit`
  proposals display as high-risk approval-owned items without auto-submit,
  browser click/navigation proposals appear as compact display-only action
  items, unknown proposal types fall back without crashing, and
  `external_api_write` proposals display as high-risk blocked-style items
  without registering or executing external writes. Legacy `/tasks` review
  items, checkpoint source suggestions, FormField-only rows, legacy fill
  fallback, and explicit approval endpoints remain as compatibility fallbacks.

Still missing from the runtime refactor direction:

- section 21 validation audit completed; remaining gaps documented in
  `docs/section-21-validation-audit.md`. This is an audit milestone, not an
  overall runtime refactor completion claim.
- Remaining gaps include legacy `/tasks` and workflow-specific compatibility
  paths, old security questionnaire graph fallback, and internal browser paths
  that still rely on compact convergence state rather than a pure Agent Runtime
  API boundary.
- Phase 11 Agent Runtime API primary boundary audit completed; remaining migration gaps documented. Remaining gaps include the legacy `/tasks` facade,
  workflow-specific endpoints, and old security questionnaire graph fallback.
- Phase 12 Agent Runtime API read boundary thin slice completed; remaining migration gaps documented. `/agent-runs/{run_id}` now returns compact AgentRun state without raw tool output. Remaining gaps include the legacy `/tasks` facade, workflow-specific endpoints, and old security questionnaire graph fallback.
- Review Queue primary AgentRun API boundary thin slice completed; remaining migration gaps documented. `/agent-runs/{run_id}/review-items` and `/agent-runs/{run_id}/review-items/{item_id}/decision` now expose proposal-backed review read/write through the AgentRun API. Remaining gaps include legacy `/tasks/{task_id}/review-items` fallback, FormField sync compatibility, workflow-specific endpoints, and old security questionnaire graph fallback.
- Review Mapping AgentRun Review Queue client helper thin slice completed; remaining migration gaps documented. Review Mapping now reads AgentRun review items first when `agent_run_id` or `agent_runtime.run_id` is present, then falls back to legacy `/tasks/{task_id}/review-items`. FormField sync compatibility remains; legacy `/tasks/{task_id}/review-items` fallback, workflow-specific endpoints, old security questionnaire graph fallback, and the legacy `/tasks` facade are still migration gaps.
- Run Cockpit AgentRun read helper thin slice completed; remaining migration gaps documented. Run Cockpit now reads AgentRun compact state first when `agent_run_id` or `agent_runtime.run_id` is present, then uses the governed workflow fallback, then the task facade fallback. Remaining gaps include the legacy `/tasks` facade, workflow-specific endpoints, old security questionnaire graph fallback, and legacy `/tasks/{task_id}/review-items` fallback.
- Task Detail governed-run start navigation now uses the refreshed Run Cockpit runtime state, so a `WAITING_REVIEW` AgentRun compact state routes to Review Mapping even when the start endpoint response is stale. Remaining gaps are unchanged.
- Phase A frontend primary AgentRun boundary audit completed; existing frontend coverage proves Task Detail, Run Cockpit, and Review Mapping use AgentRun-first compact runtime/review boundaries with governed workflow, task facade, and legacy review fallbacks preserved. This closes Phase A frontend boundary only, not the overall runtime refactor.
- Review Mapping AgentRun boundary coverage tightened for proposal-backed field edits and AgentRun decision failure fallback; compatibility fallbacks remain migration gaps.
- Run Cockpit coverage tightened for the no-run-id governed workflow path; this remains frontend boundary evidence, not overall runtime refactor completion.
- Legacy `/tasks` facade coverage tightened to prove compact `agent_runtime`
  hides raw `tool_results` / `output_json`; this remains compatibility facade
  evidence, not overall runtime refactor completion.
- Phase B backend AgentRun/review boundary evidence sweep completed; remaining migration gaps documented. `/agent-runs/{run_id}` remains compact without raw
  output; `/agent-runs/{run_id}/review-items` strips nested raw tool payloads
  from proposal values; `/agent-runs/{run_id}/review-items/{item_id}/decision`
  writes AgentReviewDecision first and keeps FormField sync limited to field
  proposals. Remaining gaps include legacy `/tasks/{task_id}/review-items`
  fallback, workflow-specific endpoints, old security questionnaire graph
  fallback, and the legacy `/tasks` facade. This is backend boundary evidence,
  not overall runtime refactor completion.
- Overall runtime refactor Stage 2, Primary API Boundary Hardening, is closed
  by focused backend/frontend/API evidence. Stage 3, Tool Runtime Coverage,
  backend legacy path audit is closed for the audited product runtime surfaces:
  page intake `extract_form` / `extract_page`, legacy analyze, rules and LLM
  mapping, page extraction, screenshot capture, fill, submit, and generic
  verification persistence now route through Tool Runtime or persist compact
  runtime state. Remaining gaps still include legacy workflow-specific
  compatibility paths, old security questionnaire graph fallback, benchmark/test
  fixture helpers, and backend paths that intentionally remain compact
  convergence state rather than pure Agent Runtime API calls. This is not an
  overall runtime refactor completion claim.
- Stage 4A, Tool Runtime Governance Coverage Sweep, is closed for
  already-runtime-backed backend product paths. Read tools (`extract_form`,
  `extract_page`, `capture_screenshot`), mapping (`map_fields` rules/LLM),
  browser write (`fill_form`), high-risk submit (`submit_form`), and
  `AgentToolCall.governance_decision_json` persistence now have focused
  governance evidence. Page extraction and job-summary prerequisite screenshots
  now route through the `capture_screenshot` runtime tool instead of directly
  calling the screenshot helper. Compatibility facades remain compact and do
  not expose raw output. This is Stage 4A evidence, not Stage 4 overall
  completion.
- Stage 4B, Governance Negative Coverage Sweep, is closed for audited product
  runtime enforcement gaps. `approved_tool_call_ids` now unlocks only the
  matching `tool_call_id`, name-wide `approved_tool_names` no longer bypasses
  governance, and sensitive browser mutation checks inspect real field-object
  payloads before approved writes execute. Existing focused coverage confirms
  unapproved `fill_form` / `submit_form` handlers stay paused, external write
  tools stay unregistered/display-only, and sensitive or consent-like
  `memory_write` values are blocked or review-gated. This is Stage 4B negative
  enforcement evidence, not Stage 4 overall completion.
- Stage 4C, Governed Browser Action Resume/Parity Sweep, is closed for audited
  product runtime browser-write resume/parity gaps. Rejected governed review
  decisions no longer trigger browser write resume, `needs_more_evidence`
  remains non-resuming, and approved/edited field proposals cannot be reused
  after the current mapped value changes. Existing focused coverage confirms
  governed submit resume is explicit-final-submit-only with stale
  value/selector snapshots rejected, `fill_form` persists verification
  evidence, and browser click/navigation proposals remain display-only. This is
  Stage 4C evidence, not Stage 4 overall completion.
- Stage 4D, Governance Closure Audit, is closed for true product runtime
  enforcement paths. Runtime-backed approved/edited fill proposals now reject
  stale selector snapshots, so changed selectors cannot reuse old review
  approval. The closure audit confirms browser fill/submit product paths route
  through Tool Runtime plus shared review/approval/stale gates, rejected and
  needs-more-evidence decisions cannot resume browser writes, sensitive browser
  inputs remain blocked or gated, legacy `/tasks` fill/submit facades do not
  bypass governed/runtime gates, async fill uses the same gate as sync fill,
  browser click/navigation proposals remain display-only, and the old security
  questionnaire graph fallback does not execute dangerous browser actions. This
  closes Stage 4 governance for true product runtime enforcement paths, not the
  overall runtime refactor.
- Stage 5, Verification Generalization Sweep, is closed for governed runtime
  verification trust paths. Sync fill failures caused by required readback
  mismatch now persist generic `AgentVerificationResult` evidence before
  failing, and async fill jobs now fail on required readback mismatch with the
  same generic evidence persistence. Existing focused coverage confirms
  `fill_form` verification candidates, submit/page_state evidence,
  `verify_browser_state` generic persistence, compact Run Cockpit verification
  presentation, and benchmark `verification_pass_rate`. The old security
  questionnaire graph fallback remains a compatibility gap because its
  verification node is skeleton-only, but it does not execute dangerous browser
  actions. This closes Stage 5 for governed runtime verification trust paths,
  not the overall runtime refactor.
- Stage 6 Compatibility Runtime Boundary Retirement Sweep is closed for
  runtime boundary classification. The audit found no production code gap:
  `/agent-runs/*` and `/workflows/{task_id}/governed*` remain primary
  AgentRun/governed boundaries; `/tasks` stays a compact legacy facade;
  `/tasks/{task_id}/review-items` stays a compatibility fallback;
  workflow-specific page extraction and job summary endpoints still carry
  real read-only product behavior through Tool Runtime; `/tasks/{task_id}/fill`
  and `/tasks/{task_id}/confirm-submit` still carry legacy browser-write
  behavior through the shared Tool Runtime, review/approval, stale, policy, and
  verification gates; the old security questionnaire graph remains skeleton
  fallback only; benchmark/test fixture helpers are not product runtime gaps.
  This closes Stage 6 boundary classification only, not the overall runtime
  refactor.
- Stage 7 Workflow-Specific Read Runtime Migration is closed for audited
  read-only product paths. `/workflows/{task_id}/governed/start` now admits
  `web_data_extract` and `job_research_summary`, expresses page extraction,
  screenshot capture, and deterministic job summary as AgentRun planned tool
  steps, and persists compact runtime evidence. Legacy
  `/tasks/{task_id}/extract-page` and `/tasks/{task_id}/job-summary` remain
  compatibility facades. Evidence:
  `test_governed_start_web_data_extract_runs_read_only_page_plan` and
  `test_governed_start_job_summary_runs_read_only_summary_plan`. This is not
  an overall runtime refactor completion claim.
- Stage 8 Browser-Write Compatibility Runtime Migration Audit is closed as an
  audit only. No unsafe product runtime bypass was found: sync fill, async
  fill, and final submit still pass through Tool Runtime plus shared
  review/approval, stale, policy, and verification gates. Browser-write
  migration itself is not closed because `/tasks/{task_id}/fill`, async fill
  jobs, and `/tasks/{task_id}/confirm-submit` remain compatibility runtime
  centers instead of a primary AgentRun continue boundary. This is not an
  overall runtime refactor completion claim.
- Stage 9 Primary AgentRun Browser-Write Continue Boundary Thin Slice is
  closed for reviewed fill execution only. `/agent-runs/{run_id}/continue`
  now gives AgentRun-backed reviewed fill a primary browser-write boundary, and
  Task Detail uses it when an AgentRun id exists while preserving
  `/tasks/{task_id}/fill` as the no-run-id fallback. Evidence:
  `test_continue_agent_run_delegates_reviewed_fill_to_shared_task_path`,
  `agent run API client uses primary continue boundary`, and
  `continue run cockpit uses AgentRun boundary when run id exists`. Async fill
  jobs and `/tasks/{task_id}/confirm-submit` remain browser-write migration
  gaps. This is not an overall runtime refactor completion claim.
- Stage 10 Primary AgentRun Submit Continue Boundary Thin Slice is closed for
  explicit final submit execution. `/agent-runs/{run_id}/continue` now accepts
  `{"action":"submit_form"}` for AgentRun-backed final submit, delegates to the
  shared submit helper, and preserves explicit approval, stale value/selector,
  Tool Runtime, verification, and compact facade gates. Task Detail uses this
  boundary when a run id exists while preserving `/tasks/{task_id}/confirm-submit`
  as the no-run-id compatibility fallback. Evidence:
  `test_continue_agent_run_delegates_submit_to_shared_task_path`,
  `agent run API client sends submit continue action payload`, and
  `submit run cockpit uses AgentRun continue boundary when run id exists`. Async
  fill jobs remain a browser-write migration gap. This is not an overall
  runtime refactor completion claim.
- Stage 11 Browser-Write Runtime Migration Closure is closed for AgentRun-backed
  async fill. `/agent-runs/{run_id}/continue` now tags queued fill jobs with
  `agent_run_id`, and the worker delegates those jobs through the AgentRun fill
  continuation helper without re-enqueueing. Legacy `/tasks/{task_id}/fill`
  jobs still enqueue unchanged, `/tasks/{task_id}/confirm-submit` remains the
  explicit-approval compatibility wrapper, and the task facade stays compact.
  Evidence: `test_continue_agent_run_enqueues_async_fill_with_run_id`,
  `test_execute_fill_stage_delegates_agent_run_backed_job`, and
  `test_fill_endpoint_creates_job_when_ready`. This closes Stage 11, not the
  overall runtime refactor.
- Stage 12 Review Compatibility Retirement Slice is closed for narrowing
  Review Queue compatibility. Field synchronization now requires a field
  proposal type (`field_value`, `answer`, or `open_ended_answer`), so non-field
  proposals do not write `FormField` even when their target shape references a
  form field. Review Mapping uses the same distinction: field proposals stay in
  proposal-backed rows, and non-field proposals stay in the compact Review
  Queue. Evidence:
  `test_review_queue_does_not_sync_non_field_proposal_with_form_field_target`
  and `proposal review helpers do not treat non-field proposals as field rows`.
  Legacy `/tasks/{task_id}/review-items` remains a compatibility fallback. This
  closes Stage 12, not the overall runtime refactor.
- Stage 13 Legacy Review Endpoint Delegate Slice is closed for audited Review
  Queue delegate/fallback behavior. `/agent-runs/{run_id}/review-items` now
  stays bound to the requested AgentRun instead of borrowing the latest task
  run, while legacy `/tasks/{task_id}/review-items` keeps task-level fallback
  behavior. Legacy review backfill now treats only field proposal types as
  field-row coverage, so non-field proposals with a `form_field` target do not
  hide the compatible field proposal row. Evidence:
  `test_get_agent_run_review_items_stays_bound_to_requested_run` and
  `test_review_items_backfill_field_row_when_non_field_proposal_targets_form_field`.
  Legacy `/tasks/{task_id}/review-items` remains a compatibility fallback; this
  closes Stage 13, not the overall runtime refactor.
- Stage 14 Governed Review Decision Delegate Slice is closed for audited
  governed review decision delegation. `/workflows/{task_id}/governed/review-items/{item_id}/decision`
  now delegates shared decision persistence, field sync, and legacy backfill to
  the shared Review Queue decision helper, and stays scoped to the canonical
  governed AgentRun (`task-{task_id}`) so stale same-task AgentRun proposals are
  rejected instead of written. Evidence:
  `test_governed_review_decision_stays_scoped_to_governed_run`. Legacy
  `/tasks/{task_id}/review-items` and AgentRun-first `/agent-runs/{run_id}/review-items`
  remain compatibility/primary boundaries respectively; this closes Stage 14,
  not the overall runtime refactor.
- Stage 15 Security Questionnaire Graph Fallback Retirement Readiness Slice is
  closed for classification only. The audit confirms the security questionnaire
  demo primary path is generic governed runtime through
  `/workflows/{task_id}/governed/start`, source-backed answers become
  proposal-backed Review Queue items with compact evidence, sensitive and
  unsupported answers remain blocked or review-gated, reviewed browser fill and
  explicit final submit continue through shared runtime gates, and verification
  trust evidence comes from generic runtime persistence rather than the old
  graph skeleton. The old security questionnaire graph fallback remains a
  compatibility fallback and does not create browser-write screenshots, action
  logs, field verification rows, or generic verification rows when reviewed.
  Evidence:
  `test_governed_start_security_questionnaire_uses_source_answer_proposals` and
  `test_old_security_graph_review_fallback_stays_non_mutating_and_compact`.
  This closes Stage 15 readiness classification, not the overall runtime
  refactor.
- Security Questionnaire Legacy Fallback Retirement Track Phase 16/17/18 is
  closed for deprecation contract, primary-path evidence tightening, and
  readiness audit. Old `/workflows/{task_id}/start`, `/workflows/{task_id}`,
  and `/workflows/{task_id}/review` are documented as deprecated compatibility
  fallback endpoints; focused evidence confirms old start does not create
  AgentRun/ToolRuntime/proposal rows, old review remains non-mutating and not a
  verification trust path, and the security questionnaire primary path
  continues through governed/AgentRun APIs with compact `answer` proposals.
  Evidence:
  `test_old_security_graph_start_stays_out_of_agent_run_primary_path` and
  `test_security_questionnaire_agent_run_exposes_compact_answer_review_items`.
  The old graph is retirable when the external compatibility window ends, but
  it is not deleted here and this is not an overall runtime refactor completion
  claim.
- Legacy Task / Review Compatibility Retirement Readiness Track Phase 19/20/21/22/23
  is closed for contract tightening and readiness evidence. `/tasks` and
  `/tasks/{task_id}` stay compact compatibility facades without raw
  `tool_results` / `output_json`; `/agent-runs/{run_id}` remains the primary
  AgentRun read boundary. Legacy `/tasks/{task_id}/review-items` now stays
  scoped to the canonical compatibility run (`task-{task_id}`), so it cannot
  borrow or decide arbitrary same-task AgentRun-owned proposals; Review Mapping
  AgentRun review writes no longer fall back to the legacy task decision
  endpoint. `FormField` sync remains narrowed to field proposals
  (`field_value`, `answer`, `open_ended_answer`), and workflow-specific
  `/tasks/{task_id}/extract-page` / `/tasks/{task_id}/job-summary` remain
  read-only compatibility facades now expressible through governed AgentRun
  planned tools. This track can close and future work may enter compatibility
  removal planning, but no compatibility API is deleted and the overall runtime
  refactor is not complete.

## Post-Portfolio Extensions

6. Domain Workflow Templates
7. Retrieval Quality and Memory Governance
8. Agent Reliability Benchmark Suite

## Product Story

The project should be presented as a review-first browser workflow assistant.
Form filling remains the first concrete workflow, but the broader system should
show how an AI assistant can read pages, extract information, use reviewed
memory, take reviewed browser actions, and prove improvement through
evaluation.

The JD-aligned demo path is a security/compliance-style questionnaire workflow:

```text
security questionnaire page
  -> extract questions and fields
  -> suggest answers from reviewed memory or mock policy docs
  -> show source evidence
  -> block sensitive or unsupported answers
  -> fill only after human review
  -> stop before final submission
```

Longer-term, domain workflows should become planning presets rather than the
main runtime abstraction. The runtime should be able to accept a user goal,
select tools, create evidence-backed proposals, pause for review when needed,
execute approved browser actions, and verify the result.

## Non-Goals

- No automatic final submission.
- No CAPTCHA solving.
- No login bypass.
- No general-purpose uncontrolled browser agent.
- No fine-tuning or model editing until the core system is credible.
- No chatbot UI unless it directly supports a reviewed browser workflow.
- No big-bang migration to an external agent SDK before the project-owned
  governance, review, verification, persistence, and evaluation contracts are
  stable.

