# Task Detail Timeline and LLM Usage Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the task detail workflow timeline and LLM usage panel accurately reflect backend state, failure location, and newly generated usage data.

**Architecture:** Keep task state rendering deterministic in frontend helper modules, and make backend/frontend contracts explicit where task status alone is insufficient. Prefer deriving failure location from existing task logs instead of inventing a broad status model change, then keep UI refreshes scoped to task detail data that can change after actions.

**Tech Stack:** FastAPI/Pydantic/SQLAlchemy backend, React 19/Vite frontend, Node test runner for frontend tests, pytest for backend endpoint tests.

## Global Constraints

- Do not revert existing user changes in the worktree.
- Use existing frontend helper patterns in `frontend/src/taskRunState.js` and `frontend/src/agentTimeline.js`.
- Avoid adding dependencies.
- Keep API additions backward-compatible where possible.
- Test every behavior change with focused frontend or backend tests.

---

## File Structure

- `backend/app/schemas.py`
  - Extend `TaskResponse` with an optional `failed_step` string if backend-derived failure location is chosen.
- `backend/app/routers/tasks.py`
  - Option A: populate `TaskResponse.failed_step` from latest failed task log when returning task data.
  - Option B: leave API unchanged and rely on frontend `listTaskLogs` for failure location.
- `frontend/src/api.js`
  - No required endpoint changes. Existing `listTaskLogs` and `getTaskLlmUsage` are enough.
- `frontend/src/agentTimeline.js`
  - Replace incorrect status-only failure inference with explicit inputs.
  - Make `MAPPING_READY` distinguish "extracted, needs mapping/review" from "mapping succeeded".
- `frontend/src/agentTimeline.test.js`
  - Add precise tests for `MAPPING_READY`, failed analyze, failed fill, failed submit, and unknown failed cases.
- `frontend/src/pages/TaskDetail.jsx`
  - Load logs and LLM usage through refreshable helper functions.
  - Refresh LLM usage after mapping, fill, and submit actions.
  - Compute workflow nodes once per render.
- `frontend/src/styles.css` or the existing main CSS file
  - Add styles for `workflow-timeline`, `timeline`, `timeline-item`, `timeline-node`, `timeline-connector`, `timeline-indicator`, and `timeline-help`.
- `frontend/src/pages/TaskDetail.test.jsx` only if the project already has React component tests
  - Otherwise keep logic tests in helper modules and manually verify UI with Vite.

## Recommended Design Decisions

1. Prefer frontend log-derived failure mapping over adding `failed_step` to `TaskResponse`.
   - Reason: backend already records `action` on failed logs: `analyze_form`, `fill_form`, `submit_form`.
   - Smaller blast radius: one existing endpoint (`/tasks/{task_id}/logs`) is enough.
   - Avoids adding a derived field to every task response unless the backend needs it elsewhere.

2. Change `getWorkflowTimeline(task)` to `getWorkflowTimeline(task, logs = [])`.
   - Existing callers still work because `logs` defaults to `[]`.
   - Task detail can pass `taskLogs`.

3. Treat `MAPPING_READY` as "extracted fields are ready for review/mapping", not guaranteed LLM mapping success.
   - Suggested timeline states:
     - `created`: success
     - `analyze`: success
     - `map`: active
     - `review`: pending
   - If fields already have mapped values, optionally show:
     - `map`: success
     - `review`: active
   - This optional behavior must be tested if implemented.

4. Refresh mutable task detail datasets together after actions.
   - `refreshTaskHistory` should become `refreshTaskData`.
   - It should refresh task, screenshots, logs, and LLM usage.
   - This prevents stale LLM usage after mapping and stale failure timeline after action failures.

---

### Task 1: Fix Workflow Timeline Semantics

**Files:**
- Modify: `frontend/src/agentTimeline.js`
- Modify: `frontend/src/agentTimeline.test.js`

**Interfaces:**
- Consumes: `task.status`, `task.form_fields`, optional `logs`.
- Produces: `getWorkflowTimeline(task, logs = []) -> Array<{ id, label, state, helpText }>`

- [ ] **Step 1: Write failing tests for `MAPPING_READY` semantics**

Add this to `frontend/src/agentTimeline.test.js`:

