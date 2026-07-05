# Phase 08 - Frontend Workflow Console

## Goal

Reorganize the frontend around workflow operations: templates, runs, approvals, trace, and evaluation.

This phase is mostly presentation and navigation. It should make the project feel like a workflow platform without changing backend behavior beyond existing APIs from previous phases.

## Why This Matters

Professional projects are judged quickly from the UI. The current UI shows form tasks, but the upgraded project should make these concepts visible:

- workflow template
- planned steps
- approval queue
- trace timeline
- evaluation results
- verification evidence

## Current Code To Read

- `frontend/src/App.jsx`
- `frontend/src/api.js`
- `frontend/src/components/Layout.jsx`
- `frontend/src/pages/Dashboard.jsx`
- `frontend/src/pages/CreateTask.jsx`
- `frontend/src/pages/TaskDetail.jsx`
- `frontend/src/pages/ReviewMapping.jsx`
- `frontend/src/pages/Benchmarks.jsx`
- `frontend/src/styles.css`
- `frontend/src/taskRunState.js`
- `frontend/src/jobPresentation.js`
- `frontend/src/verificationPresentation.js`
- `frontend/src/agentReviewPresentation.js`

## Scope

Add/adjust frontend pages:

- Workflow Templates
- Workflow Runs dashboard
- Run Detail with plan + trace + approvals
- Approval Center
- Evaluation Center

## Out Of Scope

- Do not add a visual drag-and-drop builder.
- Do not add a complex global state library.
- Do not add UI component frameworks.
- Do not redesign the entire visual style.
- Do not implement backend APIs here; use APIs from earlier phases.

## Information Architecture

Routes:

```text
/                         Workflow Runs dashboard
/workflows                Workflow Templates
/tasks/new                Create Workflow Run
/tasks/:taskId            Workflow Run Detail
/tasks/:taskId/review-mapping
/tasks/:taskId/trace      Optional dedicated trace page
/approvals                Approval Center
/benchmarks               Evaluation Center
/profiles                 Profiles
```

Keep existing task URLs to avoid backend churn.

## Navigation

Update `Layout.jsx` navigation:

```text
Runs
Workflows
Approvals
Profiles
Evaluation
```

Use existing styling.

## Page 1: Workflow Runs Dashboard

Current `Dashboard.jsx` can become runs dashboard.

Show:

- backend status
- primary CTA: `Create run`
- recent runs table
- status badge
- workflow type
- profile
- created time

Optional summary cards:

- total runs
- waiting approvals
- failed runs
- completed runs

Do not add charts in this phase.

## Page 2: Workflow Templates

Create `frontend/src/pages/WorkflowTemplates.jsx`.

Uses:

```js
api.listWorkflowTemplates()
```

Display each template as a card:

- name
- description
- enabled/coming soon badge
- ordered step list
- approval policy summary
- create button for enabled templates

Create button routes to:

```text
/tasks/new?workflow_type=form_fill
```

## Page 3: Create Workflow Run

Update `CreateTask.jsx`:

- read `workflow_type` from query string if present
- load templates
- select workflow type
- if selected template disabled, disable create button
- keep profile selector and URL input
- label page as `Create Workflow Run`

Form payload:

```js
{
  url,
  profile_id,
  description,
  workflow_type
}
```

## Page 4: Workflow Run Detail

Update `TaskDetail.jsx`.

Suggested sections in this order:

1. Error/success messages
2. Run header
3. Primary action panel
4. Pending approvals
5. Workflow plan
6. Workflow trace
7. Verification results
8. Agent reviews
9. LLM usage
10. Screenshots
11. Logs/debug report

Keep cards compact. Do not nest cards inside cards.

## Page 5: Dedicated Trace Page

Optional but recommended if Task Detail becomes too long.

Create `frontend/src/pages/RunTrace.jsx`.

Route:

```text
/tasks/:taskId/trace
```

Display:

- timeline list
- filters by phase/status
- expandable JSON input/output
- screenshot link if `screenshot_id` exists

Keep JSON collapsed by default.

## Page 6: Approval Center

Create `frontend/src/pages/Approvals.jsx`.

Uses:

```js
api.listApprovals({ status: "PENDING" })
api.approveRequest(id)
api.rejectRequest(id)
```

Display:

- pending approvals
- risk level
- reason
- proposed action summary
- task link
- approve/reject buttons

After approve/reject, refresh list.

## Page 7: Evaluation Center

Use existing `Benchmarks.jsx` and update headings/copy:

- page title: `Evaluation Center`
- route can remain `/benchmarks`
- controls from Phase 07
- show run comparison and report copy

## Presentation Helpers

Create helpers when logic is non-trivial:

- `frontend/src/workflowTemplatePresentation.js`
- `frontend/src/workflowPlanPresentation.js`
- `frontend/src/workflowTracePresentation.js`
- `frontend/src/approvalPresentation.js`

Avoid putting sorting/label logic directly in page components.

## CSS Guidelines

Modify `frontend/src/styles.css`.

Add classes:

```css
.workflow-step-list
.workflow-step-item
.trace-list
.trace-item
.trace-meta
.approval-list
.approval-card
.risk-low
.risk-medium
.risk-high
```

Constraints:

- no decorative gradient orbs
- no nested cards
- text must not overflow buttons/cards
- tables must remain horizontally scrollable on small screens
- badges should be compact

## Empty States

Add empty states:

- no templates: `No workflow templates available.`
- no approvals: `No pending approvals.`
- no trace: `No trace spans recorded yet.`
- no plan: `No workflow plan has been created yet.`

## Tests Required

Frontend tests:

- `workflowTemplatePresentation.test.js`
- `workflowPlanPresentation.test.js`
- `workflowTracePresentation.test.js`
- `approvalPresentation.test.js`

Test cases:

- labels and fallbacks
- sorting functions
- disabled template behavior
- risk label/class mapping
- trace summary formatting

Run:

```powershell
cd frontend
npm test
npm run build
```

## Acceptance Criteria

- Navigation reflects workflow platform concepts.
- Templates page exists.
- Approval Center exists.
- Task Detail shows workflow plan and trace when data exists.
- Evaluation page is positioned as evaluation, not just benchmark.
- Existing profile/task/review flows remain usable.
- Frontend tests and build pass.

## Implementation Order

1. Add/confirm API methods.
2. Add presentation helpers and tests.
3. Update navigation.
4. Add Workflow Templates page.
5. Update Create Task.
6. Add Approval Center.
7. Add plan/trace cards to Task Detail.
8. Optional: add dedicated Run Trace page.
9. Update Benchmarks title to Evaluation Center.
10. Add CSS.
11. Run tests/build.

## Trae Prompt

Implement Phase 08. Update the React/Vite frontend into a workflow console with Runs, Workflows, Approvals, Profiles, and Evaluation navigation. Add Workflow Templates and Approval Center pages, update Create Task and Task Detail to show workflow type/plan/trace/approvals, and keep existing flows working. Do not add new frontend dependencies.
