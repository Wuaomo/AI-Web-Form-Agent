# Compatibility Removal Map

Compatibility Removal Planning & Primary Path Consolidation Track

Status: Workflow compatibility endpoint removal was consolidated across the old
security graph endpoints, read-only workflow compatibility endpoints, and
legacy task review endpoints. The read-only frontend fallback helper and
Review Mapping legacy task review fallback/helper have been removed:
read-only workflow starts now surface governed deterministic start failures,
and Review Mapping now surfaces AgentRun review read/write failures instead of
calling legacy task review endpoints. Backend endpoint deletion still does not
pass remove-now because external compatibility confirmation remains open by
surface. B now exposes typed,
sanitized extraction and research-summary results through the compact AgentRun
read boundary, and Task Detail prefers those results. D shared Review Queue
coverage now uses AgentRun endpoints or direct shared helpers; only legacy-only
transport/scoping/fallback candidates remain on the task routes. No backend
compatibility API is deleted because no B/C/D external compatibility window is
explicitly confirmed closed. This does not claim the overall runtime refactor
is complete.

## Primary Boundaries

- AgentRun read: `GET /agent-runs/{run_id}`.
- AgentRun review read/write:
  `GET /agent-runs/{run_id}/review-items` and
  `POST /agent-runs/{run_id}/review-items/{item_id}/decision`.
- Governed preparation/start:
  `POST /workflows/{task_id}/governed/start` and
  `GET /workflows/{task_id}/governed`.
- Browser write:
  `POST /agent-runs/{run_id}/continue`, with default `fill_form` and
  `{"action":"submit_form"}` for explicit final submit.

## Phase 24 Dependency Map

| Surface | Status | Primary replacement | Current consumers | Fallback type | Removal evidence still needed |
| --- | --- | --- | --- | --- | --- |
| `POST /tasks`, `GET /tasks`, `GET /tasks/{task_id}` | keep-for-now | Future create/list/read AgentRun APIs plus existing `GET /agent-runs/{run_id}` for runtime state | Dashboard, Create Task, Page Intake, Task Detail, Review Mapping, tests, demo docs | Not just no-run-id; it is still the stable task shell for profile/url/status/log/screenshot/approval navigation | Create/list AgentRun API parity, frontend route migration, demo/script migration, task facade e2e, rollback path |
| `GET /tasks/{task_id}/review-items` | remove-later | `GET /agent-runs/{run_id}/review-items` | Legacy-only backend removal candidates and docs-only mentions; frontend product fallback/helper removed | No product fallback found | Explicitly close the external compatibility window, then add a removal test |
| `POST /tasks/{task_id}/review-items/{item_id}/decision` | remove-later | `POST /agent-runs/{run_id}/review-items/{item_id}/decision` | Legacy-only backend removal candidates and docs-only mentions; frontend product fallback/helper removed | No product fallback found | Explicitly close the external compatibility window, then add a removal test |
| `FormField` sync compatibility | keep-for-now | `AgentProposal` + `AgentReviewDecision`; browser write should eventually consume approved proposals directly | Review Queue sync helper, legacy fill/submit helpers, Review Mapping field edits, benchmarks, tests | Not only no-run-id; `FormField` remains extraction storage plus legacy mapped value storage | Proposal-only fill/submit path, extraction-vs-mapping storage split, benchmark parity, migration script or compatibility read model |
| `POST /tasks/{task_id}/extract-page` | remove-later | Governed start for execution plus compact `GET /agent-runs/{run_id}` result read | Backend compatibility tests and docs-only mentions; frontend product fallback and helper removed | Workflow-specific read compatibility facade, not browser-write | Explicitly close the external compatibility window, then add a removal test |
| `POST /tasks/{task_id}/job-summary` | remove-later | Governed start for execution plus compact `GET /agent-runs/{run_id}` result read | Backend compatibility tests and docs-only mentions; frontend product fallback and helper removed | Workflow-specific read compatibility facade, not browser-write | Explicitly close the external compatibility window, then add a removal test |
| `POST /tasks/{task_id}/fill` | remove-later | `POST /agent-runs/{run_id}/continue` | Task Detail no-run-id fallback, legacy async jobs, backend/frontend tests | Yes | All fill-capable paths must expose run id before fill; sync/async continue e2e; legacy empty-payload job retirement plan |
| `POST /tasks/{task_id}/confirm-submit` | remove-later | `POST /agent-runs/{run_id}/continue` with `{"action":"submit_form"}` | Task Detail no-run-id fallback, approval flow tests | Yes | Submit e2e through AgentRun continue, approval center/task refresh parity, stale approval regression coverage after fallback removal |
| `POST /workflows/{task_id}/start` | remove-later | `POST /workflows/{task_id}/governed/start` | Backend old-graph behavior tests; no frontend product helper or primary caller found | Old security graph external compatibility only | External compatibility window closes and old graph behavior tests convert to deletion/parity tests |
| `GET /workflows/{task_id}` | remove-later | `GET /agent-runs/{run_id}` or `GET /workflows/{task_id}/governed` | Backend old-graph behavior tests; no frontend product helper or page caller found | Old security graph external compatibility only | Backend behavior tests convert to deletion/parity tests and external compatibility window closes |
| `POST /workflows/{task_id}/review` | remove-later | AgentRun Review Queue decision endpoint | Backend old-graph behavior tests; no frontend product helper or page caller found | Old security graph external compatibility only | Backend behavior tests convert to deletion/parity tests and external compatibility window closes |
| Frontend Task Detail fallbacks | remove-later | Run Cockpit helpers using AgentRun first | `loadRunCockpitRuntime`, fill/submit action helpers | Mixed: AgentRun read failure, no-run-id task facade, no-run-id browser-write compatibility; old graph UI removed | Require run id for fill/submit-capable task detail paths before task wrapper deletion |
| Frontend Run Cockpit fallback order | keep-for-now | `getAgentRun` -> governed state -> task facade | `runCockpitActions.js`, tests | AgentRun read failure and no-run-id | Keep until task facade read removal has a replacement route |
| Frontend Review Mapping fallbacks | removed | AgentRun review read/write | `reviewMappingActions.js`; old graph UI removed from `ReviewMapping.jsx` | None for task review endpoints | Keep AgentRun failure surfacing covered; backend routes remain until deletion criteria pass |
| Frontend Create Task/Page Intake workflow-specific starts | removed | Governed start for all enabled demo workflows | `CreateTask.jsx`, `AnalyzePage.jsx`, `api.startReadOnlyWorkflow` | No legacy endpoint fallback; governed start failure surfaces to existing page error handling | Keep frontend on governed deterministic start |
| Benchmark/demo/script helpers | keep-for-now | Runtime benchmark mode for AgentRun-style evidence; demos should prefer governed path | `benchmark_runner.py`, `backend/benchmarks`, `docs/demo-script.md`, README | Not product runtime fallback | Keep direct full-workflow benchmark as local deterministic evaluator; add removal checks only for product API callers |

