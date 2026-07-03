# Phase 5 Execution Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify that browser automation actually wrote expected values into the page, instead of treating a Playwright fill command as proof of success.

**Architecture:** Add post-fill verification inside the browser execution layer. After filling, read each field's current browser value, compare it with expected mapped values, persist verification results, and surface failures in Task Detail and debug reports.

**Tech Stack:** Python, FastAPI, SQLAlchemy, SQLite, pytest, Playwright, React, Vite, Node test runner.

## Global Constraints

- Do not verify or display sensitive values such as passwords, OTPs, payment cards, or one-time consents.
- Do not submit forms during verification.
- Verification failures must not be hidden behind task success.
- All UI text and code comments must be English.

---

## File Structure

- Modify: `backend/app/models.py` to add `FieldVerificationResult`.
- Modify: `backend/app/schemas.py`.
- Modify: `backend/app/services/browser_executor.py`.
- Create: `backend/app/services/execution_verification_service.py`.
- Modify: `backend/app/routers/tasks.py`.
- Modify: `frontend/src/api.js`.
- Create: `frontend/src/verificationPresentation.js`.
- Modify: `frontend/src/pages/TaskDetail.jsx`.
- Add backend and frontend tests.

---

### Task 1: Add FieldVerificationResult Model

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/tests/test_database_migrations.py`

**Model Contract:**

```python
class FieldVerificationResult(Base):
    """Post-fill verification result for one form field."""

    id: int
    task_id: int
    field_id: int | None
    selector: str
    expected_value_hash: str | None
    actual_value_hash: str | None
    status: str
    reason: str | None
    message: str | None
    created_at: datetime
```

**Statuses:**

```text
VERIFIED
PARTIAL
FAILED
SKIPPED
```

**Reasons:**

```text
SELECTOR_NOT_FOUND
VALUE_MISMATCH
OPTION_NOT_SELECTED
FIELD_DISABLED
SENSITIVE_FIELD_SKIPPED
PAGE_NAVIGATED_UNEXPECTEDLY
```

**Steps:**
- [ ] Write database test creating verification results for a task.
- [ ] Store hashes, not raw expected/actual values.
- [ ] Add `FieldVerificationResultResponse`.
- [ ] Run: `cd backend; pytest tests/test_database_migrations.py -v`

**Acceptance Criteria:**
- Verification results persist without leaking raw values.

---

### Task 2: Create Verification Service

**Files:**
- Create: `backend/app/services/execution_verification_service.py`
- Create: `backend/tests/test_execution_verification_service.py`

**Interfaces:**

```python
def hash_verification_value(value: str | None) -> str | None:
    """Return a stable hash for a field value."""

def compare_field_value(expected: str | None, actual: str | None) -> tuple[str, str | None]:
    """Return verification status and reason."""

def should_skip_verification(field: FormField) -> bool:
    """Return whether a field should be skipped for safety or type reasons."""
```

**Rules:**
- [ ] Exact match returns `VERIFIED`.
- [ ] Empty expected value returns `SKIPPED`.
- [ ] Sensitive field returns `SKIPPED`.
- [ ] Mismatch returns `FAILED` with `VALUE_MISMATCH`.
- [ ] File inputs return `SKIPPED`.

**Tests:**
- [ ] Matching values verify.
- [ ] Mismatched values fail.
- [ ] Password-like field is skipped.
- [ ] File field is skipped.
- [ ] Hash function does not return raw value.
- [ ] Run: `cd backend; pytest tests/test_execution_verification_service.py -v`

**Acceptance Criteria:**
- Value comparison and safety skipping are isolated from Playwright code.

---

### Task 3: Read Actual Browser Values After Fill

**Files:**
- Modify: `backend/app/services/browser_executor.py`
- Modify: `backend/tests/test_browser_executor.py`

**Behavior:**
- [ ] After a field is filled, read its current value from the browser.
- [ ] Text inputs and textareas use DOM value.
- [ ] Select controls use selected value.
- [ ] Checkbox controls use checked state.
- [ ] Radio groups use selected option value.
- [ ] Selector-not-found returns a structured verification failure.

**Tests:**
- [ ] Text input actual value is read.
- [ ] Select actual value is read.
- [ ] Checkbox actual checked state is read.
- [ ] Missing selector produces `SELECTOR_NOT_FOUND`.
- [ ] Run: `cd backend; pytest tests/test_browser_executor.py -v`

**Acceptance Criteria:**
- Browser executor returns enough data for verification service.

---

### Task 4: Persist Verification Results During Fill

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/app/services/browser_executor.py`
- Create: `backend/tests/test_task_verification_endpoint.py`