```js
test("getWorkflowTimeline for MAPPING_READY does not claim mapping is complete by status alone", () => {
  const nodes = getWorkflowTimeline({ status: "MAPPING_READY", form_fields: [] });

  assert.equal(nodes.find((n) => n.id === "created").state, "success");
  assert.equal(nodes.find((n) => n.id === "analyze").state, "success");
  assert.equal(nodes.find((n) => n.id === "map").state, "active");
  assert.equal(nodes.find((n) => n.id === "review").state, "pending");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend
npm test -- src/agentTimeline.test.js
```

Expected: FAIL because current code sets `map` to `success` and `review` to `active`.

- [ ] **Step 3: Implement minimal `MAPPING_READY` fix**

In `frontend/src/agentTimeline.js`, replace the `MAPPING_READY` case with:

```js
case "MAPPING_READY":
  setState("created", "success");
  setState("analyze", "success");
  setState("map", "active", "Map extracted fields before reviewing values.");
  setState("review", "pending");
  break;
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
cd frontend
npm test -- src/agentTimeline.test.js
```

Expected: PASS for all `agentTimeline` tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/agentTimeline.js frontend/src/agentTimeline.test.js
git commit -m "fix: correct mapping-ready workflow state"
```

---

### Task 2: Derive Failure Location from Logs

**Files:**
- Modify: `frontend/src/agentTimeline.js`
- Modify: `frontend/src/agentTimeline.test.js`

**Interfaces:**
- Consumes: task plus task logs from `api.listTaskLogs(taskId)`.
- Produces: `getWorkflowTimeline(task, logs = [])`, where latest failed log action controls failed node.

- [ ] **Step 1: Write failing tests for failed fill and submit**

Add this to `frontend/src/agentTimeline.test.js`:

```js
test("getWorkflowTimeline marks fill failed from failed fill_form log", () => {
  const nodes = getWorkflowTimeline(
    { status: "FAILED", form_fields: [{ id: 1, mapped_value: "Alex" }] },
    [{ id: 10, action: "fill_form", status: "FAILED", created_at: "2026-07-02T10:00:00Z" }],
  );

  assert.equal(nodes.find((n) => n.id === "confirm").state, "success");
  assert.equal(nodes.find((n) => n.id === "fill").state, "failed");
  assert.equal(nodes.find((n) => n.id === "approve").state, "pending");
});