## Phase 25 No-Run-Id Fallback Audit

Task Detail:

1. Read task facade from `GET /tasks/{task_id}`.
2. If `agent_run_id` or `agent_runtime.run_id` exists, Run Cockpit reads
   `GET /agent-runs/{run_id}`.
3. If AgentRun read fails, it falls back to `GET /workflows/{task_id}/governed`.
4. If governed state is missing, it falls back to compact task facade state.
5. Fill/submit use `POST /agent-runs/{run_id}/continue` when a run id exists;
   otherwise they use `/tasks/{task_id}/fill` and
   `/tasks/{task_id}/confirm-submit`.

Review Mapping:

1. Read task facade to discover run id.
2. If a run id exists, read `GET /agent-runs/{run_id}/review-items`.
3. If no run id exists, or AgentRun review read fails, surface the error.
4. Review writes require a run id and use AgentRun decisions; no write falls
   back to the legacy task decision endpoint.

Create Task and Page Intake:

- Generic form fill, vendor onboarding, and security questionnaire demos start
  the governed deterministic path after task creation.
- `web_data_extract` and `job_research_summary` now call
  `api.startReadOnlyWorkflow`, which calls governed deterministic start and
  surfaces governed failures through existing page error handling.

Conclusion: browser-write still has intentional no-run-id compatibility
fallbacks, but Review Mapping no longer uses legacy task review read/write
fallbacks.

## Phase 26 Browser-Write Wrapper Retirement Planning

`/agent-runs/{run_id}/continue` is the primary browser-write boundary.

Current wrapper safety:

- AgentRun fill delegates to the shared reviewed fill helper with
  `agent_run_id`.
- AgentRun submit delegates to the shared submit helper with explicit
  `submit_form` action.
- Legacy fill and submit wrappers still pass through review, approval, stale
  value, stale selector, policy, Tool Runtime, and verification gates.