**Behavior:**
- [ ] Delete previous verification results before a new fill attempt.
- [ ] Persist one verification result per mapped fillable field.
- [ ] If any required field verification fails, keep task status `FAILED` or a new clear status if introduced.
- [ ] If optional fields fail but required fields pass, task can still enter `WAITING_APPROVAL` with partial verification evidence.

**Tests:**
- [ ] Successful fill creates verified results.
- [ ] Missing selector creates failed result.
- [ ] Sensitive fields are skipped.
- [ ] Required verification failure prevents silent success.
- [ ] Run: `cd backend; pytest tests/test_task_verification_endpoint.py -v`

**Acceptance Criteria:**
- Fill status reflects verification outcome.
- Verification results are persisted for UI and debug reports.

---

### Task 5: Add Verification API

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `frontend/src/api.js`
- Modify: `backend/tests/test_task_verification_endpoint.py`

**Endpoint:**

```text
GET /tasks/{task_id}/verification-results
```

**Response:**

```json
[
  {
    "field_id": 1,
    "selector": "#email",
    "status": "VERIFIED",
    "reason": null,
    "message": null
  }
]
```

**Tests:**
- [ ] Existing task returns ordered verification results.
- [ ] Missing task returns `404`.
- [ ] Frontend API method uses correct path.
- [ ] Run: `cd backend; pytest tests/test_task_verification_endpoint.py -v`

**Acceptance Criteria:**
- Frontend can show verification summary.

---

### Task 6: Add Verification Presentation Helpers

**Files:**
- Create: `frontend/src/verificationPresentation.js`
- Create: `frontend/src/verificationPresentation.test.js`

**Interfaces:**

```javascript
export function summarizeVerificationResults(results = []) {}
export function verificationStatusLabel(status) {}
export function verificationReasonLabel(reason) {}
```

**Tests:**
- [ ] Summary counts verified, failed, skipped, and partial.
- [ ] Unknown status is humanized.
- [ ] Unknown reason is humanized.
- [ ] Run: `cd frontend; npm test -- verificationPresentation.test.js`

**Acceptance Criteria:**
- UI labels are centralized and tested.

---

### Task 7: Update Task Detail And Debug Report

**Files:**
- Modify: `frontend/src/pages/TaskDetail.jsx`
- Modify: `frontend/src/debugReport.js`
- Modify: `frontend/src/debugReport.test.js`

**UI Behavior:**
- [ ] Show verification summary cards: `Verified`, `Failed`, `Skipped`.
- [ ] Show failed verification details only when failures exist.
- [ ] Do not display raw expected or actual values.
- [ ] Debug report includes verification counts and failure reasons.

**Tests:**
- [ ] Debug report includes verification failure reason.
- [ ] Debug report does not include raw sensitive values.
- [ ] Run: `cd frontend; npm test -- debugReport.test.js`

**Acceptance Criteria:**
- User and reviewer can tell whether browser execution actually succeeded.

---

### Task 8: End-To-End Verification

**Commands:**
- [ ] Run: `cd backend; pytest -v`
- [ ] Run: `cd frontend; npm run lint`
- [ ] Run: `cd frontend; npm test`
- [ ] Run: `cd frontend; npm run build`

**Manual Verification:**
- [ ] Fill a local benchmark form.
- [ ] Confirm verification results show verified fields.
- [ ] Break a selector and confirm verification failure is visible.
- [ ] Confirm final submission still requires explicit approval.

**Done Criteria:**
- Execution success is based on post-action verification, not command invocation alone.

