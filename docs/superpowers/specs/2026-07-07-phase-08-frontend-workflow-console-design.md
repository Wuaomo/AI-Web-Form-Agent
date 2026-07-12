# Phase 08 - Frontend Workflow Console (Design)

## Goal

Reorganize the existing React frontend so the product reads as a workflow platform without burying the user's main path under engineering diagnostics.

Phase 08 should make the normal path obvious:

- workflow templates
- workflow runs
- approvals
- workflow plan
- field mapping/review
- execution and final approval

Trace, LLM usage, agent reviews, screenshots, logs, and evaluation evidence must remain available, but they should be secondary by default.

This phase is primarily presentation, navigation, and information architecture. It should reuse existing backend APIs and existing page components wherever practical.

## Non-Goals / Hard Constraints

- Do not add a new backend API for Phase 08.
- Do not add a visual builder, drag-and-drop editor, or new frontend state library.
- Do not add a UI component framework.
- Do not add a second dashboard route or a `/runs` route.
- Do not add a dedicated `/workflows/:id` template detail page in this phase.
- Do not add a dedicated `/tasks/:taskId/trace` page in this phase.
- Do not rewrite the Approval Center into a new page/component hierarchy.
- Do not force a large-scale internal rename from `task` to `run` in API names, route params, or component identifiers.
- Do not turn this phase into rename churn. User-facing copy should change; internal code names only change when there is a direct local benefit.
- Do not make trace, LLM usage, agent reviews, screenshots, logs, or debug reports the default reading path for a successful run.

## Existing Code Surfaces

- App routes: [App.jsx](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/App.jsx)
- Global navigation: [Layout.jsx](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/components/Layout.jsx)
- Home page: [Dashboard.jsx](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/pages/Dashboard.jsx)
- Create page: [CreateTask.jsx](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/pages/CreateTask.jsx)
- Run detail page: [TaskDetail.jsx](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/pages/TaskDetail.jsx)
- Approval page: [ApprovalCenter.jsx](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/pages/ApprovalCenter.jsx)
- Evaluation page: [Benchmarks.jsx](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/pages/Benchmarks.jsx)
- Shared API client: [api.js](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/api.js)
- Existing presentation helpers:
  - [workflowPlanPresentation.js](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/workflowPlanPresentation.js)
  - [workflowTracePresentation.js](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/workflowTracePresentation.js)
  - [jobPresentation.js](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/jobPresentation.js)
  - [verificationPresentation.js](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/verificationPresentation.js)
  - [agentReviewPresentation.js](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/agentReviewPresentation.js)
- Upgrade reference: [08-frontend-workflow-console.md](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/docs/trae-upgrade/08-frontend-workflow-console.md)

## Product Language

User-visible copy should consistently use:

- `Runs`
- `Workflow Runs`
- `Workflow Templates`
- `Create run`
- `Workflow Run`

Avoid mixing `Dashboard` and `Runs` in visible navigation or page headings.

Important boundary:

- frontend user-visible copy should move to run/workflow-run wording
- API names, route params, and internal variable names such as `taskId`, `TaskDetail`, `api.getTask()` do not need to be renamed globally

## Information Architecture

Routes for this phase:

```text
/                         Runs
/workflows                Workflow Templates
/tasks/new                Create Workflow Run
/tasks/:taskId            Workflow Run Detail
/tasks/:taskId/review-mapping
/approvals                Approval Center
/benchmarks               Evaluation Center
/profiles                 Profiles
```

Constraints:

- `/` continues to reuse `Dashboard.jsx`
- no new `/runs` route
- no second dashboard page
- existing `/tasks/*` routes stay in place to avoid backend churn

## Global Navigation

Update the main navigation to exactly:

```text
Runs
Workflows
Approvals
Profiles
Evaluation
```

Explicit boundary:

- do not keep `Create Task` or `Create run` as a top-level nav item
- creation entry points live inside page content, not in main navigation

## Runs Home Page

Reuse [Dashboard.jsx](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/pages/Dashboard.jsx), but reposition it as a workflow-runs home page.

### Required changes