- Legacy async fill jobs with `agent_run_id` delegate back through AgentRun
  continuation and do not re-enqueue.
- Legacy async fill jobs without `agent_run_id` remain the no-run-id fallback.

No runtime/security gap found in this audit.

Deletion blockers:

- e2e proving every UI fill action has a run id after prepare.
- e2e proving every UI final-submit action has a run id and still requires
  explicit final-submit approval.
- async job parity for AgentRun continue in worker mode.
- rollback plan that can re-enable legacy wrappers if run creation regresses.

## Phase 27 Workflow-Specific Endpoint Readiness

Read-only extraction and job summary:

- Governed AgentRun start covers `web_data_extract` and `job_research_summary`
  as planned read-only tool steps.
- Legacy `/tasks/{task_id}/extract-page` and
  `/tasks/{task_id}/job-summary` remain as backend compatibility facades;
  Create Task and Page Intake no longer use them as frontend fallback paths.
- No browser-write or security gap found; these are read-only compatibility
  facades.

Security questionnaire old graph:

- Primary demo path is governed deterministic runtime through
  `/workflows/{task_id}/governed/start`.
- Review items are proposal-backed `answer` items through AgentRun Review
  Queue APIs.
- Reviewed fill and explicit final submit use shared browser-write gates.
- Old graph start/get/review remains deprecated and non-mutating for browser
  writes; it is not a verification trust path.

Deletion blockers:

- External compatibility window for old security graph clients.
- Convert old graph backend preservation tests to deletion/parity tests.
- Keep one parity/e2e path proving security questionnaire source-backed answers,
  unsupported refusal, sensitive blocking, reviewed fill, and explicit submit.
- Convert old graph tests from behavior-preservation tests to removal tests.

## Phase 28 Integrated Removal Plan

Removal order for the next track:

1. Move Create Task and Page Intake read-only workflows to governed start.
   - Candidate: `/tasks/{task_id}/extract-page`,
     `/tasks/{task_id}/job-summary`.
   - Status: frontend helper fallback removed.
   - Blockers: governed execution output is persisted, but Task Detail still
     reads the full extraction and research-summary results from legacy
     checkpoints; external consumers are not confirmed absent.
   - Required tests still needed before deletion: compact governed result-read
     coverage, Task Detail presentation coverage, and removal tests proving the
     old routes are absent.
   - Rollback: keep backend task endpoints until deletion criteria pass.

2. Remove old security questionnaire graph UI consumers.
   - Candidate: `/workflows/{task_id}/start`, `/workflows/{task_id}`,
     `/workflows/{task_id}/review`.
   - Status: frontend primary path, no-run-id old graph UI fallback, and
     frontend old graph API helpers removed.
   - Blockers: backend preservation tests, demos/scripts audit, external
     compatibility window.
   - Required tests: security questionnaire governed start/review/fill/submit
     path and old graph 404/removal tests after deletion.
   - Rollback: restore old graph routes only; no schema migration required.

3. Retire legacy task review backend routes.
   - Candidate: `/tasks/{task_id}/review-items`,
     `/tasks/{task_id}/review-items/{item_id}/decision`.
   - Status: frontend Review Mapping reads/writes AgentRun review APIs only;
     frontend task review helpers are removed.
   - Blockers: still-needed shared Review Queue behavior tests remain coupled
     to the task routes, and external consumers are not confirmed absent.
     FormField sync itself remains needed for browser-write compatibility but
     is shared by the AgentRun boundary and does not require these task routes.
   - Required tests: move shared behavior coverage to AgentRun/direct-helper
     tests, then add deletion/removal checks for the legacy routes.
   - Rollback: keep backend route implementation until deletion criteria pass.

4. Require run id for browser fill/submit.
   - Candidate: `/tasks/{task_id}/fill`,
     `/tasks/{task_id}/confirm-submit`.
   - Blockers: no-run-id task flows and legacy empty-payload fill jobs.
   - Required tests: sync and async AgentRun continue fill, explicit submit
     approval through continue, stale value/selector regressions.
   - Rollback: keep shared task helper while only route wrappers change.

5. Split `FormField` extraction storage from review/mapping decisions.
   - Candidate: FormField mapped-value sync.
   - Blockers: legacy fill reads mapped values from `FormField`, benchmarks
     create `FormField` objects directly, Review Mapping still supports direct
     field edit fallback.
   - Required tests: proposal-only fill/submit, benchmark parity, field
     extraction read model, migration/backfill.
   - Rollback: retain sync helper until browser write no longer reads mapped
     values from `FormField`.

