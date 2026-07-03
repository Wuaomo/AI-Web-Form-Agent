# Phase 2 Generalized Page Actions

> For agentic workers: implement after Phase 1 evidence is stable. Keep this phase read-only from an action-execution perspective.

## Background

Phase 1 makes the current form-fill loop measurable and explainable. Phase 2
expands the model from form fields to typed page actions, but only as evidence.
The product should understand more page controls before it is allowed to execute
more behavior.

The current `FormField` pipeline remains the source of truth for reviewed form
filling. Phase 2 adds a parallel representation:

```text
Extracted form metadata -> PageElement -> ActionCandidate -> Task Detail evidence
```

## Goals

- Represent page controls as normalized `PageElement` records.
- Derive typed `ActionCandidate` records with explicit safety levels.
- Show safe, review-required, and blocked action candidates in Task Detail.
- Keep existing form-field APIs and browser execution behavior unchanged.
- Make unsafe or unsupported actions visible without making them executable.

## Non-Goals

- Do not execute action candidates.
- Do not add free-form autonomous clicking.
- Do not remove or rename existing form-field APIs.
- Do not broaden extraction to arbitrary DOM crawling in this phase.
- Do not add a workflow planner. That belongs to Phase 3 and Phase 4.

## Ponytail Scope Controls

| Temptation | Do instead | Add later only when |
| --- | --- | --- |
| Full DOM inventory engine | Normalize existing form extraction output first | Existing metadata cannot describe needed controls |
| New browser automation executor | Keep candidates read-only | Phase 4 approves reviewed plan execution |
| Generic action plugin system | Use a fixed action-type set | Real supported workflows need extension points |
| Separate safety policy service | Small deterministic classifier | Safety rules become duplicated across modules |
| New frontend state manager | Load candidates with existing Task Detail data flow | Candidate state becomes shared across multiple pages |

The smallest useful version is persistent normalized page-element evidence plus
deterministic candidate classification.

## Design

### Architecture

```text
Task analysis
  -> existing FormField records
  -> PageElement records
  -> ActionCandidate records
  -> read-only Task Detail display
```

`PageElement` stores normalized page-control metadata. `ActionCandidate` stores
what the system thinks could be done with that element and whether it is safe,
review-required, or blocked.

### Supported Action Types

Allowed candidate types:

```text
fill, select, check, upload, click_next, wait_for_login, pause_for_review, download
```

Blocked concepts:

```text
submit, payment, delete, purchase, destructive settings changes
```

Phase 2 may classify submit-like elements as blocked evidence. It must not add
buttons that execute them.

### Safety Levels

- `safe`: ordinary fill/select/check candidates.
- `review_required`: uploads and actions requiring explicit user inspection.
- `blocked`: password, OTP, payment, billing, delete, purchase, submit, or
  otherwise destructive controls.

Every blocked candidate needs a readable English `blocked_reason`.

## Implementation Plan

### Task 1: Page Element And Action Candidate Models

Files:

- Modify `backend/app/models.py`.
- Modify `backend/app/schemas.py`.
- Test with `backend/tests/test_database_migrations.py`.

Interfaces:

```text
PageElement:
  id, task_id, element_ref, selector, role, tag_name, element_type,
  label, text, placeholder, required, disabled, options_json

ActionCandidate:
  id, task_id, page_element_id, action_type, label, selector,
  safety_level, blocked_reason, confidence
```

Implementation:

- Add SQLAlchemy models with English docstrings.
- Add relationships from `Task`.
- Match `FormField.options` style with an `options` property.
- Add `PageElementResponse` and `ActionCandidateResponse`.
- Do not migrate existing form-field data.

Validation:

```powershell
cd backend
pytest tests/test_database_migrations.py -v
```

### Task 2: Normalize Existing Extraction Output

Files:

- Create `backend/app/services/page_element_extractor.py`.
- Modify `backend/app/routers/tasks.py`.
- Test with `backend/tests/test_page_element_extractor.py`.

Interface:

```python
def build_page_elements_from_form_fields(raw_fields: list[dict[str, object]]) -> list[dict[str, object]]:
    """Normalize extracted form field dictionaries into page element dictionaries."""
```

Implementation:

- Start with `input`, `textarea`, and `select`.
- Map `field_type` to `element_type`.
- Map `field_label` or `label` to `label`.
- Infer `tag_name` only when raw metadata does not provide it.
- Preserve selector, element reference, placeholder, required flag, and options.
- Do not add a new extraction engine.

Validation:

```powershell
cd backend
pytest tests/test_page_element_extractor.py -v
```

### Task 3: Derive Safe Action Candidates

Files:

- Create `backend/app/services/action_candidate_service.py`.
- Test with `backend/tests/test_action_candidate_service.py`.

Interface:

```python
SAFE_ACTION_TYPES = {"fill", "select", "check", "upload", "pause_for_review"}
BLOCKED_ACTION_TYPES = {"submit", "payment", "delete", "purchase"}

def classify_action_candidate(element: dict[str, object]) -> dict[str, object]:
    """Return one safe or blocked action candidate for a normalized page element."""
```

Implementation:

- Text inputs become `fill`.
- Select and radio controls become `select`.
- Checkbox controls become `check`.
- File inputs become `upload` with `review_required`.
- Password, OTP, payment, billing, card, delete, purchase, and submit-like
  elements become blocked.
- Do not execute candidates.

Validation:

```powershell
cd backend
pytest tests/test_action_candidate_service.py -v
```

### Task 4: Persist Candidates After Analysis

Files:

- Modify `backend/app/routers/tasks.py`.
- Test with `backend/tests/test_task_action_candidates_endpoint.py`.

Implementation:

- In the same transaction that saves form fields, delete old page elements and
  candidates for the task, then insert new ones.
- Keep `task.status = "MAPPING_READY"` unchanged.
- Add one action log with action `derive_action_candidates` and status
  `SUCCESS`.
- Avoid duplicate candidates after repeated analysis.

Validation:

```powershell
cd backend
pytest tests/test_task_action_candidates_endpoint.py -v
```

### Task 5: Read-Only Candidate API

Files:

- Modify `backend/app/routers/tasks.py`.
- Modify `frontend/src/api.js`.
- Test with `backend/tests/test_task_action_candidates_endpoint.py`.

Endpoint:

```text
GET /tasks/{task_id}/action-candidates
```

Implementation:

- Return candidates ordered by `id`.
- Return `404` for a missing task.
- Do not include mapped values.
- Add `api.listTaskActionCandidates(taskId)`.

### Task 6: Task Detail Candidate Display

Files:

- Create `frontend/src/actionCandidatePresentation.js`.
- Create `frontend/src/actionCandidatePresentation.test.js`.
- Modify `frontend/src/pages/TaskDetail.jsx`.
- Modify `frontend/src/styles.css` only as needed.

Interface:

```javascript
export function groupActionCandidates(candidates = []) {
  return { safe: [], reviewRequired: [], blocked: [] };
}

export function actionTypeLabel(actionType) {
  return "Fill";
}
```

Implementation:

- Add section heading `Page action candidates`.
- Show grouped counts: `Safe`, `Review required`, `Blocked`.
- For each candidate show action label, element label, safety level, and blocked
  reason.
- Do not add execution buttons.

Validation:

```powershell
cd frontend
npm test -- actionCandidatePresentation.test.js
```

### Task 7: Verification

Run:

```powershell
cd backend
pytest -v
```

```powershell
cd frontend
npm test
npm run build
```

Manual checks:

- Existing form-filling flow still works.
- Task Detail shows page action candidates.
- No action candidate can be executed from the UI.

## Risks

- **Model drift from FormField:** Keep Phase 2 derived from existing extraction
  output so both views stay aligned.
- **Safety ambiguity:** Prefer blocked with explanation over silently treating
  sensitive elements as safe.
- **Scope creep into execution:** Candidate display is evidence only. Execution
  waits for reviewable plans in Phase 4.

## Follow-Up

- Add broader DOM extraction only after the existing form-derived candidates are
  insufficient.
- Add execution only through approved workflow plans.
- Add richer candidate ordering only when DOM order is available and tested.

## Acceptance Criteria

- New models persist cleanly.
- Analysis creates page elements and action candidates without breaking existing
  form fields.
- The candidate API is read-only.
- Task Detail displays candidates clearly.
- No new browser action execution path exists.

## Self-Review

- This phase broadens understanding, not autonomy.
- It reuses existing extraction data before building new extraction machinery.
- It creates the minimum substrate needed for later workflow planning.
