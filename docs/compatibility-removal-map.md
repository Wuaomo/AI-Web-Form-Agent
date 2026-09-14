# Compatibility Removal Map

Compatibility Removal Planning & Primary Path Consolidation Track

Status: Old security graph UI fallback and frontend product API helpers are
removed, but the endpoint gate still does not pass remove-now. Backend
preservation tests and the external compatibility window remain, so endpoint
deletion was not run. No backend compatibility API is deleted here, and this
does not claim the overall runtime refactor is complete.

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
| `GET /tasks/{task_id}/review-items` | remove-later | `GET /agent-runs/{run_id}/review-items` | Review Mapping fallback, backend/frontend tests | Yes: no run id or AgentRun read failure | Guarantee review pages always have a run id, remove frontend fallback, legacy task review e2e kept until migration window closes |
| `POST /tasks/{task_id}/review-items/{item_id}/decision` | remove-later | `POST /agent-runs/{run_id}/review-items/{item_id}/decision` | Review Mapping only when no run id, backend/frontend tests | Yes | No-run-id review write migration, decision parity for field approvals/edits/rejections, stale proposal regression tests |
| `FormField` sync compatibility | keep-for-now | `AgentProposal` + `AgentReviewDecision`; browser write should eventually consume approved proposals directly | Review Queue sync helper, legacy fill/submit helpers, Review Mapping field edits, benchmarks, tests | Not only no-run-id; `FormField` remains extraction storage plus legacy mapped value storage | Proposal-only fill/submit path, extraction-vs-mapping storage split, benchmark parity, migration script or compatibility read model |
| `POST /tasks/{task_id}/extract-page` | remove-later | `POST /workflows/{task_id}/governed/start` for `web_data_extract` AgentRun plan | Frontend compatibility fallback helper, backend compatibility tests | Workflow-specific read fallback, not browser-write | Checkpoint/log/screenshot parity e2e, demo/script update, no external consumers |
| `POST /tasks/{task_id}/job-summary` | remove-later | `POST /workflows/{task_id}/governed/start` for `job_research_summary` AgentRun plan | Frontend compatibility fallback helper, backend compatibility tests | Workflow-specific read fallback, not browser-write | Summary/checkpoint/log/screenshot parity e2e, benchmark/docs update, no external consumers |
| `POST /tasks/{task_id}/fill` | remove-later | `POST /agent-runs/{run_id}/continue` | Task Detail no-run-id fallback, legacy async jobs, backend/frontend tests | Yes | All fill-capable paths must expose run id before fill; sync/async continue e2e; legacy empty-payload job retirement plan |
| `POST /tasks/{task_id}/confirm-submit` | remove-later | `POST /agent-runs/{run_id}/continue` with `{"action":"submit_form"}` | Task Detail no-run-id fallback, approval flow tests | Yes | Submit e2e through AgentRun continue, approval center/task refresh parity, stale approval regression coverage after fallback removal |
| `POST /workflows/{task_id}/start` | remove-later | `POST /workflows/{task_id}/governed/start` | Backend old-graph behavior tests; no frontend product helper or primary caller found | Old security graph external compatibility only | External compatibility window closes and old graph behavior tests convert to deletion/parity tests |
| `GET /workflows/{task_id}` | remove-later | `GET /agent-runs/{run_id}` or `GET /workflows/{task_id}/governed` | Backend old-graph behavior tests; no frontend product helper or page caller found | Old security graph external compatibility only | Backend behavior tests convert to deletion/parity tests and external compatibility window closes |
| `POST /workflows/{task_id}/review` | remove-later | AgentRun Review Queue decision endpoint | Backend old-graph behavior tests; no frontend product helper or page caller found | Old security graph external compatibility only | Backend behavior tests convert to deletion/parity tests and external compatibility window closes |
| Frontend Task Detail fallbacks | remove-later | Run Cockpit helpers using AgentRun first | `loadRunCockpitRuntime`, fill/submit action helpers | Mixed: AgentRun read failure, no-run-id task facade, no-run-id browser-write compatibility; old graph UI removed | Require run id for fill/submit-capable task detail paths before task wrapper deletion |
| Frontend Run Cockpit fallback order | keep-for-now | `getAgentRun` -> governed state -> task facade | `runCockpitActions.js`, tests | AgentRun read failure and no-run-id | Keep until task facade read removal has a replacement route |
| Frontend Review Mapping fallbacks | remove-later | AgentRun review read/write | `reviewMappingActions.js` task review fallback; old graph UI removed from `ReviewMapping.jsx` | Review read fallback only | Remove task review fallback after all review pages have run id |
| Frontend Create Task/Page Intake workflow-specific starts | remove-later | Governed start for all enabled demo workflows | `CreateTask.jsx`, `AnalyzePage.jsx`, `api.startReadOnlyWorkflow` | Legacy read endpoint fallback when governed start fails | Remove fallback after read-only e2e/demo parity and compatibility window |
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
3. If AgentRun review read fails, read `GET /tasks/{task_id}/review-items`.
4. Review writes use AgentRun decision when a run id exists and do not fall
   back to the legacy task decision endpoint after AgentRun write failure.