6. Replace task facade routes.
   - Candidate: `POST /tasks`, `GET /tasks`, `GET /tasks/{task_id}`.
   - Blockers: app route model, dashboard/task detail navigation, profile/task
     shell semantics, logs/screenshots/approvals still keyed by task.
   - Required tests: create/list/read AgentRun parity, UI navigation parity,
     demo script parity.
   - Rollback: keep task facade adapter over AgentRun until old routes can be
     deleted safely.

## Phase 29-32 Read-Only Frontend Prep

Current consumers:

- `CreateTask.jsx` and `AnalyzePage.jsx` call `api.startReadOnlyWorkflow` for
  `web_data_extract` and `job_research_summary`.
- `api.startReadOnlyWorkflow` calls
  `/workflows/{task_id}/governed/start?planner_mode=deterministic`.
- Legacy `/tasks/{task_id}/extract-page` and `/tasks/{task_id}/job-summary`
  remain in backend compatibility tests and docs-only mentions.

Evidence:

- Frontend: `read-only workflow start uses governed deterministic path first`
  and `read-only workflow start surfaces governed failure without legacy
  fallback`.
- Backend: `test_governed_start_web_data_extract_runs_read_only_page_plan` and
  `test_governed_start_job_summary_runs_read_only_summary_plan`.

Removal readiness:

- Frontend primary path removed: yes.
- Frontend legacy fallback removed: yes.
- Delete now: no.
- Governed execution evidence: AgentRun/plan/tool-call, trace-span, computed
  summary, and screenshot runtime evidence are covered by backend tests.
- Next deletion blockers: the compact primary API does not expose the full
  extraction or research-summary result that Task Detail still reads from
  legacy checkpoints; external consumers are also not confirmed absent.

## Workflow Compatibility Endpoint Removal Gate

Audit commands:

- `rg -n "startWorkflow|getWorkflowState|reviewWorkflow|/workflows/\$\{|/workflows/.*/(start|review)|workflows/.*start|workflows/.*review|workflows/\{task_id\}" frontend/src backend/app/routers backend/tests README.md docs scripts backend/benchmarks`
- `rg -n "extract-page|job-summary|startReadOnlyWorkflow|runReadOnlyWorkflow|web_data_extract|job_research_summary" frontend/src backend/app/routers backend/tests README.md docs scripts backend/benchmarks`
- `rg -n "workflows.*start|workflows.*review|extract-page|job-summary" backend/app/routers -S`

Old security graph endpoint consumers:

| Endpoint group | Product caller | Compatibility helper/fallback | Backend preservation test | Docs-only mention | Benchmark/demo helper | External compatibility blocker |
| --- | --- | --- | --- | --- | --- | --- |
| `POST /workflows/{task_id}/start`, `GET /workflows/{task_id}`, `POST /workflows/{task_id}/review` | None found in `frontend/src` or product routers beyond the route implementation. | Backend route remains in `backend/app/routers/workflows.py` as deprecated old graph fallback; frontend old graph helpers are absent. | `backend/tests/test_workflow_runtime_endpoint.py` still preserves old start/get/review behavior; `backend/tests/test_section_21_validation_audit.py` still documents the fallback surface. | README, architecture, roadmap, RFC, Section 21 audit, and this map describe the endpoints as deprecated compatibility. | No direct caller found in `scripts` or `backend/benchmarks`. | Yes. The external compatibility window is still open. |

Read-only workflow compatibility endpoint consumers:

| Endpoint group | Product caller | Compatibility helper/fallback | Backend preservation test | Docs-only mention | Benchmark/demo helper | External compatibility blocker |
| --- | --- | --- | --- | --- | --- | --- |
| `POST /tasks/{task_id}/extract-page`, `POST /tasks/{task_id}/job-summary` | `CreateTask.jsx` and `AnalyzePage.jsx` call `api.startReadOnlyWorkflow`, which now calls governed start only. | None in product frontend fallback paths; low-level frontend helpers are removed. | `backend/tests/test_task_mapping_endpoint.py` still verifies legacy endpoint runtime persistence; `backend/tests/test_section_21_validation_audit.py` still documents them as read-only compatibility facades. | README, roadmap, RFC, Section 21 audit, and this map describe these as read-only compatibility facades. | No direct caller found in `scripts` or `backend/benchmarks`; docs/demo references are narrative only. | Treat as not closed until no external consumers are confirmed and removal tests replace preservation tests. |

