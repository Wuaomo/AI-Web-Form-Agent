# Compatibility Removal Map

Compatibility Removal Planning & Primary Path Consolidation Track

Status: Phase 29-32 read-only frontend primary-path prep complete. No
compatibility API is deleted here, and this does not claim the overall runtime
refactor is complete.

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
| `POST /workflows/{task_id}/start` | remove-later | `POST /workflows/{task_id}/governed/start` | Task Detail legacy security panel, backend tests | Old security graph fallback | Remove Task Detail old panel/start path, external compatibility window closes, old graph tests converted to deletion/parity tests |
| `GET /workflows/{task_id}` | remove-later | `GET /agent-runs/{run_id}` or `GET /workflows/{task_id}/governed` | Task Detail legacy runtime probe, Review Mapping old approvals, backend tests | Old security graph fallback | Remove old graph UI reads, prove security questionnaire Review Queue covers same user decisions |
| `POST /workflows/{task_id}/review` | remove-later | AgentRun Review Queue decision endpoint | Review Mapping legacy submitReview path, backend tests | Old security graph fallback | Remove legacy review submit UI, prove approved security answers fill only through AgentRun continue |
| Frontend Task Detail fallbacks | remove-later | Run Cockpit helpers using AgentRun first | `loadRunCockpitRuntime`, old workflow panel, fill/submit action helpers | Mixed: AgentRun read failure, no-run-id, old graph | Contract test with run-id-required fill/submit, remove old graph panel after security demo parity |
| Frontend Run Cockpit fallback order | keep-for-now | `getAgentRun` -> governed state -> task facade | `runCockpitActions.js`, tests | AgentRun read failure and no-run-id | Keep until task facade read removal has a replacement route |
| Frontend Review Mapping fallbacks | remove-later | AgentRun review read/write | `reviewMappingActions.js`, `ReviewMapping.jsx` old graph state/review submit | Review read fallback and old graph fallback | Remove task review fallback after all review pages have run id; remove old graph review UI |
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
   - Blockers: Task Detail legacy panel and Review Mapping old submit flow.
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

## Runtime And Security Gaps

Found in this audit: none.

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

- None. Read-only frontend primary routing has moved, but compatibility
  fallback, backend compatibility tests, and external/demo parity blockers still
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
- Frontend old graph/no-run-id fallback branches
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
