# Section 21 Validation Audit

Date: 2026-09-10

Scope: RFC section 21 validation only. Current status: section 21 validation
audit completed; remaining gaps documented. This audit records current evidence
and remaining gaps; it does not mark full refactor completion.
Phase 11 Agent Runtime API primary boundary audit completed; remaining migration gaps documented.
Phase 12 Agent Runtime API read boundary thin slice completed; remaining migration gaps documented.
Review Queue primary AgentRun API boundary thin slice completed; remaining migration gaps documented.
Review Mapping AgentRun Review Queue client helper thin slice completed; remaining migration gaps documented.
Review Mapping AgentRun field edit and decision fallback coverage tightened.
Run Cockpit AgentRun read helper thin slice completed; remaining migration gaps documented.
Run Cockpit no-run-id governed workflow coverage tightened.
Task Detail static review affordance now uses Run Cockpit AgentRun-first compact
review state before stale task status.
Phase A frontend primary AgentRun boundary audit completed; no production code
changes were needed. This closes Phase A frontend boundary only, not the
overall runtime refactor.
Phase B backend AgentRun/review boundary evidence sweep completed; remaining migration gaps documented. This closes only the backend AgentRun/review boundary
evidence sweep, not the overall runtime refactor.
Stage 4A Tool Runtime Governance Coverage Sweep completed; one product runtime
gap was fixed and remaining compatibility gaps are documented. This closes only
the Stage 4A sweep, not the overall Stage 4 governance refactor.
Stage 4B Governance Negative Coverage Sweep completed; two product runtime
governance gaps were fixed and remaining compatibility gaps are documented.
This closes only the Stage 4B negative enforcement sweep, not the overall
Stage 4 governance refactor.
Stage 4C Governed Browser Action Resume/Parity Sweep completed; two product
runtime browser-write resume/parity gaps were fixed and remaining
compatibility gaps are documented. This closes only Stage 4C, not the overall
Stage 4 governance refactor.
Stage 4D Governance Closure Audit completed; one product runtime enforcement
gap was fixed and remaining compatibility gaps are documented. This closes the
Stage 4 governance refactor for true product runtime enforcement paths, not the
overall runtime refactor.
Stage 5 Verification Generalization Sweep completed; two product runtime
verification evidence gaps were fixed and remaining compatibility gaps are
documented. This closes Stage 5 for governed runtime verification trust paths,
not the overall runtime refactor.
Stage 6 Compatibility Runtime Boundary Retirement Sweep completed; no
production code changes were needed. The sweep classified primary AgentRun
runtime boundaries, legacy facades, compatibility fallbacks, workflow-template
endpoints, old security questionnaire graph fallback, frontend read fallbacks,
and benchmark/test fixture helpers. This closes Stage 6 boundary
classification only, not the overall runtime refactor.
Stage 7 Workflow-Specific Read Runtime Migration completed for audited
read-only product paths. Governed AgentRun start now admits `web_data_extract`
and `job_research_summary`, expresses page extraction, screenshot capture, and
deterministic job summary as planned tool steps, and keeps legacy read
endpoints as compatibility facades. Evidence:
`test_governed_start_web_data_extract_runs_read_only_page_plan` and
`test_governed_start_job_summary_runs_read_only_summary_plan`. This closes
Stage 7 only, not the overall runtime refactor.
Stage 8 Browser-Write Compatibility Runtime Migration Audit completed. The
audit found no unsafe browser-write bypass in product paths, but did find that
browser-write execution still has not migrated to a primary AgentRun continue
boundary: `/tasks/{task_id}/fill`, async fill jobs, and
`/tasks/{task_id}/confirm-submit` remain compatibility runtime centers. This
closes the Stage 8 audit only; it does not close browser-write runtime
migration or the overall runtime refactor.
Stage 9 Primary AgentRun Browser-Write Continue Boundary Thin Slice completed
for reviewed fill execution only. `/agent-runs/{run_id}/continue` now provides
the primary AgentRun browser-write boundary for reviewed fill and Task Detail
uses it when a run id exists, while no-run-id tasks still fall back to
`/tasks/{task_id}/fill`. Async fill jobs and
`/tasks/{task_id}/confirm-submit` remain browser-write migration gaps.
Stage 10 Primary AgentRun Submit Continue Boundary Thin Slice completed for
explicit final submit execution. `/agent-runs/{run_id}/continue` now accepts
`{"action":"submit_form"}` as the AgentRun-backed final submit boundary while
legacy `/tasks/{task_id}/confirm-submit` stays as a compatibility wrapper and
no-run-id fallback. At Stage 10, async fill jobs still remained a browser-write
migration gap.
Stage 11 Browser-Write Runtime Migration Closure completed for AgentRun-backed
async fill. `/agent-runs/{run_id}/continue` now tags queued fill jobs with
`agent_run_id`, and the worker delegates those jobs through the AgentRun fill
continuation helper without re-enqueueing. Legacy `/tasks/{task_id}/fill` jobs
still enqueue with an empty payload, and `/tasks/{task_id}/confirm-submit`
remains the explicit-approval compatibility wrapper.

## Overall Runtime Refactor Stage Status

Current stage: Stage 11 Browser-Write Runtime Migration Closure is closed for
AgentRun-backed async fill. Browser-write runtime migration is closed for the
audited AgentRun-backed fill, async fill, and explicit submit paths while
legacy `/tasks/{task_id}/fill` and `/tasks/{task_id}/confirm-submit` remain
compatibility entrypoints. Stage 10 submit continue, Stage 9 reviewed-fill
continue, Stage 8 audit, Stage 7 read-only migration, Stage 6 boundary
classification, Stage 5 verification, and Stage 4 governance remain closed in
their scoped senses. The overall runtime refactor is not complete.

Stage 2, Primary API Boundary Hardening, has focused test evidence for:

- compact `/agent-runs/{run_id}` reads without raw tool output;
- proposal-backed compact `/agent-runs/{run_id}/review-items` reads;
- AgentRun-first `/agent-runs/{run_id}/review-items/{item_id}/decision` writes;
- legacy `/tasks` and `/tasks/{task_id}/review-items` as compatibility facade/fallback paths;
- FormField synchronization limited to field proposals;
- raw `tool_results`, `output_json`, and `raw_output_json` staying out of primary API/UI boundaries.

Stage 3 has four small Tool Runtime coverage slices:
`analyze_page_intake()` now runs `extract_form` and `extract_page` through the
existing Tool Runtime instead of calling browser extraction services directly.
Legacy synchronous LLM mapping now runs through the existing `map_fields`
runtime tool instead of directly calling the LLM mapper from the endpoint.
Async job LLM mapping now uses the same `map_fields` runtime tool instead of
calling the legacy mapper directly from the worker. Legacy screenshot capture
now runs through the `capture_screenshot` runtime tool instead of directly
calling the browser executor from the endpoint.
Evidence:
`backend/tests/test_page_intake_service.py::test_analyze_page_intake_uses_tool_runtime_for_browser_reads`,
`backend/tests/test_task_mapping_endpoint.py::test_llm_mapping_persists_map_fields_runtime_call`,
`backend/tests/test_job_worker.py::test_execute_job_llm_mapping_persists_runtime_call`,
`backend/tests/test_task_mapping_endpoint.py::test_capture_screenshot_persists_runtime_call`.