- eyebrow/title copy becomes `Runs` / `Workflow Runs`
- primary CTA becomes `Create run`
- main content becomes the recent workflow runs table
- backend status remains visible but is demoted to supporting information

### Content priority

Primary:

- recent workflow runs table
- create run CTA

Secondary:

- backend status
- light supporting actions such as profile management

### Runs table

Show:

- Run
- Status
- Workflow type
- Profile
- Description
- Created

Notes:

- links still point to `/tasks/:taskId`
- if workflow type is missing in a payload, fallback to `form_fill`
- no charts in this phase

## Workflow Templates Page

Create `frontend/src/pages/WorkflowTemplates.jsx`.

### Scope boundary

- this phase only adds a template list page
- do not add `/workflows/:id`
- do not add a detailed template drill-down page

### Data source

- `api.listWorkflowTemplates()`

### Presentation

Display each template as a compact card with:

- name
- description
- status badge (`Available` / `Coming soon`)
- create button for enabled templates only

For disabled templates:

- show `Coming soon`
- do not allow creation

The page should stay intentionally light. It does not need a complex step explorer, policy breakdown view, or long-form template details.

### Create action

Enabled templates route to:

```text
/tasks/new?workflow_type=<template_id>
```

## Create Workflow Run Page

Reuse [CreateTask.jsx](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/pages/CreateTask.jsx).

### User-facing goals

- title copy becomes `Create Workflow Run`
- page explains the user is creating a run from a workflow template
- keep current analyze -> map flow after successful creation

### Query handling boundary

`workflow_type` from the query string must be treated conservatively:

- it is only a default value
- the final enabled/disabled truth must come from the fetched template list
- query state must not bypass template validation

If the query points to a disabled or unknown template:

- show a small notice explaining the requested template is unavailable
- fallback the selected workflow type to `form_fill` when available
- if `form_fill` is unexpectedly unavailable, disable create rather than submitting an invalid template

This keeps the page tolerant without trusting stale links.

### Form behavior

Keep:

- URL input
- profile selection
- description
- workflow template selection
- LLM provider selection

Submit payload remains:

```json
{
  "url": "...",
  "profile_id": 1,
  "description": "...",
  "workflow_type": "form_fill"
}
```

## Workflow Run Detail

Reuse [TaskDetail.jsx](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/pages/TaskDetail.jsx).

### Naming boundary

- visible labels change to `Run` / `Workflow Run`
- internal symbols such as `TaskDetail`, `taskId`, and `api.getTask()` may remain unchanged

### Priority order

Task Detail should emphasize the user's operational path before diagnostics.

Recommended section order:

1. error and success messages
2. run header
3. primary action panel
4. pending approvals
5. workflow plan
6. verification results
7. mapping/review entry points
8. collapsed `Advanced` or `Debug` area

The advanced/debug area may contain:

- workflow trace
- agent reviews
- LLM usage
- screenshots
- logs / debug report / background job details

If a run fails, show a concise failure summary in the default path and provide a direct route to the relevant advanced evidence.

### Trace card boundary

Trace is diagnostic support, not the main content of Task Detail.

The Trace card must live in the advanced/debug area by default and must not visually outrank:

- plan
- approvals
- mapping
- verification

## Trace Card Design

Do not create a dedicated trace page in this phase.

### Summary (always visible)

The card must show:

- latest status
- total span count
- failed span count
- last phase/name

### Default list behavior

Default behavior is failed-only:

- if failed spans exist, show up to 3 failed spans by default
- if there are no failed spans, do not show any span list
- successful runs stay quiet and compact

### Show more behavior

- if failed spans exist, `Show more` expands the failed list to at most 10 failed spans
- if there are no failed spans, no list expansion is offered
- do not render the full trace list inside the card

### Full-data exits

Keep low-cost escape hatches rather than a larger trace surface:

- `View raw trace JSON`
- `Copy trace JSON`

These are sufficient for full inspection in Phase 08.

### Placement

- successful runs keep trace collapsed inside advanced/debug
- failed runs may show a small failed phase/name/error summary in the main path
- raw trace JSON is never shown inline by default