Remove-now decision:

| Endpoint group | Decision | Why not delete in this gate |
| --- | --- | --- |
| Old security graph backend endpoints | remove-later | No product caller or frontend helper remains, but backend preservation tests and the external compatibility window still exist. |
| Read-only workflow compatibility endpoints | remove-later | The frontend compatibility fallback helper is removed, but backend preservation test conversion, external-consumer confirmation, and removal tests are still missing. |

Endpoint deletion was not executed because neither group meets remove-now
criteria. This gate updates the compatibility map only.

## Old Security Graph Frontend Prep

Current consumers:

- `frontend/src/api.js` no longer exposes `startWorkflow`,
  `getWorkflowState`, or `reviewWorkflow` product helpers for the old graph
  endpoints.
- `frontend/src/api.test.js` now asserts those product helpers do not exist.
- `frontend/src/pages/TaskDetail.jsx` no longer reads old graph state or renders
  the old graph fallback panel.
- `frontend/src/pages/ReviewMapping.jsx` no longer reads old graph state or
  submits old graph review state.
- `frontend/src/runCockpitActions.js` already uses
  `GET /agent-runs/{run_id}` and `POST /agent-runs/{run_id}/continue` when a
  run id exists, with governed/task facade fallback only for reads or no-run-id
  browser-write compatibility.
- `frontend/src/reviewMappingActions.js` uses AgentRun review read/write only.
  Missing run ids and AgentRun review failures now surface to the page error
  state instead of falling back to task review endpoints.
- Related frontend tests now cover AgentRun-first Run Cockpit reads, AgentRun
  continue fill/submit, AgentRun-first Review Mapping read/write, no AgentRun
  write fallback after AgentRun errors, and old security graph UI fallback
  removal.

Primary replacements:

- `POST /workflows/{task_id}/governed/start?planner_mode=deterministic`
- `GET /agent-runs/{run_id}`
- `GET /agent-runs/{run_id}/review-items`
- `POST /agent-runs/{run_id}/review-items/{item_id}/decision`
- `POST /agent-runs/{run_id}/continue`

Evidence:

- `frontend/src/runCockpitPresentation.test.js::shouldShowLegacyWorkflowRuntimePanel hides legacy panel when Run Cockpit has runtime state`
- `frontend/src/reviewMappingActions.test.js::review mapping never loads old security graph fallback`
- Existing frontend evidence for AgentRun-first Run Cockpit, Review Mapping,
  and AgentRun continue boundaries.
- Existing backend evidence:
  `test_governed_start_security_questionnaire_uses_source_answer_proposals`,
  `test_old_security_graph_start_stays_out_of_agent_run_primary_path`, and
  `test_old_security_graph_review_fallback_stays_non_mutating_and_compact`.

Removal readiness:

- Frontend primary path removed: yes.
- Frontend old graph API helpers removed: yes.
- Delete now: no.
- Next deletion blockers: public compatibility window, backend preservation
  test conversion, and final confirmation that demos/scripts have no old graph
  dependency.

## Old Security Graph Endpoint Gate

Audit commands:

- `rg -n "startWorkflow|getWorkflowState|reviewWorkflow" frontend/src backend/app backend/tests README.md docs scripts backend/benchmarks`
- `rg -n "workflows/.*start|workflows/.*review|workflows/.*governed|agent-runs/.*/continue|agent_run_id|agent_runtime" README.md docs scripts backend/benchmarks frontend/src/pages backend/tests`

Consumer classification:

- Product primary consumer: none found for
  `POST /workflows/{task_id}/start`, `GET /workflows/{task_id}`, or
  `POST /workflows/{task_id}/review`.
- Product UI old graph fallback: none found. `frontend/src/pages/TaskDetail.jsx`
  no longer calls `api.getWorkflowState`, and
  `frontend/src/pages/ReviewMapping.jsx` no longer calls `api.getWorkflowState`
  or `api.reviewWorkflow`.
- Frontend API removal-readiness tests: `frontend/src/api.test.js` asserts
  `api.startWorkflow`, `api.getWorkflowState`, and `api.reviewWorkflow` are not
  exposed as product helpers.
- Backend compatibility behavior tests:
  `backend/tests/test_workflow_runtime_endpoint.py` still verifies old start,
  get, review, non-security rejection, and missing-runtime behavior.
