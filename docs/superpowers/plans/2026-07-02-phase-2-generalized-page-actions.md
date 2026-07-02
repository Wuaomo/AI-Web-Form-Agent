# Phase 2 Generalized Page Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the system from form-field filling to a controlled page-action model that can represent safe browser actions beyond text inputs.

**Architecture:** Keep `FormField` behavior intact and introduce a parallel action layer. The backend extracts `PageElement` records and derives `ActionCandidate` objects; the frontend shows read-only action evidence before later phases allow plan review and execution.

**Tech Stack:** Python, FastAPI, SQLAlchemy, SQLite, pytest, React, Vite, Node test runner, Playwright.

## Global Constraints

- All user-facing page text must be English.
- All new code comments and docstrings must be English.
- Do not remove or rename the existing form-field APIs.
- Do not allow free-form autonomous clicking.
- Only support explicit, typed action candidates: `fill`, `select`, `check`, `upload`, `click_next`, `wait_for_login`, `pause_for_review`, `download`.
- `submit`, `payment`, `delete`, `purchase`, and destructive actions must be blocked unless a later explicit approval step supports them.
- Every backend action candidate must include a safety classification.

---

## File Structure

- `backend/app/models.py`: add persistent `PageElement` and `ActionCandidate` models.
- `backend/app/schemas.py`: add response schemas for page elements and action candidates.
- `backend/app/services/page_element_extractor.py`: convert extracted DOM metadata into normalized page elements.
- `backend/app/services/action_candidate_service.py`: derive safe action candidates from page elements.
- `backend/app/routers/tasks.py`: expose read-only page element and action candidate endpoints.
- `backend/tests/test_page_element_extractor.py`: extraction normalization tests.
- `backend/tests/test_action_candidate_service.py`: safety classification tests.
- `backend/tests/test_task_action_candidates_endpoint.py`: API endpoint tests.
- `frontend/src/actionCandidatePresentation.js`: frontend labels and grouping helpers.
- `frontend/src/actionCandidatePresentation.test.js`: helper tests.
- `frontend/src/pages/TaskDetail.jsx`: show action candidates as evidence.

---

### Task 1: Add Page Element And Action Candidate Models

**Purpose:** Create a general action representation without breaking existing `FormField` records.

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Test: `backend/tests/test_database_migrations.py`

**Interfaces:**
- `PageElement` fields:
  - `id: int`
  - `task_id: int`
  - `element_ref: str | None`
  - `selector: str`
  - `role: str | None`
  - `tag_name: str`
  - `element_type: str | None`
  - `label: str | None`
  - `text: str | None`
  - `placeholder: str | None`
  - `required: bool`
  - `disabled: bool`
  - `options_json: str | None`
- `ActionCandidate` fields:
  - `id: int`
  - `task_id: int`
  - `page_element_id: int | None`
  - `action_type: str`
  - `label: str`
  - `selector: str | None`
  - `safety_level: str`
  - `blocked_reason: str | None`
  - `confidence: float | None`

**Implementation Instructions:**
- [ ] Add SQLAlchemy models with English docstrings.
- [ ] Add relationships from `Task` to `page_elements` and `action_candidates`.
- [ ] Use `options_json` with a property named `options`, matching the style of `FormField.options`.
- [ ] Add Pydantic response schemas named `PageElementResponse` and `ActionCandidateResponse`.
- [ ] Do not migrate existing form field data into these tables.

**Tests:**
- [ ] Verify tables can be created through the existing database initialization path.
- [ ] Verify `PageElement.options` returns an empty list for invalid JSON.
- [ ] Run: `cd backend; pytest tests/test_database_migrations.py -v`

**Acceptance Criteria:**
- New models persist cleanly.
- Existing task and form-field tests still pass.

---

### Task 2: Normalize Extracted DOM Into Page Elements

**Purpose:** Convert current form extraction output into a broader page element inventory.

**Files:**
- Create: `backend/app/services/page_element_extractor.py`
- Modify: `backend/app/routers/tasks.py`
- Test: `backend/tests/test_page_element_extractor.py`

**Interfaces:**
- Produce function:

```python
def build_page_elements_from_form_fields(raw_fields: list[dict[str, object]]) -> list[dict[str, object]]:
    """Normalize extracted form field dictionaries into page element dictionaries."""
```

**Implementation Instructions:**
- [ ] Start with form controls only: `input`, `textarea`, and `select`.
- [ ] Map `field_type` to `element_type`.
- [ ] Map `field_label` or `label` to `label`.
- [ ] Set `tag_name` from raw metadata when available; otherwise infer from `field_type`.
- [ ] Preserve `selector`, `element_ref`, `placeholder`, `required`, and options.
- [ ] Do not extract buttons in this task unless they already appear in existing form extraction output.
- [ ] Add English comments only where normalization decisions are not obvious.

**Tests:**
- [ ] Text input becomes a page element with `element_type: "text"`.
- [ ] Select field preserves options.
- [ ] Missing label falls back to placeholder or selector.
- [ ] Run: `cd backend; pytest tests/test_page_element_extractor.py -v`

**Acceptance Criteria:**
- Page elements can be generated from existing extraction data.
- Existing form analysis remains unchanged.

---

### Task 3: Derive Safe Action Candidates

**Purpose:** Turn normalized page elements into typed action candidates with safety classifications.

**Files:**
- Create: `backend/app/services/action_candidate_service.py`
- Test: `backend/tests/test_action_candidate_service.py`