Stage 3 backend legacy path audit is now closed for the audited product runtime
surfaces: form extraction, page extraction, field mapping rules/LLM, browser
fill/submit, verification persistence, and screenshot capture. The overall
runtime refactor is still not complete. Remaining gaps are compatibility
surfaces: legacy `/tasks` facades, workflow-specific endpoints, benchmark/test
fixture helpers, and the old security questionnaire graph fallback.

Stage 4A governance coverage sweep is now closed for the audited product
runtime surfaces. Read tools (`extract_form`, `extract_page`,
`capture_screenshot`), mapping (`map_fields` rules/LLM), browser write
(`fill_form`), high-risk submit (`submit_form`), and
`AgentToolCall.governance_decision_json` persistence have focused evidence for
compact persisted governance decisions. Fixed in this slice: page extraction
and job-summary prerequisite extraction now route their screenshot side effect
through the `capture_screenshot` runtime tool and persist the `ALLOW`
governance decision. Compatibility facades remain compact and do not expose raw
tool output. Benchmark/test fixture helpers and the old security questionnaire
graph fallback remain outside this product runtime sweep.

Stage 4B negative governance enforcement sweep is now closed for the audited
product runtime gaps:

- `ToolRuntime` pause/block behavior blocks handlers for `BLOCKED`,
  `REVIEW_REQUIRED`, and `APPROVAL_REQUIRED`.
- `approved_tool_call_ids` now unlocks only the exact matching
  `tool_call_id`; name-wide `approved_tool_names` no longer bypasses
  governance for future calls.
- Browser mutation governance now inspects real field-object payloads as well
  as dict/list payloads before allowing approved writes, so password, OTP,
  payment, CAPTCHA, and token browser inputs are blocked at the shared runtime
  enforcement point. Consent-like browser fields remain gated by the shared
  fill policy/approval path.
- `fill_form` without review and `submit_form` without explicit final-submit
  approval do not execute their browser handlers.
- External write tools remain unregistered through the MCP/OpenAPI read-only
  adapter path; `external_api_write` proposals stay display-only and compact.
- `memory_write` sensitive values are blocked and consent-like values require
  review/approval tied to the exact proposed action.
- Legacy compatibility endpoints remain, but audited fill/submit/review
  facades route through the same runtime gates or stop before dangerous browser
  execution.

Fixed in this slice:

- Removed name-wide runtime approval via `approved_tool_names`; only exact
  `approved_tool_call_ids` can advance a paused tool call.
- Hardened sensitive browser mutation detection for real field objects passed
  by product runtime wrappers.

Stage 4C governed browser action resume/parity sweep is now closed for the
audited product runtime gaps:

- Governed review decisions now resume paused browser writes only for
  `approved` or `edited` decisions; `rejected` and `needs_more_evidence`
  decisions cannot approve a paused `fill_form` tool call.
- Legacy `/tasks/{task_id}/fill` now treats an approved or edited field
  proposal as stale when its persisted `proposed_value` no longer matches the
  current `FormField.mapped_value`, so changed browser writes require fresh
  review.
- Existing coverage confirms governed approval resume for `submit_form` is
  only attempted from the explicit final-submit endpoint, and only when the
  approved field snapshot and current selector/value snapshot still match.
- Existing coverage confirms `fill_form` produces verification candidates and
  persisted `AgentVerificationResult` evidence after execution.
- Existing coverage confirms `form_submit` requires explicit final-submit
  approval before execution and persists submit verification evidence.
- Existing coverage confirms `browser_click` and `browser_navigation`
  proposals remain compact display-only review items, not executable browser
  tools.

Fixed in this slice:

- Removed `rejected` from governed review auto-resume decisions.
- Made the field proposal browser-write gate compare approved proposal value
  against the current mapped field value before allowing fill.

Stage 4D governance closure audit is now closed for true product runtime
enforcement paths:

- Fixed: approved or edited field proposals backed by runtime `map_fields`
  output cannot be reused after the current field selector changes; stale fill
  selector snapshots block `/tasks/{task_id}/fill` before browser execution.
- Audited: all real browser fill and submit product paths reach
  `fill_form` / `submit_form` through Tool Runtime wrappers and the shared
  review/approval gates.
- Audited: sync `/tasks/{task_id}/fill` and async fill jobs share
  `filter_fillable_fields_by_policy` and
  `split_fields_by_browser_write_review` before browser execution.
- Audited: final submit execution starts only from
  `/tasks/{task_id}/confirm-submit` after an exact approved action snapshot;
  stale field values or selectors do not reuse governed submit execution.
- Audited: `rejected` and `needs_more_evidence` review decisions do not resume
  browser writes.
- Audited: browser click/navigation and external write proposals remain compact
  display-only review items; no executable browser click/navigation or external
  write tool is registered in the product runtime.
- Audited: the old security questionnaire graph fallback can move through a
  review resume, but its `fill_browser` node is a non-mutating skeleton and
  does not call Playwright or `BrowserExecutor`; this remains a compatibility
  gap, not a dangerous-action bypass.
- Kept out of scope: benchmark/test fixture helpers and compatibility facades
  that do not execute dangerous browser actions.

Fixed in this slice:

- Made the field proposal browser-write gate compare the current selector
  against the latest persisted runtime mapping snapshot when one exists.

Stage 5 verification generalization sweep is now closed for governed runtime
verification trust paths:

- Fixed: sync `/tasks/{task_id}/fill` now persists failed required field
  readback evidence to generic `AgentVerificationResult` before returning
  failure, instead of leaving the generic runtime trust layer empty on
  verification-blocked fills.
- Fixed: async fill jobs now use the same required field verification failure
  gate as sync fill; required readback mismatches persist generic verification
  evidence and fail the job instead of reporting a successful wait-for-approval
  state.
- Covered: `fill_form` produces field-level verification candidates from DOM
  readback evidence and successful fills persist generic
  `AgentVerificationResult` rows.
- Covered: `submit_form` persists submit/page_state verification evidence only
  after explicit final-submit approval.
- Covered: `verify_browser_state` tool output persists generic
  `AgentVerificationResult` rows, including failed mismatch status and JSON
  expected/actual values.
- Covered: Run Cockpit consumes compact verification summaries and evidence
  snippets, limits mismatch/evidence display, and does not expose raw
  `output_json`.
- Covered: runtime and full-workflow benchmark modes continue to report
  `verification_pass_rate` in no-key deterministic paths.
- Compatibility gap only: the old security questionnaire graph fallback still
  has a skeleton `verify_result` that returns `verified: true`, but its
  `fill_browser` node is non-mutating and does not execute Playwright or
  `BrowserExecutor`; it is not valid real browser verification evidence.
- Kept out of scope: new dashboards, new dependencies, legacy endpoint
  deletion, and old security questionnaire graph migration beyond documenting
  the compatibility gap.

Fixed in this slice:

- Persisted generic failed fill verification evidence for sync required
  readback failures.
- Failed async fill jobs on required readback mismatch while preserving generic
  verification evidence.

## Runtime Object Persistence Matrix