## Approval Center

Reuse [ApprovalCenter.jsx](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/frontend/src/pages/ApprovalCenter.jsx).

### Scope boundary

- do not create `pages/Approvals.jsx`
- do not redesign the approval card system
- do not introduce a new component library

### Required changes

- page title/navigation copy becomes `Approvals` / `Approval Center`
- keep the current list structure
- add or keep the run link to `/tasks/:taskId`
- fill visible gaps for:
  - risk level
  - reason
  - status

This is a refinement pass, not a re-architecture.

## Evaluation Center

Phase 07 already established the Evaluation Center on `/benchmarks`.

Phase 08 should only ensure navigation and cross-page wording are consistent:

- nav label becomes `Evaluation`
- page title remains `Evaluation Center`
- no separate evaluation route is added

## Presentation Helpers

Keep non-trivial view logic out of page components.

Required helper additions or extensions:

- `frontend/src/workflowTemplatePresentation.js`
- `frontend/src/workflowTracePresentation.js`
- `frontend/src/approvalPresentation.js` if risk/status labeling grows beyond small inline conditionals

Expected helper responsibilities:

- template status labels and create availability
- trace summary extraction
- failed-only slicing and show-more behavior
- raw trace JSON formatting/copy payload preparation
- approval risk/status labels when needed

Existing helper modules should be reused rather than replaced.

## CSS Guidelines

Modify `frontend/src/styles.css` minimally.

Goals:

- preserve the current visual system
- keep cards compact
- keep advanced/debug sections collapsed by default
- avoid nested cards
- keep tables scrollable on small screens
- ensure buttons and badges do not overflow

Phase 08 should feel more organized, not newly redesigned.

## Empty States

Required empty-state copy:

- no templates: `No workflow templates available.`
- no approvals: `No pending approvals.`
- no plan: `No workflow plan has been created yet.`
- no trace spans recorded yet: only use this when raw trace exists as an empty payload view; successful runs should normally just show the compact summary without a list

For trace specifically:

- if there are no failed spans, prefer summary + raw/copy actions over an oversized empty-state block

## Testing Scope

Frontend tests should stay lightweight and focus on presentation logic.

Suggested files:

- `workflowTemplatePresentation.test.js`
- `workflowTracePresentation.test.js`
- `approvalPresentation.test.js` if helper logic is introduced

Key cases:

- template `Coming soon` behavior and create enablement
- disabled/unknown `workflow_type` query falls back safely
- runs wording labels and fallback display logic
- trace summary formatting
- failed-only default list behavior
- show-more expansion capped at 10 failed spans
- no-failure trace stays collapsed
- successful runs keep advanced/debug evidence collapsed
- failed runs show a concise failure summary in the normal path
- raw trace copy/view payload formatting
- approval risk/status labels if helper added

Run:

```powershell
cd frontend
npm test
npm run build
```

## Acceptance Criteria

- the main navigation reflects workflow platform concepts
- `/` behaves as Runs, not Dashboard, without adding `/runs`
- Workflow Templates page exists as a simple list page
- enabled templates offer `Create` and disabled templates show `Coming soon`
- Create Workflow Run handles query `workflow_type` conservatively and falls back safely
- Task Detail uses run-oriented copy without requiring large internal renames
- Task Detail has a clear normal path for completing a run
- Trace, LLM usage, agent reviews, screenshots, logs, and debug reports are advanced/debug evidence by default
- failed runs expose a concise failure summary with access to the relevant evidence
- Approval Center remains the same page with improved wording and missing information filled in
- existing creation, mapping, review, approval, and evaluation flows continue to work
- frontend tests and build pass

## Implementation Order

1. update global navigation wording and routes
2. add Workflow Templates page and route
3. add template presentation helper and tests
4. update CreateTask into Create Workflow Run with conservative query handling
5. update Dashboard into Runs home
6. update TaskDetail wording, default path, and advanced/debug disclosure
7. refine ApprovalCenter wording and missing fields
8. add minimal CSS adjustments
9. run frontend tests and build
