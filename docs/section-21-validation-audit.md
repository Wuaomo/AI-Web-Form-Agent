# Section 21 Validation Audit

Date: 2026-09-03

Scope: RFC section 21 validation only. This audit records current evidence and
remaining gaps; it does not mark the full runtime refactor complete.

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
| Run Cockpit compact state | covered | `backend/tests/test_workflow_runtime_endpoint.py::test_governed_get_restores_compact_state_from_db_when_memory_state_is_missing`, `frontend/src/runCockpitPresentation.test.js` | Advanced/debug raw state remains backend-only. |
| No-key deterministic demos and benchmark replay | covered | `backend/tests/test_workflow_runtime_endpoint.py::test_governed_start_keeps_demo_paths_no_key_deterministic`, `backend/tests/test_benchmark_endpoint.py::test_run_benchmark_full_workflow_runs_without_provider`, `::test_run_benchmark_runtime_runs_without_provider` | Generic demo preparation and benchmark replay are covered; legacy fallback remains documented separately. |
| Read-only external tools | covered | `backend/tests/test_agent_runtime_external_tools.py` | External connector execution remains adapter-driven and allowlisted only. |
| External write tools | covered | `backend/tests/test_agent_runtime_external_tools.py::test_external_adapter_rejects_write_capable_mcp_tools`, `::test_external_adapter_rejects_write_capable_openapi_operations`, `frontend/src/reviewMappingPresentation.test.js::buildReviewQueueCompactItems guards external write proposals` | External writes are not executable; only compact display guards exist. |
| Docs and demo alignment | partial | `README.md`, `docs/architecture.md`, `docs/demo-script.md`, this audit | README/RFC/roadmap still need final audit-status wording after validation slices finish. |

## Raw Output Exposure Matrix

| Boundary | Validation | Evidence |
| --- | --- | --- |
| Task facade | covered | `backend/tests/test_task_mapping_endpoint.py::test_get_task_includes_compact_agent_runtime_state`, `::test_list_tasks_includes_compact_agent_runtime_state`, `::test_extract_page_persists_runtime_call_without_raw_task_facade_output` assert `tool_results` and raw page output stay out of `agent_runtime`. |
| Run Cockpit | covered | `frontend/src/runCockpitPresentation.test.js::getRunCockpitToolCalls returns compact recent tool history` and `::getRunCockpitVerificationDetails returns compact evidence items` expose counts and compact evidence, not raw `output_json`. |
| Review Queue | covered | `frontend/src/reviewMappingPresentation.test.js::buildReviewQueueCompactItems shows browser action proposals compactly` and `::buildReviewQueueCompactItems guards external write proposals` strip nested `tool_results`; `backend/tests/test_task_mapping_endpoint.py::test_review_items_show_external_write_without_raw_tool_results` strips backend proposal payloads. |
| External read-only tools | covered | `backend/tests/test_agent_runtime_external_tools.py::test_external_readonly_output_becomes_compact_tool_evidence` keeps raw output in `ToolResult.output_json` while producing compact `EvidenceItem` summaries for UI use. |
| Backend persistence | covered | `backend/tests/test_workflow_runtime_endpoint.py::test_governed_start_persists_tool_calls_and_results` proves raw `AgentToolResult.output_json` is persisted for backend recovery, and `::test_governed_get_restores_compact_state_from_db_when_memory_state_is_missing` proves compact restore omits raw markers. |

## Compatibility Paths Kept

- `/tasks` task detail and list facades.
- `FormField` fallback and synchronization for field proposals.
- Legacy review items when no persisted `AgentProposal` exists.
- Explicit approval endpoints for final submit and policy gates.
- Old security questionnaire graph fallback.