| Runtime object | Validation | Evidence |
| --- | --- | --- |
| `AgentRun` | covered | `backend/app/models.py`, `backend/tests/test_workflow_runtime_endpoint.py::test_governed_start_persists_agent_run_and_plan` |
| `AgentPlan` | covered | `backend/app/models.py`, `backend/tests/test_workflow_runtime_endpoint.py::test_governed_start_persists_agent_run_and_plan` |
| `ToolCall` | covered | `AgentToolCall` table in `backend/app/models.py`, `backend/tests/test_workflow_runtime_endpoint.py::test_governed_start_persists_tool_calls_and_results` |
| `ToolResult` | covered | `AgentToolResult` table in `backend/app/models.py`, `backend/tests/test_workflow_runtime_endpoint.py::test_governed_start_persists_tool_calls_and_results` |
| `Proposal` | covered | `AgentProposal` table in `backend/app/models.py`, `backend/tests/test_task_mapping_endpoint.py::test_review_items_restore_tool_created_governed_proposals` |
| `EvidenceItem` | covered | `AgentEvidenceItem` table in `backend/app/models.py`, `backend/tests/test_task_mapping_endpoint.py::test_review_items_restore_tool_created_governed_proposals` |
| `ReviewDecision` | covered | `AgentReviewDecision` table in `backend/app/models.py`, `backend/tests/test_workflow_runtime_endpoint.py::test_governed_review_decision_persists_agent_decision_and_status` |
| `GovernanceDecision` | covered | Embedded on `AgentToolCall.governance_decision_json`, `backend/tests/test_workflow_runtime_endpoint.py::test_governed_start_persists_tool_calls_and_results` |
| `VerificationResult` | covered | `AgentVerificationResult` table in `backend/app/models.py`, `backend/tests/test_database_migrations.py::test_agent_verification_result_model_stores_json_values` |

## Section 21 Validation Matrix

| Criterion | Status | Evidence | Remaining gap |
| --- | --- | --- | --- |
| Runtime object persistence | covered | `backend/tests/test_section_21_validation_audit.py`, `backend/tests/test_database_migrations.py`, `backend/tests/test_workflow_runtime_endpoint.py` | Governance decisions are persisted as compact JSON on tool calls, not as a standalone table. |
| Generic governed graph demo path | partial | `backend/tests/test_workflow_runtime_endpoint.py::test_governed_start_form_fill_pauses_with_review_proposals`, `::test_governed_start_vendor_onboarding_maps_custom_profile_fields`, `::test_governed_start_security_questionnaire_uses_source_answer_proposals`, `::test_governed_start_web_data_extract_runs_read_only_page_plan`, `::test_governed_start_job_summary_runs_read_only_summary_plan` | Generic graph is primary for demo preparation and audited read-only workflow-specific paths; old security questionnaire graph remains as fallback. |
| Internal browser read/write Tool Runtime path | partial | `backend/tests/test_agent_runtime_tool_runtime.py`, `backend/tests/test_page_intake_service.py::test_analyze_page_intake_uses_tool_runtime_for_browser_reads`, `backend/tests/test_task_mapping_endpoint.py::test_analyze_persists_extract_form_runtime_call`, `::test_login_and_analyze_persists_extract_form_runtime_call`, `::test_extract_page_persists_runtime_call_without_raw_task_facade_output`, `::test_job_summary_page_extraction_persists_runtime_call`, `::test_rules_mapping_persists_map_fields_runtime_call`, `::test_llm_mapping_persists_map_fields_runtime_call`, `::test_capture_screenshot_persists_runtime_call`, `::test_fill_persists_runtime_tool_call_result`, `backend/tests/test_workflow_runtime_endpoint.py::test_governed_start_web_data_extract_runs_read_only_page_plan`, `::test_governed_start_job_summary_runs_read_only_summary_plan`, `backend/tests/test_job_worker.py::test_execute_job_rules_mapping_persists_runtime_call`, `::test_execute_job_llm_mapping_persists_runtime_call`, `::test_execute_fill_stage_persists_runtime_tool_call`, `backend/tests/test_confirm_submit.py::test_confirm_submit_records_submit_runtime_tool_call` | Legacy endpoints still exist; browser-write compatibility entrypoints remain, but audited read-only workflow-specific behavior now has a primary AgentRun plan/tool path. |
| Browser write and submit governance | covered | `backend/tests/test_agent_runtime_tool_runtime.py::test_tool_runtime_pauses_review_required_tools_before_handler`, `::test_tool_runtime_pauses_submit_tools_before_handler`, `backend/tests/test_workflow_runtime_endpoint.py::test_governed_review_rejection_does_not_resume_paused_fill_form`, `backend/tests/test_task_mapping_endpoint.py::test_fill_returns_409_when_approved_proposal_value_is_stale`, `backend/tests/test_task_mapping_endpoint.py::test_fill_returns_409_when_approved_proposal_selector_is_stale`, `backend/tests/test_confirm_submit.py::test_confirm_submit_first_request_creates_approval_and_returns_409` | Browser click/navigation proposals are display-only until executable action parity is built. |
| Verification trust layer | covered | `backend/tests/test_agent_runtime_tool_runtime.py::test_fill_form_wraps_browser_executor_after_approval`, `backend/tests/test_task_verification_endpoint.py::test_fill_creates_verified_results`, `backend/tests/test_task_verification_endpoint.py::test_fill_creates_failed_result_for_missing_selector`, `backend/tests/test_job_worker.py::test_execute_fill_stage_blocks_required_verification_failure`, `backend/tests/test_confirm_submit.py::test_confirm_submit_records_submit_runtime_tool_call`, `backend/tests/test_workflow_runtime_endpoint.py::test_save_governed_runtime_state_persists_verify_browser_state_result`, `backend/tests/test_governed_agent_graph.py::test_verify_browser_state_mismatch_fails_governed_run` | Old security questionnaire graph fallback has skeleton verification only and is not real browser verification evidence. |
| Review Queue primary proposal entry | covered | `backend/tests/test_task_mapping_endpoint.py::test_review_items_restore_persisted_proposals_before_deriving_from_fields`, `frontend/src/reviewMappingPresentation.test.js` | Legacy `/tasks` review items and FormField sync remain compatibility fallbacks. |
| Run Cockpit compact state | covered | `backend/tests/test_workflow_runtime_endpoint.py::test_governed_get_restores_compact_state_from_db_when_memory_state_is_missing`, `frontend/src/runCockpitPresentation.test.js`, `frontend/src/runCockpitActions.test.js` | Advanced/debug raw state remains backend-only. |
| No-key deterministic demos and benchmark replay | covered | `backend/tests/test_workflow_runtime_endpoint.py::test_governed_start_keeps_demo_paths_no_key_deterministic`, `backend/tests/test_benchmark_endpoint.py::test_run_benchmark_full_workflow_runs_without_provider`, `::test_run_benchmark_runtime_runs_without_provider` | Generic demo preparation and benchmark replay are covered; legacy fallback remains documented separately. |
| Read-only external tools | covered | `backend/tests/test_agent_runtime_external_tools.py` | External connector execution remains adapter-driven and allowlisted only. |
| External write tools | covered | `backend/tests/test_agent_runtime_external_tools.py::test_external_adapter_rejects_write_capable_mcp_tools`, `::test_external_adapter_rejects_write_capable_openapi_operations`, `frontend/src/reviewMappingPresentation.test.js::buildReviewQueueCompactItems guards external write proposals` | External writes are not executable; only compact display guards exist. |
| Docs and demo alignment | covered | `README.md`, `docs/roadmap/00-ai-engineer-alignment-roadmap.md`, `docs/agent-runtime-refactor-rfc.zh.md`, `docs/demo-script.md`, this audit | Keep future docs updates tied to behavior changes. |

