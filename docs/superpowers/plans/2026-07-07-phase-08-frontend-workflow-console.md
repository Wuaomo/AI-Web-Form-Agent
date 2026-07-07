# Phase 08 - Frontend Workflow Console (Implementation Plan)

**Goal:** Reposition the existing React frontend as a workflow console with Runs, Workflows, Approvals, Profiles, and Evaluation navigation, while keeping backend APIs and existing task-based internals intact.

**Hard boundaries:**
- Do not add new backend APIs.
- Do not add `/runs` or a second dashboard page.
- Do not add `/workflows/:id`.
- Do not add `/tasks/:taskId/trace`.
- Do not create a new `Approvals.jsx` page or rebuild the approval card system.
- Do not do large-scale internal rename churn from `task` to `run`.
- User-facing copy should say `Run / Workflow Run`; internal symbols such as `taskId`, `TaskDetail`, and `api.getTask()` may remain.

## Step 1 - Update App Routes and Global Navigation

**Files**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/Layout.jsx`

**Work**
- Add the `/workflows` route pointing to a new `WorkflowTemplates` page.
- Keep `/` mapped to `Dashboard.jsx`; do not add `/runs`.
- Keep existing `/tasks/*`, `/approvals`, `/profiles`, `/benchmarks` routes unchanged.
- Update main navigation labels to exactly:
  - `Runs`
  - `Workflows`
  - `Approvals`
  - `Profiles`
  - `Evaluation`
- Remove `Create Task` from top-level navigation.

## Step 2 - Add Workflow Templates Page and Helper

**Files**
- Create: `frontend/src/pages/WorkflowTemplates.jsx`
- Create: `frontend/src/workflowTemplatePresentation.js`
- Create: `frontend/src/workflowTemplatePresentation.test.js`
- Modify: `frontend/src/api.js` only if a convenience wrapper is missing (prefer reuse if already present)

**Work**
- Build a simple templates list page using `api.listWorkflowTemplates()`.
- Keep page scope intentionally small:
  - list only
  - no `/workflows/:id`
  - no complex template details view
- Each template card should show:
  - name
  - description
  - status label (`Available` / `Coming soon`)
  - `Create` button only for enabled templates
- Disabled templates should remain visible but not actionable.
- Move label/availability logic into `workflowTemplatePresentation.js` rather than inline conditionals inside the page.

## Step 3 - Update CreateTask into Create Workflow Run

**Files**
- Modify: `frontend/src/pages/CreateTask.jsx`
- Reuse: `frontend/src/workflowTemplatePresentation.js`
- Update tests if present for page-level helpers or API usage

**Work**
- Change visible copy from task-oriented wording to:
  - page title `Create Workflow Run`
  - action button `Create run`
- Read `workflow_type` from query string as a default only.
- Fetch templates and validate the requested/default workflow against server-provided template state.
- Conservative fallback rules:
  - if query `workflow_type` matches an enabled template, select it
  - if it points to a disabled or unknown template:
    - show a notice that the requested template is unavailable
    - fallback to `form_fill` if enabled
    - if `form_fill` is not enabled, disable create
- Keep submit behavior unchanged:
  - create run
  - analyze
  - map
  - navigate to review mapping
- Do not introduce a new backend validation path in frontend; the frontend only aligns the default selection to current template state.

## Step 4 - Reposition Dashboard as Runs Home

**Files**
- Modify: `frontend/src/pages/Dashboard.jsx`

**Work**
- Change page eyebrow/title to `Runs` / `Workflow Runs`.
- Change primary CTA to `Create run`.
- Make the recent runs table the main content block.
- Demote backend status to supporting information rather than hero content.
- Keep profile-management shortcut as secondary content.
- Update visible table labels from `Task` to `Run`, but keep links and underlying task objects unchanged.
- If workflow type is absent in the task payload, display `form_fill`.

## Step 5 - Refine TaskDetail as Workflow Run Detail

**Files**
- Modify: `frontend/src/pages/TaskDetail.jsx`
- Modify: `frontend/src/workflowTracePresentation.js`
- Create or update: `frontend/src/workflowTracePresentation.test.js`

**Work**
- Update user-visible copy to `Run` / `Workflow Run`.
- Keep internal identifiers (`taskId`, `task`, `TaskDetail`) as-is unless a local rename clearly improves readability.
- Reorder content so workflow operations come before diagnostics:
  - messages
  - run header
  - primary action panel
  - pending approvals
  - workflow plan
  - verification results
  - mapping/review entry point
  - workflow trace
  - diagnostics
- Keep Trace as a secondary card, not the main event.

### Trace card implementation

- Add helper functions for:
  - trace summary extraction
  - failed-span filtering
  - default visible items
  - expanded visible items (capped at 10)
  - raw JSON serialization/copy payload
- Card behavior:
  - always show summary:
    - latest status
    - total span count
    - failed span count
    - last phase/name
  - if failed spans exist:
    - default list shows up to 3 failed spans
    - `Show more` expands to at most 10 failed spans
  - if failed spans do not exist:
    - no list is shown
    - no expansion is offered
    - keep success path quiet
- Add low-cost full-data exits:
  - `View raw trace JSON`
  - `Copy trace JSON`
- Do not render the full trace list inline.

## Step 6 - Refine Approval Center In Place

**Files**
- Modify: `frontend/src/pages/ApprovalCenter.jsx`
- Create or modify: `frontend/src/approvalPresentation.js` only if label/risk logic becomes non-trivial
- Create or update tests only if helper logic is added

**Work**
- Keep the existing page/component.
- Update visible copy to `Approvals` / `Approval Center`.
- Keep the current list structure.
- Ensure each item clearly shows:
  - run link to `/tasks/:taskId`
  - reason
  - risk level
  - status
- Avoid a broader redesign or card rewrite.

## Step 7 - Align Evaluation Navigation and Page Labels

**Files**
- Modify: `frontend/src/components/Layout.jsx`
- Modify: `frontend/src/pages/Benchmarks.jsx` only if cross-page wording still says `Benchmarks` in visible headings/buttons

**Work**
- Ensure nav label is `Evaluation`.
- Keep route `/benchmarks`.
- Reuse existing Phase 07 Evaluation Center work; Phase 08 only aligns top-level naming.

## Step 8 - Minimal CSS Adjustments

**Files**
- Modify: `frontend/src/styles.css`

**Work**
- Add only the CSS needed to support:
  - workflow template cards
  - compact trace summary/list/actions
  - runs-home emphasis
  - approval metadata layout improvements
- Maintain current visual system:
  - no component-library style overhaul
  - no decorative redesign
  - no nested cards
- Keep tables horizontally scrollable on small screens.

## Step 9 - Frontend Test Checklist

**Files**
- Run/update:
  - `frontend/src/workflowTemplatePresentation.test.js`
  - `frontend/src/workflowTracePresentation.test.js`
  - `frontend/src/approvalPresentation.test.js` if helper added
  - existing tests affected by renamed visible copy

**Key cases**
- template status label and create availability
- disabled/unknown `workflow_type` query falls back safely
- runs wording and fallback workflow-type display
- trace summary formatting
- failed-only default trace list
- `Show more` capped at 10 failed spans
- no-failure trace stays collapsed
- raw trace JSON payload formatting or copy string generation
- approval risk/status labels if helper introduced

## Step 10 - Verification Commands

**Frontend tests**
```bash
npm test
```

**Frontend build**
```bash
npm run build
```

**Done when**
- navigation is workflow-console oriented without adding `/runs`
- Workflow Templates page exists and remains list-only
- Create Workflow Run handles `workflow_type` query conservatively and falls back to `form_fill` when needed
- Dashboard reads as Runs home
- TaskDetail shows a compact failed-only Trace card and keeps diagnostics secondary
- Approval Center is improved in place, not rebuilt
- visible wording uses `Run / Workflow Run` while internal task-based code remains mostly intact
- tests and build pass