- Backend endpoint implementation:
  `backend/app/routers/workflows.py` still exposes the deprecated old graph
  routes and documents governed/AgentRun APIs as the product path.
- Docs-only mentions: README, architecture, roadmap, RFC, Section 21 audit, and
  this map describe the old endpoints as deprecated compatibility fallback.
- Demo scripts and benchmark helpers: no product/demo script caller of the old
  graph endpoints was found in this audit; benchmark references are runtime
  helper imports or docs, not direct old endpoint dependencies.

No-run-id gap closure:

- Create Task starts `security_questionnaire`, `vendor_onboarding`, and
  `form_fill` through `api.startGovernedWorkflow(..., plannerMode:
  "deterministic")` immediately after task creation.
- Page Intake persists the intake task and then starts the same governed
  deterministic path for `security_questionnaire`.
- Task Detail prepare uses `startRunCockpitRuntime`, which calls governed
  deterministic start, not old graph start.
- With a run id, Task Detail reads `GET /agent-runs/{run_id}` first and
  fill/submit use `POST /agent-runs/{run_id}/continue`.
- With a run id, Review Mapping reads/writes AgentRun review items and does not
  fall back to task review writes after AgentRun write errors.
- No real product-created security questionnaire run-id gap was found. The old
  graph UI fallback for no-run-id tasks is removed; remaining old graph callers
  are backend preservation tests or legacy/manual old clients.

Frontend old graph helper removal:

- `api.startWorkflow`, `api.getWorkflowState`, and `api.reviewWorkflow` were
  removed from `frontend/src/api.js`.
- Task Detail does not call old start/read and its prepare button calls
  governed start.
- Review Mapping does not read/write the old graph.
- Existing focused tests cover the UI fallback removal:
  `review mapping never loads old security graph fallback` and
  `shouldShowLegacyWorkflowRuntimePanel hides legacy panel when Run Cockpit has
  runtime state`.

Remove-now decision:

| Endpoint | Frontend primary path removed | Decision | Minimal remaining blocker |
| --- | --- | --- | --- |
| `POST /workflows/{task_id}/start` | yes | remove-later | Backend behavior tests and external compatibility window remain. |
| `GET /workflows/{task_id}` | yes | remove-later | Backend behavior tests and external compatibility window remain. |
| `POST /workflows/{task_id}/review` | yes | remove-later | Backend behavior tests and external compatibility window remain. |

Endpoint deletion was not executed because the map decision is not remove-now.
This gate removes the frontend old graph UI fallback and product API helpers,
documents the remaining blockers, and keeps compatibility endpoints intact.

## Compatibility Backend Removal Closure Gate

Audit commands:

- `rg -n "extract-page|job-summary" frontend/src backend/app/routers backend/tests scripts backend/benchmarks README.md docs`
- `rg -n "workflows/.*/start|workflows/\{task_id\}/start|/workflows/\$\{[^}]+\}/start|workflows/.*/review|workflows/\{task_id\}/review|/workflows/\$\{[^}]+\}/review|getWorkflowRuntime|startWorkflowRuntime|reviewWorkflowRuntime" frontend/src backend/app/routers backend/tests scripts backend/benchmarks README.md docs`
- `rg -n "tasks/.*/review-items|tasks/\{task_id\}/review-items|/tasks/\$\{[^}]+\}/review-items|listTaskReviewItems|reviewTaskItem" frontend/src backend/app/routers backend/tests scripts backend/benchmarks README.md docs`

Consumer classification:

| Surface | Product caller | Compatibility helper/fallback | Backend preservation test | Docs-only mention | Benchmark/demo helper | External compatibility blocker |
| --- | --- | --- | --- | --- | --- | --- |
| B. `POST /tasks/{task_id}/extract-page`, `POST /tasks/{task_id}/job-summary` | `CreateTask.jsx` and `AnalyzePage.jsx` call governed deterministic start only. Task Detail reads typed `workflow_result` data from the AgentRun compact boundary. No product caller hits the legacy endpoints. | None in frontend product paths; unused legacy helpers remain absent from `frontend/src/api.js`. | Two endpoint-specific tests preserve legacy route behavior; governed and AgentRun tests cover execution plus sanitized result reads. | README, architecture/roadmap/RFC audit docs, Section 21 audit, and this map. | None found in `scripts` or `backend/benchmarks`. | Not confirmed closed. Repository absence proves only that no internal consumer was found. |
| C. `POST /workflows/{task_id}/start`, `GET /workflows/{task_id}`, `POST /workflows/{task_id}/review` | None found in `frontend/src`, scripts, benchmarks, or product routers beyond the route implementation. | Backend route remains in `backend/app/routers/workflows.py` as deprecated old graph compatibility fallback. Frontend old graph product helpers remain absent. | `backend/tests/test_workflow_runtime_endpoint.py` preserves old start/get/review behavior; `backend/tests/test_section_21_validation_audit.py` documents the fallback. | README, architecture/roadmap/RFC audit docs, Section 21 audit, and this map. | None found in `scripts` or `backend/benchmarks`. | Yes, external compatibility window remains open. |
| D. `GET /tasks/{task_id}/review-items`, `POST /tasks/{task_id}/review-items/{item_id}/decision` | Review Mapping requires a run id and uses AgentRun review APIs only; AgentRun failures surface instead of falling back. | None in frontend product paths; legacy helpers remain absent from `frontend/src/api.js`. | Shared behavior coverage now uses AgentRun endpoints/direct helpers. Remaining task-route tests cover canonical scoping, arbitrary-run rejection, synthetic ids, no-prior-proposal compatibility, or transport. | README, roadmap/RFC audit docs, Section 21 audit, and this map. | None found in `scripts` or `backend/benchmarks`. | Not confirmed closed. Repository absence proves only that no internal consumer was found. |

Primary replacement parity:

- B has execution and product read parity for `extract_page`,
  `capture_screenshot`, and `generate_job_summary`. The governed path persists
  AgentRun/tool evidence, `GET /agent-runs/{run_id}` exposes only the typed
  `workflow_result.extraction` and `workflow_result.research_summary`
  whitelists, and Task Detail prefers those complete results. Legacy
  checkpoints remain presentation compatibility for historical data only.
- C has governed security-questionnaire parity for source-backed answer
  proposals, sensitive blocking, unsupported-answer refusal, AgentRun Review
  Queue decisions, reviewed fill, explicit final submit, and generic
  verification. The old graph remains non-mutating and is not a verification
  trust path.
- D has AgentRun parity for compact reads, requested-run scoping, all four
  decision values, wrong-run rejection, pending-count updates, field sync, and
  non-field runtime-only decisions. Review Mapping has no legacy task review
  fallback.

Backend preservation test classification:

| Surface | Still-needed behavior preservation | Future deletion test candidate | Parity evidence already covered |
| --- | --- | --- | --- |
| B | Page extraction, deterministic summary generation, screenshot capture, Tool Runtime governance, persistence, trace behavior, and typed sanitized AgentRun result reads remain product behavior. | `test_extract_page_persists_runtime_call_without_raw_task_facade_output` and `test_job_summary_page_extraction_persists_runtime_call` are tied to the legacy task routes and become removal checks only after external-window closure. | Governed start parity tests plus `test_get_agent_run_returns_sanitized_page_extraction_result` and `test_get_agent_run_returns_sanitized_research_summary_result`. |
| C | Governed security questionnaire proposal, policy, review, browser-write, submit-approval, and verification tests remain required. | Old-route tests for start interrupt, compact GET state, review resume, missing state/task, unsupported workflow, old-path redaction, compatibility-only persistence, and non-mutating review should be replaced by removal checks when the external window closes. | `test_governed_start_security_questionnaire_uses_source_answer_proposals`, `test_governed_start_security_questionnaire_marks_sensitive_fields_blocked`, `test_governed_start_security_questionnaire_marks_unsupported_no_evidence_answer`, plus AgentRun continue/review/verification coverage. |
| D | Proposal/evidence persistence and backfill, compact sanitization, decision persistence, pending counts, FormField sync for `field_value` / `answer` / `open_ended_answer` only, and non-field/unknown/external-write handling now run through AgentRun endpoints or direct shared helpers. | Legacy canonical-run scoping, arbitrary same-task run rejection, synthetic legacy field-id fallback, no-prior-proposal flow, and task-route transport assertions remain deletion/removal candidates. | AgentRun review tests plus the migrated primary-path cases in `test_task_mapping_endpoint.py`. |

FormField sync remains intentionally limited by
`FORM_FIELD_SYNC_PROPOSAL_TYPES` to `field_value`, `answer`, and
`open_ended_answer`. `memory_write`, `form_submit`, browser actions, external
writes, and unknown proposal types remain runtime-only.