## Raw Output Exposure Matrix

| Boundary | Validation | Evidence |
| --- | --- | --- |
| Task facade | covered | `backend/tests/test_task_mapping_endpoint.py::test_get_task_includes_compact_agent_runtime_state`, `::test_list_tasks_includes_compact_agent_runtime_state`, `::test_extract_page_persists_runtime_call_without_raw_task_facade_output` assert `tool_results`, `output_json`, and raw page output stay out of `agent_runtime`. |
| Run Cockpit | covered | `frontend/src/runCockpitPresentation.test.js::getRunCockpitToolCalls returns compact recent tool history` and `::getRunCockpitVerificationDetails returns compact evidence items` expose counts and compact evidence, not raw `output_json`. |
| Review Queue | covered | `frontend/src/reviewMappingPresentation.test.js::buildReviewQueueCompactItems shows browser action proposals compactly` and `::buildReviewQueueCompactItems guards external write proposals` strip nested `tool_results`; `backend/tests/test_task_mapping_endpoint.py::test_review_items_show_external_write_without_raw_tool_results` and `backend/tests/test_agent_run_read_endpoint.py::test_get_agent_run_review_items_strips_nested_raw_tool_payloads` strip backend proposal payloads. |
| External read-only tools | covered | `backend/tests/test_agent_runtime_external_tools.py::test_external_readonly_output_becomes_compact_tool_evidence` keeps raw output in `ToolResult.output_json` while producing compact `EvidenceItem` summaries for UI use. |
| Backend persistence | covered | `backend/tests/test_workflow_runtime_endpoint.py::test_governed_start_persists_tool_calls_and_results` proves raw `AgentToolResult.output_json` is persisted for backend recovery, and `::test_governed_get_restores_compact_state_from_db_when_memory_state_is_missing` proves compact restore omits raw markers. |

## Runtime API Boundary Matrix

| Boundary | Classification | Audit result |
| --- | --- | --- |
| `/agent-runs/{run_id}` | primary read boundary | Returns compact AgentRun state from persisted runtime rows without raw `tool_results` / `output_json`. |
| `/agent-runs/{run_id}/continue` | primary browser-write boundary | Continues AgentRun-backed reviewed fill by default, and accepts `{"action":"submit_form"}` for explicit-approved final submit through the shared submit path while preserving review/approval, policy, stale, Tool Runtime, verification, and compact facade gates. |
| `/agent-runs/{run_id}/review-items` | primary review boundary | Returns proposal-backed Review Queue items through AgentRun while preserving legacy FormField/checkpoint backfill and stripping nested raw tool payloads from proposal values. |
| `/agent-runs/{run_id}/review-items/{item_id}/decision` | primary review boundary | Writes `AgentReviewDecision` through AgentRun and keeps FormField sync only for field proposals. |
| `/workflows/{task_id}/governed/start` | primary | Generic governed AgentRun preparation boundary for no-key demo paths. |
| `/workflows/{task_id}/governed` | primary | Restores compact governed runtime state for Run Cockpit. |
| `/workflows/{task_id}/governed/review-items/{item_id}/decision` | primary | Writes AgentReviewDecision for proposal-backed review decisions. |
| `/tasks` | legacy facade | Lists task shells with compact AgentRun facade state only. |
| `/tasks/{task_id}` | legacy facade | Returns legacy task detail with compact `agent_runtime`, not raw tool results. |
| `/tasks/{task_id}/review-items` | compatibility fallback | Prefers persisted AgentProposal rows, then derives legacy FormField/checkpoint items when needed. |
| `/workflows/templates` | workflow-template endpoint | Static workflow template metadata only; not a runtime execution boundary. |
| `/workflows/{task_id}/start` | old security questionnaire graph fallback | Starts the old security-only graph and pauses at review; not the primary demo path. |
| `/workflows/{task_id}/review` | old security questionnaire graph fallback | Resumes the old graph after review, but the fill/verify nodes are skeleton-only and non-mutating. |
| `/tasks/{task_id}/extract-page` | read-only compatibility facade | Legacy facade retained; equivalent page extraction and screenshot reads are now expressible through governed AgentRun planned tool steps. |
| `/tasks/{task_id}/job-summary` | read-only compatibility facade | Legacy facade retained; equivalent prerequisite reads and deterministic summary are now expressible through governed AgentRun planned tool steps. |
| `/tasks/{task_id}/fill` | legacy browser-write compatibility runtime | Executes browser fill only after review/policy/stale gates and through Tool Runtime. |
| `/tasks/{task_id}/confirm-submit` | legacy submit compatibility runtime | Compatibility wrapper over the shared submit helper; executes submit only after explicit final-submit approval and Tool Runtime gates. |

## Task And Workflow Endpoint Evidence Matrix

| Boundary | Evidence | Coverage |
| --- | --- | --- |
| `/tasks/{task_id}` | compact `agent_runtime` without raw `tool_results` / `output_json` | `backend/tests/test_task_mapping_endpoint.py::test_get_task_includes_compact_agent_runtime_state` |
| `/tasks` | compact list facade without raw `tool_results` / `output_json` | `backend/tests/test_task_mapping_endpoint.py::test_list_tasks_includes_compact_agent_runtime_state` |
| `/tasks/{task_id}/extract-page` | records runtime output while keeping the task facade compact | `backend/tests/test_task_mapping_endpoint.py::test_extract_page_persists_runtime_call_without_raw_task_facade_output` |
| `/tasks/{task_id}/job-summary` prerequisite extraction | records `extract_page` and `capture_screenshot` runtime governance when no extraction checkpoint exists | `backend/tests/test_task_mapping_endpoint.py::test_job_summary_page_extraction_persists_runtime_call` |
| `/tasks/{task_id}/map-fields?provider=...` | LLM mapping executes through `map_fields` Tool Runtime and persists compact runtime evidence | `backend/tests/test_task_mapping_endpoint.py::test_llm_mapping_persists_map_fields_runtime_call` |
| `/tasks/{task_id}/fill` | legacy browser-write compatibility path uses review/policy/stale gates before Tool Runtime fill | `backend/tests/test_task_mapping_endpoint.py::test_fill_persists_runtime_tool_call_result`, `::test_fill_returns_409_when_approved_proposal_value_is_stale`, `::test_fill_returns_409_when_approved_proposal_selector_is_stale` |
| `/agent-runs/{run_id}/continue` | primary AgentRun reviewed-fill and explicit-submit boundary delegates to the shared fill/submit paths | `backend/tests/test_agent_run_read_endpoint.py::test_continue_agent_run_delegates_reviewed_fill_to_shared_task_path`, `::test_continue_agent_run_delegates_submit_to_shared_task_path` |
| `/tasks/{task_id}/confirm-submit` | legacy submit compatibility wrapper requires explicit approval before Tool Runtime submit | `backend/tests/test_confirm_submit.py::test_confirm_submit_first_request_creates_approval_and_returns_409`, `::test_confirm_submit_records_submit_runtime_tool_call` |
| `/workflows/{task_id}/governed` | restores compact state from persisted AgentRun data | `backend/tests/test_workflow_runtime_endpoint.py::test_governed_get_restores_compact_state_from_db_when_memory_state_is_missing` |
| `/workflows/{task_id}/start` | old security graph fallback pauses before skeleton fill | `backend/tests/test_security_questionnaire_graph.py::test_run_until_review_stops_before_fill` |

