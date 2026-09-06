# Section 21 Validation Audit

Date: 2026-09-06

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
| Generic governed graph demo path | partial | `backend/tests/test_workflow_runtime_endpoint.py::test_governed_start_form_fill_pauses_with_review_proposals`, `::test_governed_start_vendor_onboarding_maps_custom_profile_fields`, `::test_governed_start_security_questionnaire_uses_source_answer_proposals` | Generic graph is primary for demo preparation; old security questionnaire graph remains as fallback. |
| Internal browser read/write Tool Runtime path | partial | `backend/tests/test_agent_runtime_tool_runtime.py`, `backend/tests/test_task_mapping_endpoint.py::test_analyze_persists_extract_form_runtime_call`, `::test_fill_persists_runtime_tool_call_result`, `backend/tests/test_confirm_submit.py::test_confirm_submit_records_submit_runtime_tool_call` | Legacy endpoints still exist; some paths record compact convergence state rather than being pure Agent Runtime API calls. |
| Browser write and submit governance | covered | `backend/tests/test_agent_runtime_tool_runtime.py::test_tool_runtime_pauses_review_required_tools_before_handler`, `::test_tool_runtime_pauses_submit_tools_before_handler`, `backend/tests/test_confirm_submit.py::test_confirm_submit_first_request_creates_approval_and_returns_409` | Browser click/navigation proposals are display-only until executable action parity is built. |
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
| Review Queue | covered | `frontend/src/reviewMappingPresentation.test.js::buildReviewQueueCompactItems shows browser action proposals compactly` and `::buildReviewQueueCompactItems guards external write proposals` strip nested `tool_results`; `backend/tests/test_task_mapping_endpoint.py::test_review_items_show_external_write_without_raw_tool_results` strips backend proposal payloads. |
| External read-only tools | covered | `backend/tests/test_agent_runtime_external_tools.py::test_external_readonly_output_becomes_compact_tool_evidence` keeps raw output in `ToolResult.output_json` while producing compact `EvidenceItem` summaries for UI use. |
| Backend persistence | covered | `backend/tests/test_workflow_runtime_endpoint.py::test_governed_start_persists_tool_calls_and_results` proves raw `AgentToolResult.output_json` is persisted for backend recovery, and `::test_governed_get_restores_compact_state_from_db_when_memory_state_is_missing` proves compact restore omits raw markers. |

## Runtime API Boundary Matrix

| Boundary | Classification | Audit result |
| --- | --- | --- |
| `/agent-runs/{run_id}` | primary read boundary | Returns compact AgentRun state from persisted runtime rows without raw `tool_results` / `output_json`. |
| `/agent-runs/{run_id}/review-items` | primary review boundary | Returns proposal-backed Review Queue items through AgentRun while preserving legacy FormField/checkpoint backfill. |
| `/agent-runs/{run_id}/review-items/{item_id}/decision` | primary review boundary | Writes `AgentReviewDecision` through AgentRun and keeps FormField sync only for field proposals. |
| `/workflows/{task_id}/governed/start` | primary | Generic governed AgentRun preparation boundary for no-key demo paths. |
| `/workflows/{task_id}/governed` | primary | Restores compact governed runtime state for Run Cockpit. |
| `/workflows/{task_id}/governed/review-items/{item_id}/decision` | primary | Writes AgentReviewDecision for proposal-backed review decisions. |
| `/tasks` | legacy facade | Lists task shells with compact AgentRun facade state only. |
| `/tasks/{task_id}` | legacy facade | Returns legacy task detail with compact `agent_runtime`, not raw tool results. |
| `/tasks/{task_id}/review-items` | compatibility fallback | Prefers persisted AgentProposal rows, then derives legacy FormField/checkpoint items when needed. |
| `/workflows/*` | workflow-specific compatibility | Workflow-template and old graph endpoints remain during migration. |

## Task And Workflow Endpoint Evidence Matrix

| Boundary | Evidence | Coverage |
| --- | --- | --- |
| `/tasks/{task_id}` | compact `agent_runtime` without raw `tool_results` / `output_json` | `backend/tests/test_task_mapping_endpoint.py::test_get_task_includes_compact_agent_runtime_state` |
| `/tasks` | compact list facade without raw `tool_results` / `output_json` | `backend/tests/test_task_mapping_endpoint.py::test_list_tasks_includes_compact_agent_runtime_state` |
| `/tasks/{task_id}/extract-page` | records runtime output while keeping the task facade compact | `backend/tests/test_task_mapping_endpoint.py::test_extract_page_persists_runtime_call_without_raw_task_facade_output` |
| `/workflows/{task_id}/governed` | restores compact state from persisted AgentRun data | `backend/tests/test_workflow_runtime_endpoint.py::test_governed_get_restores_compact_state_from_db_when_memory_state_is_missing` |

## Frontend Runtime Boundary Evidence Matrix

| Surface | Priority | Coverage |
| --- | --- | --- |
| Task Detail | Run Cockpit AgentRun state first | `frontend/src/pages/TaskDetail.jsx`, `frontend/src/runCockpitActions.test.js::run cockpit reads AgentRun compact state before governed workflow fallback`, `frontend/src/taskRunState.test.js::getTaskRunState uses Run Cockpit review state before stale task status`, `frontend/src/taskRunState.test.js::getTaskRunState uses pending Run Cockpit review count before stale task status` |
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

## Compatibility Paths Kept

- `/tasks` task detail and list facades.
- `FormField` fallback and synchronization for field proposals.
- legacy `/tasks/{task_id}/review-items` fallback when no persisted `AgentProposal` exists.
- Explicit approval endpoints for final submit and policy gates.
- Old security questionnaire graph fallback.

## Remaining Migration Gaps

- The legacy `/tasks` facade remains the compatibility shell for task detail and list views.
- workflow-specific endpoints remain for template, compatibility, and older workflow paths.
- old security questionnaire graph fallback remains until generic runtime parity is complete.
- Review Mapping now reads AgentRun review items first when `agent_run_id` or `agent_runtime.run_id` is present, then falls back to legacy `/tasks/{task_id}/review-items`.
- Review Mapping still keeps legacy `/tasks/{task_id}/review-items` fallback and FormField sync compatibility during migration.
- Phase A closes only the frontend AgentRun boundary. Backend compatibility
  paths and broader runtime migration gaps remain.