Remove-now decision:

| Surface | Status | Delete this gate? | Minimal blocker |
| --- | --- | --- | --- |
| B. Read-only backend endpoints | remove-later | No | Product read parity is closed, but the external compatibility window is not explicitly confirmed closed. |
| C. Old security graph backend endpoints | remove-later | No | External compatibility window is still open and backend preservation tests still assert old graph behavior. |
| D. Legacy task review endpoints | remove-later | No | Shared behavior tests are decoupled, but the external compatibility window is not explicitly confirmed closed. |

Runtime/security gaps:

- No new browser-write safety gap found. B is read-only, C remains
  non-mutating/skeleton-only for browser writes, and D is review persistence
  compatibility rather than a browser execution path.
- Existing gates still hold: reviewed fill and final submit use shared
  AgentRun/Tool Runtime gates when a run id exists; final submit still requires
  explicit approval; old graph fallback is not verification trust evidence.

Remaining gaps:

- B needs an explicit external compatibility-window closure before a failing
  route-removal test may be added.
- C needs the external compatibility window closed before old graph removal
  tests replace preservation tests.
- D needs an explicit external compatibility-window closure before its
  legacy-only candidates may be converted to route-removal tests. FormField
  sync remains intentionally limited to field proposals for browser-write
  compatibility.

Closure outcome: B product parity and D test decoupling are complete. B, C,
and D independently remain remove-later because this repository contains no
explicit evidence that any external compatibility window has closed. No
removal test was added and no backend route was deleted merely to show
progress. FormField sync remains unchanged.

## Runtime And Security Gaps

Found in this audit:

- Fixed: governed B execution now exposes a typed, sanitized compact result
  through AgentRun, and Task Detail renders full extraction text plus the
  research summary from that primary result before checkpoint history.
- Fixed: Task Detail could still expose the old security graph read/panel path
  when generic Run Cockpit state was unavailable. That old graph UI fallback is
  now removed.
- Fixed: Review Mapping could still read and submit old security graph state
  for no-run-id security questionnaire tasks. That old graph UI fallback is now
  removed.
- Fixed: `frontend/src/api.js` still exposed product helpers for the old graph
  endpoints. Those helpers are now removed, and the API client test asserts
  they stay absent.
- Fixed: Review Mapping still had a legacy task review read/write fallback.
  Missing run ids and AgentRun review failures now surface errors, and
  `frontend/src/api.js` no longer exposes `listTaskReviewItems` or
  `reviewTaskItem`.
- No browser-write safety bypass was found; reviewed fill and final submit
  still use the shared AgentRun/Tool Runtime gates when a run id exists.

Already covered by existing evidence:

- Compact facades avoid exposing raw `tool_results` and `output_json`.
- Review writes are scoped to the requested AgentRun or canonical
  compatibility run.
- Non-field proposals do not sync `FormField`.
- Browser writes require reviewed mapping, policy gates, stale checks, Tool
  Runtime execution, and verification evidence.
- Final submit still requires explicit approval.
- Old security graph fallback does not execute dangerous browser writes and is
  not trusted for verification.

## Surface Buckets

remove-now:

- None. B product parity and D shared-test separation are closed, but no B/C/D
  external compatibility window is explicitly confirmed closed.

removed:

- Frontend read-only compatibility fallback branch.
- Frontend Review Mapping legacy task review fallback/helper.

remove-later:

- `/tasks/{task_id}/extract-page`
- `/tasks/{task_id}/job-summary`
- `/tasks/{task_id}/fill`
- `/tasks/{task_id}/confirm-submit`
- `/workflows/{task_id}/start`
- `/workflows/{task_id}`
- `/workflows/{task_id}/review`
- `/tasks/{task_id}/review-items`
- `/tasks/{task_id}/review-items/{item_id}/decision`

keep-for-now:

- `POST /tasks`, `GET /tasks`, `GET /tasks/{task_id}`.
- `FormField` extraction rows and field-proposal sync.
- Run Cockpit task facade fallback.
- Benchmark full-workflow/direct fixture helpers.

## Close Criteria

This endpoint gate can close when:

- This map is committed.
- Backend tests pass.
- Frontend tests pass.
- Frontend production build passes.

No smaller follow-up compatibility phase is created. Future backend deletion
starts only after the target surface receives explicit external-window closure;
that work begins with a failing removal test for that surface.