## Frontend Runtime Boundary Evidence Matrix

| Surface | Priority | Coverage |
| --- | --- | --- |
| Task Detail | Run Cockpit AgentRun state first and AgentRun continue for reviewed fill/final submit when a run id exists | `frontend/src/pages/TaskDetail.jsx`, `frontend/src/runCockpitActions.test.js::run cockpit reads AgentRun compact state before governed workflow fallback`, `frontend/src/runCockpitActions.test.js::continue run cockpit uses AgentRun boundary when run id exists`, `frontend/src/runCockpitActions.test.js::submit run cockpit uses AgentRun continue boundary when run id exists`, `frontend/src/taskRunState.test.js::getTaskRunState uses Run Cockpit review state before stale task status`, `frontend/src/taskRunState.test.js::getTaskRunState uses pending Run Cockpit review count before stale task status` |
| Run Cockpit | AgentRun compact state before governed workflow and task facade fallback | `frontend/src/runCockpitActions.test.js::run cockpit reads AgentRun compact state before governed workflow fallback`, `::run cockpit falls back to governed workflow when AgentRun read fails`, `::run cockpit reads governed workflow when no AgentRun id exists`, `::run cockpit falls back to task facade when primary reads fail` |
| Review Mapping | AgentRun review items before legacy task fallback | `frontend/src/reviewMappingActions.test.js::review mapping resolves AgentRun review items before task fallback`, `frontend/src/reviewMappingActions.test.js::review item decisions prefer AgentRun review boundary with task fallback`, `frontend/src/reviewMappingActions.test.js::field edits prefer AgentRun review boundary when a run id exists`, `frontend/src/reviewMappingActions.test.js::review item decisions fall back to task review when AgentRun review fails` |

## Phase A Frontend Boundary Audit

Status: completed for the frontend primary AgentRun boundary. The audit found
existing coverage for the required AgentRun-first read/review flows, so this
slice updated evidence only.

- Task Detail primary review affordance is driven by compact Run Cockpit runtime
  review state before stale legacy task status.
- Task Detail governed-run start navigation uses refreshed Run Cockpit runtime
  state before deciding whether to open Review Mapping.
- Run Cockpit reads `/agent-runs/{run_id}` first, then falls back to
  `/workflows/{task_id}/governed`, then the compact task facade.
- Run Cockpit without an AgentRun id has focused coverage for the governed
  workflow fallback path.
- Review Mapping reads and writes AgentRun review items first when a run id is
  present, then falls back to legacy task review items.
- Field edits backed by proposals now have focused coverage for the AgentRun
  review boundary, and AgentRun decision failure has focused legacy task
  fallback coverage.
- Legacy task status, governed workflow, task facade, FormField sync, and
  legacy review-item compatibility paths remain documented migration fallbacks.
- Frontend compact helpers keep raw `tool_results` / `output_json` out of the
  primary UI; raw trace/page JSON remains behind advanced/debug disclosure.

Run Cockpit now reads AgentRun compact state first when `agent_run_id` or
`agent_runtime.run_id` is present, then uses the governed workflow fallback,
then the task facade fallback. Task Detail also uses the refreshed Run Cockpit
runtime state after starting a governed run before deciding whether to navigate
to Review Mapping. Task Detail's static primary action also treats compact
runtime `WAITING_REVIEW`, `interrupt_at: review`, or `pending_review_count > 0`
as review-ready before stale legacy task status.

## Phase B Backend Boundary Audit

Status: completed for backend AgentRun/review boundary evidence. The sweep found
one real compactness gap in nested proposal values, fixed it at the shared
review proposal compaction helper, and added focused endpoint coverage.

- `/agent-runs/{run_id}` has focused backend coverage for compact persisted
  state without raw `tool_results`, `output_json`, or raw output markers.
- `/agent-runs/{run_id}/review-items` now strips nested raw tool payloads from
  persisted proposal values before returning proposal-backed review items.
- `/agent-runs/{run_id}/review-items/{item_id}/decision` writes
  `AgentReviewDecision` through the AgentRun boundary.
- FormField sync remains limited to field proposals; non-field proposals such
  as `memory_write` stay runtime-only.
- Legacy `/tasks/{task_id}/review-items` fallback, FormField sync compatibility,
  workflow-specific endpoints, old security questionnaire graph fallback, and
  the legacy `/tasks` facade remain documented migration gaps.
- This closes Phase B backend AgentRun/review boundary evidence only, not the
  overall runtime refactor.

## Stage 3 Tool Runtime Coverage Audit

Status: backend legacy path audit closed. This audit found one additional real
legacy backend gap and fixed it without changing the no-key deterministic rules
path.

- Already wrapped or covered: page intake browser reads, legacy analyze,
  login-and-analyze, rules mapping, LLM mapping, page extraction, fill, submit,
  and generic verification persistence.
- Fixed in this slice: legacy screenshot capture now executes through the
  `capture_screenshot` runtime tool and persists compact `AgentToolCall` /
  `AgentToolResult` evidence.
- Still legacy by design: `/tasks` remains a compatibility facade,
  workflow-specific endpoints remain, old security questionnaire graph fallback
  remains, and benchmark internals still use direct fixture helpers for local
  evaluation rather than becoming product runtime code.

## Stage 4A Tool Runtime Governance Coverage Sweep

Status: completed for already-runtime-backed product legacy paths. This is a
governance evidence sweep, not the overall Stage 4 governance refactor.

- `extract_form` legacy analyze, login-and-analyze, and worker analyze persist
  `ALLOW` governance decisions on `AgentToolCall.governance_decision_json`.
- `extract_page` legacy page extraction and job-summary prerequisite extraction
  persist `ALLOW` governance decisions.
- `capture_screenshot` standalone capture, page extraction, and job-summary
  prerequisite screenshots now persist `ALLOW` governance decisions.
- `map_fields` rules and LLM endpoint/worker paths persist `RECORD_ONLY`
  governance decisions.
- `fill_form` endpoint and worker browser writes persist `VERIFY_REQUIRED`
  governance after required review/approval gates.
- `submit_form` persists `VERIFY_REQUIRED` only after explicit final-submit
  approval; first submit requests still create approval/review state and return
  409.
- Compatibility facades remain compact: raw `tool_results`, `output_json`, and
  nested raw payloads stay out of primary task/AgentRun/Review Queue responses.

Fixed in this slice:

- `/tasks/{task_id}/extract-page` and `/tasks/{task_id}/job-summary`
  prerequisite extraction no longer call the screenshot helper directly; both
  route the screenshot side effect through `capture_screenshot` Tool Runtime and
  persist compact governance evidence.

## Stage 4B Governance Negative Coverage Sweep

