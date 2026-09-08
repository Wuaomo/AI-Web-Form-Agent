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