test("getWorkflowTimeline marks submit failed from failed submit_form log", () => {
  const nodes = getWorkflowTimeline(
    { status: "FAILED", form_fields: [{ id: 1, mapped_value: "Alex" }] },
    [{ id: 11, action: "submit_form", status: "FAILED", created_at: "2026-07-02T10:01:00Z" }],
  );

  assert.equal(nodes.find((n) => n.id === "fill").state, "success");
  assert.equal(nodes.find((n) => n.id === "approve").state, "success");
  assert.equal(nodes.find((n) => n.id === "submit").state, "failed");
});
```

- [ ] **Step 2: Write failing test for failed analyze**

Add:

```js
test("getWorkflowTimeline marks analyze failed from failed analyze_form log", () => {
  const nodes = getWorkflowTimeline(
    { status: "FAILED", form_fields: [] },
    [{ id: 12, action: "analyze_form", status: "FAILED", created_at: "2026-07-02T10:02:00Z" }],
  );

  assert.equal(nodes.find((n) => n.id === "created").state, "success");
  assert.equal(nodes.find((n) => n.id === "analyze").state, "failed");
  assert.equal(nodes.find((n) => n.id === "map").state, "pending");
});
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
cd frontend
npm test -- src/agentTimeline.test.js
```

Expected: FAIL because `getWorkflowTimeline` ignores logs and misplaces failures.

- [ ] **Step 4: Implement log helper**

Add near the top of `frontend/src/agentTimeline.js`:

```js
function latestFailedAction(logs) {
  return [...logs]
    .filter((log) => log.status === "FAILED")
    .sort((a, b) => {
      const timeDiff = new Date(b.created_at || 0) - new Date(a.created_at || 0);
      return timeDiff || (Number(b.id) || 0) - (Number(a.id) || 0);
    })[0]?.action;
}
```

Change the signature:

```js
function getWorkflowTimeline(task, logs = []) {
```

- [ ] **Step 5: Replace `FAILED` branch**

Replace the current `case "FAILED":` block with:

```js
case "FAILED": {
  setAllTo("pending");
  setState("created", "success");

  const failedAction = latestFailedAction(logs);
  if (failedAction === "analyze_form" || failedAction === "manual_login" || failedAction === "resume_after_login") {
    setState("analyze", "failed");
  } else if (failedAction === "map_fields" || failedAction === "llm_map_fields") {
    setState("analyze", "success");
    setState("map", "failed");
  } else if (failedAction === "fill_form") {
    setState("analyze", "success");
    setState("map", "success");
    setState("review", "success");
    setState("confirm", "success");
    setState("fill", "failed");
  } else if (failedAction === "submit_form" || failedAction === "confirm_submit") {
    setState("analyze", "success");
    setState("map", "success");
    setState("review", "success");
    setState("confirm", "success");
    setState("fill", "success");
    setState("approve", "success");
    setState("submit", "failed");
  } else {
    const hasFields = (task?.form_fields || []).length > 0;
    setState("analyze", hasFields ? "success" : "failed");
    if (hasFields) {
      setState("map", "failed");
    }
  }
  break;
}
```

If actual failed mapping logs use a different action name, first inspect logs with:

```bash
rg -n 'create_log\\(|action="' backend/app frontend/src
```

Then update the action list and tests with exact existing action names.

- [ ] **Step 6: Run focused tests**

Run:

```bash
cd frontend
npm test -- src/agentTimeline.test.js
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/agentTimeline.js frontend/src/agentTimeline.test.js
git commit -m "fix: derive failed workflow step from logs"
```

---

### Task 3: Refresh Logs and LLM Usage After Mutating Actions

**Files:**
- Modify: `frontend/src/pages/TaskDetail.jsx`

**Interfaces:**
- Consumes: `api.getTask`, `api.listTaskScreenshots`, `api.listTaskLogs`, `api.getTaskLlmUsage`.
- Produces: current `task`, `screenshots`, `taskLogs`, and `llmUsage` after each user action.

- [ ] **Step 1: Add or keep `taskLogs` state**

In `frontend/src/pages/TaskDetail.jsx`, ensure state exists:

```js
const [taskLogs, setTaskLogs] = useState([]);
```

- [ ] **Step 2: Create refresh helper**

Replace `refreshTaskHistory` with:

```js
async function refreshTaskData(nextTask = null) {
  const [taskResult, screenshotItems, logItems, usageResult] = await Promise.all([
    nextTask ? Promise.resolve(nextTask) : api.getTask(taskId),
    api.listTaskScreenshots(taskId),
    api.listTaskLogs(taskId),
    api.getTaskLlmUsage(taskId).catch(() => null),
  ]);
  setTask(taskResult);
  setScreenshots(screenshotItems);
  setTaskLogs(logItems);
  setLlmUsage(usageResult);
}
```

- [ ] **Step 3: Use refresh helper on initial load**

Change the initial data load to include logs and usage:

```js
useEffect(() => {
  Promise.all([
    api.getTask(taskId),
    api.listTaskScreenshots(taskId),
    api.listProfiles(),
    api.listLlmProviders(),
    api.listTaskLogs(taskId),
    api.getTaskLlmUsage(taskId).catch(() => null),
  ])
    .then(([taskResult, screenshotItems, profileItems, providerItems, logItems, usageResult]) => {
      setTask(taskResult);
      setScreenshots(screenshotItems);
      setProfiles(profileItems);
      setLlmProviders(providerItems);
      setTaskLogs(logItems);
      setLlmUsage(usageResult);
      setSelectedLlmProvider(getSavedLlmProvider(providerItems));
    })
    .catch((requestError) => setError(requestError.message))
    .finally(() => setLoading(false));
}, [taskId]);
```

Remove the separate `useEffect` that only calls `api.getTaskLlmUsage(taskId)` and `api.listTaskLogs(taskId)`.

- [ ] **Step 4: Replace refresh call sites**

Replace:

```js
await refreshTaskHistory(...)
```

with:

```js
await refreshTaskData(...)
```

Apply this in `runAction`, `analyzeAndReview`, `loginAnalyzeAndMap`, and error paths.

- [ ] **Step 5: Refresh after map-field calls**

After:

```js
await api.mapTaskFields(taskId, getMappingOptions());
```

call:

```js
await refreshTaskData();
```

Do this before navigation where practical. If immediate navigation to review page makes this invisible, still keeping it makes error paths and browser back behavior consistent.

- [ ] **Step 6: Pass logs into timeline and avoid repeated recomputation**

Before `return`, add:

```js
const workflowNodes = task ? getWorkflowTimeline(task, taskLogs) : [];
```

Then replace:

```jsx
{getWorkflowTimeline(task).map((node, index) => (
```

with:

```jsx
{workflowNodes.map((node, index) => (
```

Replace:

```jsx
{index < getWorkflowTimeline(task).length - 1 && (
```

with:

```jsx
{index < workflowNodes.length - 1 && (
```

- [ ] **Step 7: Run build and tests**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: both commands pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/TaskDetail.jsx
git commit -m "fix: refresh task detail usage and logs after actions"
```

---

### Task 4: Add Timeline Styles

**Files:**
- Modify: existing frontend CSS file that defines `.card`, `.badge`, `.detail-list`

**Interfaces:**
- Consumes: classes emitted by `TaskDetail.jsx`.
- Produces: visible horizontal or wrapping workflow timeline with distinct pending, success, active, blocked, and failed states.

- [ ] **Step 1: Locate CSS file**

Run:

```bash
rg -n "\\.card|\\.detail-list|\\.badge" frontend/src -g "*.css"
```

Use the file that already owns task detail styles.

- [ ] **Step 2: Add CSS**

Add this CSS to that file:

```css
.workflow-timeline {
  overflow-x: auto;
}

.timeline {
  display: flex;
  align-items: flex-start;
  gap: 0;
  min-width: max-content;
}

.timeline-item {
  display: flex;
  align-items: center;
  position: relative;
}

.timeline-node {
  min-width: 96px;
  border: 1px solid var(--border-color, #d8dee4);
  border-radius: 8px;
  padding: 8px 10px;
  background: #fff;
  color: #57606a;
  font-size: 0.875rem;
  line-height: 1.2;
  text-align: center;
  white-space: nowrap;
}

.timeline-node.success {
  border-color: #2da44e;
  background: #f0fff4;
  color: #1a7f37;
}

.timeline-node.active {
  border-color: #0969da;
  background: #ddf4ff;
  color: #0550ae;
}

.timeline-node.blocked {
  border-color: #bf8700;
  background: #fff8c5;
  color: #9a6700;
}

.timeline-node.failed {
  border-color: #cf222e;
  background: #ffebe9;
  color: #cf222e;
}

.timeline-connector {
  width: 28px;
  height: 2px;
  background: #d8dee4;
}

.timeline-connector.completed {
  background: #2da44e;
}

.timeline-indicator {
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-left: 6px;
  border-radius: 999px;
  background: currentColor;
}

.timeline-help {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  width: 180px;
  margin: 0;
  color: #57606a;
  font-size: 0.75rem;
  line-height: 1.3;
  white-space: normal;
}

@media (max-width: 720px) {
  .timeline {
    flex-direction: column;
    min-width: 0;
    gap: 8px;
  }

  .timeline-item {
    flex-direction: column;
    align-items: flex-start;
  }

  .timeline-connector {
    width: 2px;
    height: 16px;
    margin-left: 18px;
  }

  .timeline-help {
    position: static;
    width: auto;
    margin-top: 4px;
  }
}
```

If the app uses different CSS variables, replace only `var(--border-color, #d8dee4)` with the existing border token.

- [ ] **Step 3: Run build**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 4: Manual browser verification**

Run:

```bash
cd frontend
npm run dev
```

Open the task detail page and verify:

- Success nodes are visually distinct.
- Active node is visually distinct.
- Failed node is visually distinct.
- Mobile width does not overlap help text.
- Long task URLs and timeline content do not push the page sideways except inside the timeline scroller.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/*.css frontend/src/**/*.css
git commit -m "style: add workflow timeline states"
```

---

### Task 5: Strengthen LLM Usage Display Behavior

**Files:**
- Modify: `frontend/src/pages/TaskDetail.jsx`
- Optional Modify: `frontend/src/debugReport.js` if keeping the current uncommitted debug report feature.

**Interfaces:**
- Consumes: `llmUsage.summary`.
- Produces: stable usage card for zero usage, unavailable usage, and refreshed usage.

- [ ] **Step 1: Make missing usage explicit in state**

Keep `llmUsage` as `null` for "not loaded or unavailable".

Render card only after task is loaded:

```jsx
<div className="card">
  <h3>LLM Usage</h3>
  {llmUsage?.summary ? (
    llmUsage.summary.request_count > 0 ? (
      <dl className="detail-list">
        <div>
          <dt>Requests</dt>
          <dd>{llmUsage.summary.request_count}</dd>
        </div>
        <div>
          <dt>Total tokens</dt>
          <dd>{llmUsage.summary.total_tokens}</dd>
        </div>
        <div>
          <dt>Cache hit rate</dt>
          <dd>{Math.round(llmUsage.summary.cache_hit_rate * 100)}%</dd>
        </div>
        <div>
          <dt>Cache hit tokens</dt>
          <dd>{llmUsage.summary.cache_hit_tokens}</dd>
        </div>
        <div>
          <dt>Cache miss tokens</dt>
          <dd>{llmUsage.summary.cache_miss_tokens}</dd>
        </div>
      </dl>
    ) : (
      <p>No LLM usage yet.</p>
    )
  ) : (
    <p>LLM usage is not available.</p>
  )}
</div>
```

- [ ] **Step 2: Verify cache hit math**

Backend currently returns `cache_hit_rate` as a ratio from 0 to 1. Keep:

```js
Math.round(llmUsage.summary.cache_hit_rate * 100)
```

Do not change it to `toFixed` unless product wants decimals.

- [ ] **Step 3: Run frontend tests and build**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/TaskDetail.jsx frontend/src/debugReport.js
git commit -m "fix: make llm usage panel resilient"
```

If `frontend/src/debugReport.js` is not part of this feature, do not stage it.

---

## Optional Backend Alternative: Add `failed_step` to `TaskResponse`

Use this only if product wants failure location available anywhere tasks are listed, not just task detail.

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routers/tasks.py`
- Test: `backend/tests/test_tasks_endpoint.py` or nearest existing task endpoint test file

**Interface:**

```py
failed_step: Literal["analyze", "map", "fill", "submit"] | None
```

Implementation approach:

- Query latest `TaskLog` with `status == "FAILED"` for each task detail response.
- Map:
  - `analyze_form`, `manual_login`, `resume_after_login` -> `analyze`
  - mapping log action names -> `map`
  - `fill_form` -> `fill`
  - `confirm_submit`, `submit_form` -> `submit`
- Keep field optional so old data and list responses remain safe.

Prefer avoiding this until multiple screens need it.

---

## Verification Matrix

- Frontend logic:
  - `cd frontend && npm test`
  - Must include tests for `MAPPING_READY`, failed analyze, failed fill, failed submit.
- Frontend production build:
  - `cd frontend && npm run build`
- Backend API compatibility:
  - If backend is unchanged, no backend tests required for this plan.
  - If `TaskResponse.failed_step` is added, run the relevant pytest file and one task endpoint integration test.
- Manual UI:
  - Task with `CREATED`
  - Task with `MAPPING_READY` before successful mapping
  - Task with `READY_TO_FILL`
  - Task with `WAITING_APPROVAL`
  - Task with `COMPLETED`
  - Task with `FAILED` after analyze/fill/submit failure
  - Task with zero LLM usage
  - Task after successful LLM mapping usage

## Self-Review

- Spec coverage:
  - Incorrect `MAPPING_READY` timeline state: covered by Task 1.
  - Incorrect failure node due to missing `failed_step`: covered by Task 2.
  - Missing timeline CSS: covered by Task 4.
  - Stale LLM usage after actions: covered by Task 3 and Task 5.
- Placeholder scan:
  - No TBD/TODO placeholders remain.
  - Optional backend path is explicitly scoped and not required for the recommended path.
- Type consistency:
  - `getWorkflowTimeline(task, logs = [])` is used consistently.
  - `taskLogs` is state in `TaskDetail.jsx` and is passed to `getWorkflowTimeline`.
  - `llmUsage.summary.cache_hit_rate` remains a 0-to-1 ratio.

## Execution Handoff

Plan complete. Recommended execution order:

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5

Each task should be implemented and tested independently. If the current worktree has unrelated uncommitted changes, stash or commit them separately before starting implementation.