Status: completed for negative governance enforcement in audited product
runtime paths. This is not the overall Stage 4 governance refactor.

- Fixed: exact tool-call approval is enforced by `approved_tool_call_ids`;
  `approved_tool_names` no longer grants broad approval for same-named future
  calls.
- Fixed: sensitive browser mutation checks inspect real field-object payloads,
  covering the legacy `fill_form` wrapper shape in addition to dict/list inputs.
- Already covered: unapproved `fill_form` and `submit_form` calls pause before
  handlers execute; final submit creates/persists an approval and returns 409
  until explicit approval.
- Already covered: external write-capable MCP/OpenAPI tools reject
  registration; `external_api_write` proposals are compact display-only items.
- Already covered: sensitive memory writes are blocked, consent-like writes
  require exact-action approval, and governed review decisions do not write
  workflow memory directly.
- Kept out of scope: benchmark/test fixture helpers, workflow-template
  compatibility endpoints that do not execute dangerous actions, and the old
  security questionnaire graph fallback.

## Stage 4C Governed Browser Action Resume/Parity Sweep

Status: completed for governed browser action resume/parity in audited product
runtime paths. This is not the overall Stage 4 governance refactor.

- Fixed: `rejected` governed review decisions no longer trigger
  `resume_governed_runtime_from_review`, so they cannot approve or execute a
  paused `fill_form` browser write.
- Fixed: approved or edited field proposals cannot be reused after the mapped
  field value changes; stale fill proposals block `/tasks/{task_id}/fill`
  before browser execution.
- Already covered: `needs_more_evidence` decisions do not resume governed
  review pauses.
- Already covered: governed submit approval resume is limited to
  `submit_form`, starts only from `/tasks/{task_id}/confirm-submit`, and skips
  stale field-value or selector snapshots.
- Already covered: legacy `/tasks/{task_id}/fill` and async fill jobs execute
  through the same `split_fields_by_browser_write_review` and Tool Runtime
  gates.
- Already covered: executed `fill_form` writes verification candidates and
  persisted generic verification evidence; executed `submit_form` writes
  submit verification evidence.
- Already covered: `browser_click` and `browser_navigation` proposals are
  display-only compact review items.
- Kept out of scope: benchmark/test fixture helpers, compatibility facades that
  do not execute dangerous browser actions, and the old security questionnaire
  graph fallback unless it can bypass dangerous actions.

## Stage 4D Governance Closure Audit

Status: completed. Stage 4 governance is closed for true product runtime
enforcement paths; this is not an overall runtime refactor completion claim.

- Fixed: approved or edited runtime field proposals cannot be reused after the
  mapped field selector changes; stale selector snapshots now block fill before
  browser execution.
- Covered: browser fill reaches Tool Runtime through sync `/tasks/{task_id}/fill`
  and async fill jobs after the same review, stale-proposal, policy, and
  approval gates.
- Covered: final submit reaches Tool Runtime only through explicit
  `/tasks/{task_id}/confirm-submit` approval and exact field/selector snapshot
  checks.
- Covered: `rejected` and `needs_more_evidence` decisions cannot resume paused
  browser writes.
- Covered: password, OTP, payment, CAPTCHA, and token browser inputs are
  blocked; consent-like browser inputs are review/approval-gated; sensitive
  memory writes are blocked and consent-like memory writes are gated.
- Covered: legacy `/tasks` fill/submit facades route through governed/runtime
  gates before dangerous execution.
- Covered: browser click/navigation proposals are display-only because no
  executable product browser click/navigation tool is registered.
- Compatibility gap only: the old security questionnaire graph fallback remains
  but its fill node is non-mutating and does not execute dangerous actions.

## Stage 5 Verification Generalization Sweep

Status: completed for governed runtime verification trust paths. This is not an
overall runtime refactor completion claim.

- Fixed: sync fill failures caused by required field readback mismatch now
  persist generic `AgentVerificationResult` evidence before the API fails.
- Fixed: async fill jobs now fail on required field readback mismatch and keep
  generic verification evidence, matching the sync fill path.
- Covered: fill produces field-level verification candidates and persists
  generic verification rows from DOM readback.
- Covered: submit persists page_state verification evidence only after explicit
  final-submit approval.
- Covered: generic `verify_browser_state` results persist as
  `AgentVerificationResult` and mismatch output fails governed runs.
- Covered: Run Cockpit presents only compact verification status, mismatch
  count, up to three mismatches, and up to three compact evidence lines.
- Covered: benchmark/runtime mode still includes `verification_pass_rate` in
  no-key deterministic coverage.
- Compatibility gap only: old security questionnaire graph fallback skeleton
  verification can say `verified: true` without real browser verification, but
  the fallback's fill node is non-mutating, so it is not a dangerous execution
  success path.

## Stage 6 Compatibility Runtime Boundary Retirement Sweep

Status: completed for runtime boundary classification. No production runtime
gap was found, so this slice changed documentation only and did not delete
legacy endpoints.

- Primary AgentRun runtime boundary: `/agent-runs/{run_id}`,
  `/agent-runs/{run_id}/review-items`,
  `/agent-runs/{run_id}/review-items/{item_id}/decision`,
  `/workflows/{task_id}/governed/start`,
  `/workflows/{task_id}/governed`, and
  `/workflows/{task_id}/governed/review-items/{item_id}/decision`.
- Legacy facade: `/tasks` and `/tasks/{task_id}` expose task shells plus
  compact `agent_runtime` state only; they do not expose raw `tool_results`,
  `output_json`, or `raw_output_json`.
- Compatibility fallback: `/tasks/{task_id}/review-items` still backfills
  FormField/checkpoint review rows only when persisted `AgentProposal` rows are
  missing. It does not bypass the AgentRun review boundary when a run id is
  available.
- Workflow-template endpoint: `/workflows/templates` is static template
  metadata, not runtime execution.
- Workflow-specific compatibility paths with real read-only product behavior:
  `/tasks/{task_id}/extract-page` and the prerequisite extraction inside
  `/tasks/{task_id}/job-summary` still execute page reads and screenshots, but
  those reads route through `extract_page` and `capture_screenshot` Tool
  Runtime wrappers and keep facade output compact.
- Workflow-specific compatibility paths with real browser write behavior:
  `/tasks/{task_id}/fill`, async fill jobs, and
  `/tasks/{task_id}/confirm-submit` remain legacy entrypoints, but audited
  browser writes route through Tool Runtime plus review, approval, stale-value,
  stale-selector, policy, and verification gates.
- Old security questionnaire graph fallback: `/workflows/{task_id}/start`,
  `/workflows/{task_id}`, and `/workflows/{task_id}/review` remain
  compatibility endpoints for the old in-memory graph. Its `fill_browser` and
  `verify_result` nodes are skeleton-only and do not perform real Playwright or
  `BrowserExecutor` browser execution/verification.
- Frontend fallback/read helpers: Task Detail, Run Cockpit, and Review Mapping
  are AgentRun-first. Governed workflow, task facade, old workflow state, and
  legacy review item reads remain compatibility fallbacks.
- Benchmark/test fixture helpers: runtime benchmark fixture tools and direct
  local fixture replay are evaluation harness code, not product runtime gaps.

Fixed in this slice:

- None. The audit found classification/doc drift only.

## Stage 7 Workflow-Specific Read Runtime Migration

Status: completed for audited read-only product paths. This is not an overall
runtime refactor completion claim.

- Fixed: `/workflows/{task_id}/governed/start` now admits `web_data_extract`
  and plans `extract_page` plus `capture_screenshot` as low-risk AgentRun tool
  steps, so page extraction has a primary generic run path before the legacy
  `/tasks/{task_id}/extract-page` facade is used.
- Fixed: `/workflows/{task_id}/governed/start` now admits
  `job_research_summary` and plans `extract_page`, `capture_screenshot`, and
  deterministic `generate_job_summary` as low-risk AgentRun tool steps.
- Fixed: `generate_job_summary` is registered as a read-only Tool Runtime
  wrapper over the existing deterministic `generate_research_summary` service;
  it consumes the prior `extract_page` tool output from generic runtime state.
- Covered: page intake already runs `extract_form` and `extract_page` through
  Tool Runtime; this slice keeps it as an intake classifier/checkpoint path
  while read-only workflow execution moves to governed AgentRun plans.
- Covered: Run Cockpit can show the resulting compact read-only AgentRun state
  through existing plan/tool-call helpers without exposing `output_json`.
- Kept: legacy `/tasks/{task_id}/extract-page` and
  `/tasks/{task_id}/job-summary` remain compatibility facades and still write
  legacy checkpoints/logs for the existing UI.
- Kept out of scope: deleting endpoints, adding dashboards, changing no-key
  deterministic behavior, and converting benchmark/test fixture helpers into
  product runtime code.

Evidence:

- `backend/tests/test_workflow_runtime_endpoint.py::test_governed_start_web_data_extract_runs_read_only_page_plan`
- `backend/tests/test_workflow_runtime_endpoint.py::test_governed_start_job_summary_runs_read_only_summary_plan`
- `backend/tests/test_section_21_validation_audit.py::test_stage_7_read_runtime_migration_status_is_reflected`

## Stage 8 Browser-Write Compatibility Runtime Migration Audit

Status: completed as an audit only. No production code changes were made. This
does not close browser-write runtime migration or the overall runtime refactor.

- Audited: `/tasks/{task_id}/fill` is still the browser-write runtime center
  for the user fill action. It validates `READY_TO_FILL`, required mappings,
  proposal approval freshness, policy approvals, and then calls
  `execute_fill_form_runtime_tool`.
- Audited: async fill jobs still bypass a primary AgentRun continue endpoint,
  but they use the same `filter_fillable_fields_by_policy`,
  `split_fields_by_browser_write_review`, `execute_fill_form_runtime_tool`, and
  failed required verification gate as synchronous fill.
- Audited: `/tasks/{task_id}/confirm-submit` is still the submit execution
  center. It creates or requires explicit final-submit approval, rejects stale
  approval snapshots, tries governed approval resume when a persisted
  `submit_form` pause matches the current field/selector snapshot, and only
  then falls back to `execute_submit_form_runtime_tool`.
- Audited: governed runtime has review and approval resume state for paused
  `fill_form` / `submit_form` tool calls through
  `resume_governed_runtime_from_review`,
  `resume_governed_runtime_from_approval`, and exact
  `approved_tool_call_ids`.
- Audited: `fill_form` and `submit_form` Tool Runtime coverage is complete for
  current product browser writes: both tools are registered as browser-mutating
  tools, require exact prior approval to execute, and persist compact
  `AgentToolCall` / `AgentToolResult` state.
- Audited: review, approval, stale-value, stale-selector, policy, and
  verification gates are shared by the synchronous and async legacy fill paths;
  submit has shared explicit approval plus stale snapshot checks before any
  browser execution.
- Audited: Run Cockpit can show browser-write AgentRun state through compact
  restored plan, tool-call, governance, and verification summaries.
- Audited: the task facade remains compact and does not expose raw
  `output_json`, `tool_results`, or `raw_output_json`.
- Audited: benchmark and test fixture helpers are evaluation support code, not
  product runtime gaps.

Migration conclusion:

- Not migrated yet: there is no primary browser-write
  `/agent-runs/{run_id}/continue` style boundary for reviewed fill execution,
  async fill job continuation, or final submit execution.
- Keep: legacy `/tasks/{task_id}/fill`, async fill jobs, and
  `/tasks/{task_id}/confirm-submit` must remain compatibility endpoints until a
  real AgentRun continue boundary owns browser-write execution.
- Next thin slice: add a primary AgentRun continue/browser-write endpoint that
  reuses the existing shared gates and Tool Runtime wrappers, then make legacy
  `/tasks` write endpoints delegate to it.

## Stage 9 Primary AgentRun Browser-Write Continue Boundary Thin Slice

Status: completed for reviewed fill execution only. This is not an overall
browser-write migration completion claim and not an overall runtime refactor
completion claim.

- Fixed: `/agent-runs/{run_id}/continue` now resolves the persisted AgentRun
  and continues reviewed fill through the same shared fill path used by
  `/tasks/{task_id}/fill`, preserving `READY_TO_FILL`, proposal review,
  stale-value, stale-selector, policy approval, Tool Runtime, and verification
  gates.
- Fixed: Task Detail now calls `/agent-runs/{run_id}/continue` for the fill
  action when `agent_run_id` or `agent_runtime.run_id` exists; no-run-id tasks
  still call legacy `/tasks/{task_id}/fill`.
- Covered: Run Cockpit can display the resulting `fill_form` AgentRun state
  through the existing compact AgentRun read helper without exposing
  `tool_results`, `output_json`, or `raw_output_json`.
- Kept: legacy `/tasks/{task_id}/fill` remains as a compatibility endpoint and
  no-run-id frontend fallback.
- Remaining: async fill jobs still execute through the legacy job worker, even
  though they reuse the same shared fill gates and Tool Runtime helper.
- Remaining: `/tasks/{task_id}/confirm-submit` remains the legacy final-submit
  compatibility runtime center.
- Kept out of scope: new dashboards, new dependencies, endpoint deletion,
  final-submit migration, and the old security questionnaire graph fallback.

Evidence:

- `backend/tests/test_agent_run_read_endpoint.py::test_continue_agent_run_delegates_reviewed_fill_to_shared_task_path`
- `backend/tests/test_agent_run_read_endpoint.py::test_continue_agent_run_returns_404_for_missing_run`
- `frontend/src/api.test.js::agent run API client uses primary continue boundary`
- `frontend/src/runCockpitActions.test.js::continue run cockpit uses AgentRun boundary when run id exists`
- `frontend/src/runCockpitActions.test.js::continue run cockpit falls back to legacy fill without run id`

## Stage 10 Primary AgentRun Submit Continue Boundary Thin Slice

Status: completed for explicit final submit execution. This is not an overall
browser-write migration completion claim and not an overall runtime refactor
completion claim.

- Fixed: `/agent-runs/{run_id}/continue` now accepts `{"action":"submit_form"}`
  and continues AgentRun-backed final submit through the same shared submit path
  used by legacy `/tasks/{task_id}/confirm-submit`.
- Fixed: legacy `/tasks/{task_id}/confirm-submit` is now a compatibility
  wrapper over the shared submit helper instead of owning a separate route body.