5. Without a run id, review writes use the legacy task decision endpoint.

Create Task and Page Intake:

- Generic form fill, vendor onboarding, and security questionnaire demos start
  the governed deterministic path after task creation.
- `web_data_extract` and `job_research_summary` now call
  `api.startReadOnlyWorkflow`, which tries governed deterministic start first
  and only calls workflow-specific task endpoints as compatibility fallback.

Conclusion: with a run id, browser-write and review writes already use AgentRun
primary boundaries. Without a run id, fallbacks remain intentional compatibility
paths, not security bypasses.

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
  `/tasks/{task_id}/job-summary` remain as compatibility fallbacks; Create Task
  and Page Intake no longer use them as the primary frontend start path.
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

- Remove old security graph consumers from Task Detail and Review Mapping.
- Keep one parity/e2e path proving security questionnaire source-backed answers,
  unsupported refusal, sensitive blocking, reviewed fill, and explicit submit.
- Convert old graph tests from behavior-preservation tests to removal tests.

## Phase 28 Integrated Removal Plan

Removal order for the next track:

1. Move Create Task and Page Intake read-only workflows to governed start.
   - Candidate: `/tasks/{task_id}/extract-page`,
     `/tasks/{task_id}/job-summary`.
   - Status: frontend helper migration complete.
   - Blockers: checkpoint/log/screenshot parity e2e, demo/script migration,
     external compatibility window.
   - Required tests still needed before deletion: one e2e-style read-only task
     flow per workflow and removal tests proving no product caller remains.
   - Rollback: keep task endpoints behind API helpers until parity passes.

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

3. Require run id for Review Mapping review read/write.
   - Candidate: `/tasks/{task_id}/review-items`,
     `/tasks/{task_id}/review-items/{item_id}/decision`.
   - Blockers: legacy tasks without AgentRun and FormField-only review rows.
   - Required tests: Review Mapping AgentRun read/write only, migrated old
     task review data, decision parity.
   - Rollback: keep helper fallback branch until migrated data is proven.

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
  `/workflows/{task_id}/governed/start?planner_mode=deterministic` first.
- Legacy `/tasks/{task_id}/extract-page` and `/tasks/{task_id}/job-summary`
  remain in `api.js` only as compatibility fallback helpers and in backend
  compatibility tests.

Evidence:

- Frontend: `read-only workflow start uses governed deterministic path first`
  and `read-only workflow start keeps legacy endpoint as governed fallback`.
- Backend: `test_governed_start_web_data_extract_runs_read_only_page_plan` and
  `test_governed_start_job_summary_runs_read_only_summary_plan`.

Removal readiness:

- Frontend primary path removed: yes.
- Delete now: no.
- Next deletion blockers: read-only e2e/demo parity, checkpoint/log/screenshot
  parity for extraction, summary/checkpoint parity for job summary, and external
  compatibility window.

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
- `frontend/src/reviewMappingActions.js` already uses
  AgentRun review read/write when a run id exists. Its task review fallback
  remains for no-run-id or AgentRun read failure compatibility, and AgentRun
  review write failures do not fall back to task writes.
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

## Runtime And Security Gaps

Found in this audit:

- Fixed: Task Detail could still expose the old security graph read/panel path
  when generic Run Cockpit state was unavailable. That old graph UI fallback is
  now removed.
- Fixed: Review Mapping could still read and submit old security graph state
  for no-run-id security questionnaire tasks. That old graph UI fallback is now
  removed.
- Fixed: `frontend/src/api.js` still exposed product helpers for the old graph
  endpoints. Those helpers are now removed, and the API client test asserts
  they stay absent.
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

- None. Old security graph frontend primary routing and no-run-id UI fallback
  have moved off the old graph and frontend product API helpers are removed,
  but backend compatibility tests and the external compatibility window still
  exist.

remove-later:

- `/tasks/{task_id}/review-items`
- `/tasks/{task_id}/review-items/{item_id}/decision`
- `/tasks/{task_id}/extract-page`
- `/tasks/{task_id}/job-summary`
- `/tasks/{task_id}/fill`
- `/tasks/{task_id}/confirm-submit`
- `/workflows/{task_id}/start`
- `/workflows/{task_id}`
- `/workflows/{task_id}/review`
- Frontend read-only compatibility fallback branch

keep-for-now:

- `POST /tasks`, `GET /tasks`, `GET /tasks/{task_id}`.
- `FormField` extraction rows and field-proposal sync.
- Run Cockpit task facade fallback.
- Benchmark full-workflow/direct fixture helpers.

## Close Criteria

This planning track can close when:

- This map is committed.
- Backend tests pass.
- Frontend tests pass.
- Frontend production build passes.

The next track should delete only after its target surface has no frontend
consumer, no benchmark/demo dependency, and parity tests cover the replacement.