**Interfaces:**
- Produce:

```python
SAFE_ACTION_TYPES = {"fill", "select", "check", "upload", "pause_for_review"}
BLOCKED_ACTION_TYPES = {"submit", "payment", "delete", "purchase"}

def classify_action_candidate(element: dict[str, object]) -> dict[str, object]:
    """Return one safe or blocked action candidate for a normalized page element."""
```

**Implementation Instructions:**
- [ ] Text-like inputs become `fill`.
- [ ] Select and radio controls become `select`.
- [ ] Checkbox controls become `check`.
- [ ] File inputs become `upload` with `safety_level: "review_required"`.
- [ ] Password, OTP, payment, card, billing, delete, purchase, and submit-like elements become blocked candidates.
- [ ] Use `safety_level` values:
  - `"safe"`
  - `"review_required"`
  - `"blocked"`
- [ ] Set `blocked_reason` for every blocked candidate.
- [ ] Do not execute any candidate in this task.

**Tests:**
- [ ] Text input returns `fill` and `safe`.
- [ ] File input returns `upload` and `review_required`.
- [ ] Password input returns `blocked`.
- [ ] Submit button returns `blocked`.
- [ ] Run: `cd backend; pytest tests/test_action_candidate_service.py -v`

**Acceptance Criteria:**
- Every candidate has an action type and safety classification.
- Unsafe actions are visible but blocked.

---

### Task 4: Persist Candidates After Analysis

**Purpose:** Save page elements and action candidates whenever a task is analyzed.

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Test: `backend/tests/test_task_action_candidates_endpoint.py`

**Implementation Instructions:**
- [ ] In `save_extracted_fields()`, after saving `FormField` records, also save `PageElement` and `ActionCandidate` records.
- [ ] Delete old page elements and action candidates for the task before inserting new ones.
- [ ] Use the same database transaction as form-field persistence.
- [ ] Keep `task.status = "MAPPING_READY"` behavior unchanged.
- [ ] Create one action log with action `"derive_action_candidates"` and status `"SUCCESS"`.

**Tests:**
- [ ] Analyzed task has page elements.
- [ ] Analyzed task has action candidates.
- [ ] Re-analysis replaces previous candidates instead of duplicating them.
- [ ] Run: `cd backend; pytest tests/test_task_action_candidates_endpoint.py -v`

**Acceptance Criteria:**
- Analysis produces field mappings and page-action evidence together.
- No duplicate candidates appear after repeated analysis.

---

### Task 5: Add Read-Only Action Candidate API

**Purpose:** Allow the frontend to display action candidates without executing them.

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `frontend/src/api.js`
- Test: `backend/tests/test_task_action_candidates_endpoint.py`

**Interfaces:**
- Add:

```text
GET /tasks/{task_id}/action-candidates
```

- Response: `list[ActionCandidateResponse]`.

**Implementation Instructions:**
- [ ] Return candidates ordered by `id`.
- [ ] Return `404` if task does not exist.
- [ ] Do not include mapped values in this response.
- [ ] Add `api.listTaskActionCandidates(taskId)` in `frontend/src/api.js`.

**Tests:**
- [ ] Existing task returns list.
- [ ] Missing task returns `404`.
- [ ] Frontend API method builds the correct path if API tests cover paths.
- [ ] Run: `cd backend; pytest tests/test_task_action_candidates_endpoint.py -v`

**Acceptance Criteria:**
- Frontend can retrieve candidates.
- Endpoint is read-only.

---

### Task 6: Display Action Candidates On Task Detail

**Purpose:** Show that the app understands page actions beyond fields while still keeping execution locked down.

**Files:**
- Create: `frontend/src/actionCandidatePresentation.js`
- Create or Modify: `frontend/src/actionCandidatePresentation.test.js`
- Modify: `frontend/src/pages/TaskDetail.jsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Produce:

```javascript
export function groupActionCandidates(candidates = []) {
  return { safe: [], reviewRequired: [], blocked: [] };
}

export function actionTypeLabel(actionType) {
  return "Fill";
}
```

**Implementation Instructions:**
- [ ] Load action candidates in `TaskDetail.jsx` alongside task, logs, screenshots, and LLM usage.
- [ ] Add a section heading `"Page action candidates"`.
- [ ] Show grouped counts:
  - `"Safe"`
  - `"Review required"`
  - `"Blocked"`
- [ ] For each candidate show action label, element label, safety level, and blocked reason if present.
- [ ] Do not add execution buttons in this phase.
- [ ] Keep all page text English.

**Tests:**
- [ ] Safe/review-required/blocked candidates are grouped correctly.
- [ ] Unknown action type renders a humanized label.
- [ ] Run: `cd frontend; npm test -- actionCandidatePresentation.test.js`

**Acceptance Criteria:**
- Users can see generalized page-action understanding.
- The app still only executes the existing reviewed form-fill flow.

---

### Task 7: Verification

**Commands:**
- [ ] Run: `cd backend; pytest -v`
- [ ] Run: `cd frontend; npm test`
- [ ] Run: `cd frontend; npm run build`

**Acceptance Criteria:**
- All tests pass.
- Existing form-filling flow still works.
- Action candidates are visible but not executable.

## Self-Review

- Spec coverage: This plan upgrades field-only extraction into typed page-action evidence.
- Placeholder scan: No placeholder implementation steps remain.
- Scope check: This phase does not implement multi-step workflow execution or broad autonomous browsing.