- Fixed: Task Detail now sends final submit through the AgentRun continue
  boundary when `agent_run_id` or `agent_runtime.run_id` exists; no-run-id tasks
  still call legacy `/tasks/{task_id}/confirm-submit`.
- Covered: the first AgentRun submit continue request still creates/persists a
  final-submit approval and returns 409 without executing `submit_form`.
- Covered: after approval, AgentRun submit continue executes `submit_form`
  through Tool Runtime and persists compact `AgentToolCall`, `AgentToolResult`,
  and submit verification state.
- Covered by shared submit path: stale approved field values and stale selector
  snapshots cannot reuse old approval; governed approval resume only matches
  the current submit field snapshot.
- Kept: final submit still requires explicit user approval, legacy
  confirm-submit remains as the compatibility fallback, and task facade output
  stays compact without `tool_results` / `output_json`.
- Remaining: async fill jobs still execute through the legacy job worker, even
  though they reuse shared fill gates and Tool Runtime helpers.
- Kept out of scope: new dashboards, new dependencies, endpoint deletion, async
  fill job migration, and the old security questionnaire graph fallback.

Evidence:

- `backend/tests/test_agent_run_read_endpoint.py::test_continue_agent_run_delegates_submit_to_shared_task_path`
- `backend/tests/test_confirm_submit.py::test_confirm_submit_first_request_creates_approval_and_returns_409`
- `backend/tests/test_confirm_submit.py::test_confirm_submit_records_submit_runtime_tool_call`
- `frontend/src/api.test.js::agent run API client sends submit continue action payload`
- `frontend/src/runCockpitActions.test.js::submit run cockpit uses AgentRun continue boundary when run id exists`
- `frontend/src/runCockpitActions.test.js::submit run cockpit falls back to legacy confirm submit without run id`

## Stage 11 Browser-Write Runtime Migration Closure

Status: completed for AgentRun-backed async fill. This is not an overall
runtime refactor completion claim.

- Fixed: AgentRun fill continuation now passes `agent_run_id` into queued
  `FILL_FORM` jobs when async mode is enabled.
- Fixed: AgentRun-backed `FILL_FORM` jobs now delegate through the AgentRun
  fill continuation helper and execute without re-enqueueing.
- Kept: legacy `/tasks/{task_id}/fill` enqueue behavior remains compatible and
  still writes an empty job payload.
- Kept: review-first fill gates, stale-value checks, stale-selector checks,
  Tool Runtime execution, and required readback failure persistence continue to
  come from the shared fill path.
- Kept: `/tasks/{task_id}/confirm-submit` remains the explicit final-submit
  compatibility wrapper.
- Kept out of scope: new dashboards, new dependencies, endpoint deletion, old
  security questionnaire graph fallback, and claiming the overall runtime
  refactor is complete.

Evidence:

- `backend/tests/test_agent_run_read_endpoint.py::test_continue_agent_run_enqueues_async_fill_with_run_id`
- `backend/tests/test_job_worker.py::test_execute_fill_stage_delegates_agent_run_backed_job`
- `backend/tests/test_task_job_enqueue.py::test_fill_endpoint_creates_job_when_ready`

## Compatibility Paths Kept

- `/tasks` task detail and list facades.
- `FormField` fallback and synchronization for field proposals.
- legacy `/tasks/{task_id}/review-items` fallback when no persisted `AgentProposal` exists.
- Explicit approval endpoints for final submit and policy gates.
- Old security questionnaire graph fallback.
- Workflow-specific page extraction and job summary endpoints remain
  compatibility facades now that their audited read-only behavior is
  expressible as generic AgentRun planned tool steps.
- `/tasks/{task_id}/fill` remains a browser-write compatibility endpoint and
  no-run-id fallback after Stage 9; `/tasks/{task_id}/confirm-submit` remains
  a no-run-id compatibility wrapper after Stage 10; AgentRun-backed async fill
  jobs now delegate through the Stage 11 continuation helper.
- Benchmark/test fixture helpers remain direct local evaluation helpers and are
  not product runtime boundaries.

## Remaining Migration Gaps

- The legacy `/tasks` facade remains the compatibility shell for task detail and list views.
- workflow-specific endpoints remain, but they are now classified as static
  template metadata, read-only compatibility facades, legacy browser-write
  compatibility runtime paths, or old security graph fallback.
- old security questionnaire graph fallback remains until generic runtime
  parity is complete; it is not trusted for real browser execution or
  verification evidence.
- `/tasks/{task_id}/extract-page` and `/tasks/{task_id}/job-summary` still
  preserve legacy checkpoints/logs as compatibility facades; the audited
  read-only page extraction, screenshot, and deterministic summary behavior now
  has generic AgentRun planned tool step coverage.
- `/tasks/{task_id}/fill` still carries real browser-write product behavior as
  a legacy compatibility entrypoint; `/tasks/{task_id}/confirm-submit` remains
  a compatibility wrapper over the shared submit helper. Both are gated through
  Tool Runtime, review/approval, stale checks, policy, and verification.
- Async and synchronous legacy LLM mapping are now covered by Tool Runtime.
- Legacy screenshot capture is now covered by Tool Runtime.
- Page extraction and job-summary prerequisite screenshots are now covered by
  `capture_screenshot` Tool Runtime governance evidence.
- Stage 4B closed the audited negative enforcement gaps for exact tool-call
  approvals and sensitive field-object browser inputs.
- Stage 4C closed the audited browser action resume/parity gaps for rejected
  governed review resume and stale field proposal fill approvals.
- Stage 4D closed Stage 4 governance for true product runtime enforcement paths
  after fixing stale selector reuse for runtime-backed fill proposals.
- Stage 5 closed verification generalization for governed runtime trust paths
  after fixing sync failed-fill generic evidence and async required mismatch
  failure parity.
- Stage 6 closed compatibility runtime boundary classification; no production
  runtime boundary gap was found.
- Stage 7 closed the audited workflow-specific read runtime migration for page
  extraction and job summary by adding generic AgentRun read plans and a
  deterministic `generate_job_summary` Tool Runtime wrapper.
- Stage 8 closed the browser-write compatibility runtime migration audit only.
  No unsafe product runtime bypass was found.
- Stage 9 closed the reviewed-fill AgentRun continue boundary thin slice:
  `/agent-runs/{run_id}/continue` now owns AgentRun-backed reviewed fill from
  the primary UI/API path.
- Stage 10 closed the explicit-submit AgentRun continue boundary thin slice:
  `/agent-runs/{run_id}/continue` now owns AgentRun-backed final submit from
  the primary UI/API path through `{"action":"submit_form"}`.
- Stage 11 closed AgentRun-backed async fill migration by tagging queued fill
  jobs with `agent_run_id` and delegating those jobs back through the AgentRun
  fill continuation helper without changing legacy task fill job payloads.
- Review Mapping now reads AgentRun review items first when `agent_run_id` or `agent_runtime.run_id` is present, then falls back to legacy `/tasks/{task_id}/review-items`.
- Review Mapping still keeps legacy `/tasks/{task_id}/review-items` fallback and FormField sync compatibility during migration.
- Phase A closes only the frontend AgentRun boundary. Backend compatibility
  paths and broader runtime migration gaps remain.
