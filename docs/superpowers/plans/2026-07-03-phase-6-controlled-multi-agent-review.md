# Phase 6 Controlled Multi-Agent Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add specialized AI review roles for mapping critique, safety review, and execution verification without allowing autonomous browser control or bypassing human approval.

**Architecture:** Use a deterministic coordinator that calls specialist agents in a fixed order. Agents return strict JSON decisions. Agents do not directly control Playwright and cannot approve final submission.

**Tech Stack:** Python, FastAPI, SQLAlchemy, SQLite, pytest, React, Vite, Node test runner, existing LLM provider integration.

## Global Constraints

- Do not build a free-form multi-agent chat system.
- Do not let agents click, type, submit, or navigate in the browser.
- All agent outputs must be strict JSON and validated before persistence.
- Human review and final submission approval remain mandatory.
- All UI text and code comments must be English.

---

## File Structure

- Create: `backend/app/agent_constants.py`
- Modify: `backend/app/models.py` to add `AgentReview`.
- Create: `backend/app/services/agent_coordinator.py`
- Create: `backend/app/services/mapping_critic_agent.py`
- Create: `backend/app/services/safety_review_agent.py`
- Create: `backend/app/services/execution_verification_agent.py`
- Modify: `backend/app/routers/tasks.py`
- Create: `frontend/src/agentReviewPresentation.js`
- Modify: `frontend/src/pages/ReviewMapping.jsx` and/or `TaskDetail.jsx`.
- Add backend and frontend tests.

---

### Task 1: Define Agent Roles And Decision Constants

**Files:**
- Create: `backend/app/agent_constants.py`
- Create: `backend/tests/test_agent_constants.py`

**Constants:**

```python
AGENT_ROLE_MAPPING_CRITIC = "MAPPING_CRITIC"
AGENT_ROLE_SAFETY_REVIEW = "SAFETY_REVIEW"
AGENT_ROLE_EXECUTION_VERIFICATION = "EXECUTION_VERIFICATION"

AGENT_DECISION_PASS = "PASS"
AGENT_DECISION_REVIEW_REQUIRED = "REVIEW_REQUIRED"
AGENT_DECISION_BLOCK = "BLOCK"
```

**Steps:**
- [ ] Test constants are unique and uppercase.
- [ ] Implement constants with English docstring.
- [ ] Run: `cd backend; pytest tests/test_agent_constants.py -v`

**Acceptance Criteria:**
- Agent roles and decisions are stable and reusable.

---

### Task 2: Add AgentReview Model

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/tests/test_database_migrations.py`

**Model Contract:**

```python
class AgentReview(Base):
    id: int
    task_id: int
    role: str
    decision: str
    input_hash: str
    output_json: str
    model: str | None
    provider: str | None
    created_at: datetime
```

**Rules:**
- [ ] Store structured output JSON.
- [ ] Do not store full prompt text.
- [ ] Do not store API keys or credentials.
- [ ] Add `AgentReviewResponse`.

**Tests:**
- [ ] Agent review persists and loads by task.
- [ ] Output JSON round-trips.
- [ ] Run: `cd backend; pytest tests/test_database_migrations.py -v`

**Acceptance Criteria:**
- Agent decisions can be audited later.

---

### Task 3: Build Deterministic Agent Coordinator

**Files:**
- Create: `backend/app/services/agent_coordinator.py`
- Create: `backend/tests/test_agent_coordinator.py`

**Interfaces:**

```python
def build_agent_input_hash(payload: object) -> str:
    """Return deterministic hash for agent input."""

def validate_agent_json(payload: object, required_keys: set[str]) -> dict[str, object]:
    """Validate agent JSON output and return a dict."""

def run_agent_review_sequence(task_id: int, db: Session, roles: list[str]) -> list[AgentReview]:
    """Run selected review agents in fixed order."""
```

**Rules:**
- [ ] Coordinator decides order.
- [ ] Agent output must contain `decision`, `summary`, and `items`.
- [ ] Invalid JSON becomes `REVIEW_REQUIRED`, not silent success.
- [ ] Coordinator persists every accepted decision.

**Tests:**
- [ ] Input hash is deterministic.
- [ ] Missing required JSON key raises validation error.
- [ ] Invalid agent result becomes review-required evidence.
- [ ] Roles run in requested order.
- [ ] Run: `cd backend; pytest tests/test_agent_coordinator.py -v`

**Acceptance Criteria:**
- Agent orchestration is predictable and auditable.

---

### Task 4: Implement Mapping Critic Agent

**Files:**
- Create: `backend/app/services/mapping_critic_agent.py`
- Create: `backend/tests/test_mapping_critic_agent.py`

**Agent Input:**
- [ ] Extracted fields.
- [ ] Proposed mappings.
- [ ] Required status.
- [ ] Confidence scores.

**Agent Output JSON:**

```json
{
  "decision": "REVIEW_REQUIRED",
  "summary": "Two required fields need attention.",
  "items": [
    {
      "field_id": 1,
      "issue": "LOW_CONFIDENCE",
      "message": "The name field confidence is below threshold."
    }
  ]
}
```

**Rules:**
- [ ] Required unmapped fields produce `REVIEW_REQUIRED`.
- [ ] Low confidence fields produce `REVIEW_REQUIRED`.
- [ ] Obvious safe mappings can pass.
- [ ] The agent cannot modify mappings directly in this phase.

**Tests:**
- [ ] Required missing field creates review item.
- [ ] Low confidence field creates review item.
- [ ] All high-confidence required fields produce pass.
- [ ] Run: `cd backend; pytest tests/test_mapping_critic_agent.py -v`

**Acceptance Criteria:**
- Mapping review improves human review quality without changing values automatically.

---

### Task 5: Implement Safety Review Agent

**Files:**
- Create: `backend/app/services/safety_review_agent.py`
- Create: `backend/tests/test_safety_review_agent.py`

**Agent Input:**
- [ ] Extracted fields.
- [ ] Mapped values metadata.
- [ ] Field labels, types, selectors, options.

**Blocked Tokens:**

```text
password
otp
payment
card
billing
delete
purchase
submit
consent
terms
privacy
```

**Rules:**
- [ ] Payment/delete/purchase fields produce `BLOCK`.
- [ ] Password/OTP fields produce `BLOCK`.
- [ ] Consent/terms/privacy fields produce `REVIEW_REQUIRED`.
- [ ] Normal profile fields produce `PASS`.

**Tests:**
- [ ] Password field blocks.
- [ ] Payment field blocks.
- [ ] Terms checkbox requires review.
- [ ] Normal email field passes.
- [ ] Run: `cd backend; pytest tests/test_safety_review_agent.py -v`

**Acceptance Criteria:**
- Safety review never weakens existing backend safety rules.

---

### Task 6: Implement Execution Verification Agent

**Files:**
- Create: `backend/app/services/execution_verification_agent.py`
- Create: `backend/tests/test_execution_verification_agent.py`

**Input:**
- [ ] Verification results from Phase 5.
- [ ] Screenshot metadata.
- [ ] Action logs.

**Output:**
- [ ] `PASS` when all required fields verified.
- [ ] `REVIEW_REQUIRED` when optional fields fail.
- [ ] `BLOCK` when required fields fail or page navigated unexpectedly.

**Tests:**
- [ ] All required verified passes.
- [ ] Optional mismatch requires review.
- [ ] Required mismatch blocks.
- [ ] Unexpected navigation blocks.
- [ ] Run: `cd backend; pytest tests/test_execution_verification_agent.py -v`

**Acceptance Criteria:**
- Agent helps interpret verification evidence but does not approve submission.

---

### Task 7: Add Agent Review API

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Create: `backend/tests/test_agent_review_endpoint.py`
- Modify: `frontend/src/api.js`

**Endpoints:**

```text
POST /tasks/{task_id}/agent-reviews
GET /tasks/{task_id}/agent-reviews
```

**Behavior:**
- [ ] POST accepts roles list.
- [ ] POST runs coordinator.
- [ ] GET returns reviews newest first.
- [ ] Missing task returns `404`.
- [ ] Invalid role returns `400`.

**Tests:**
- [ ] Run mapping critic via endpoint.
- [ ] Invalid role rejected.
- [ ] Reviews listed after run.
- [ ] Run: `cd backend; pytest tests/test_agent_review_endpoint.py -v`

**Acceptance Criteria:**
- UI can trigger and display controlled agent reviews.

---

### Task 8: Add Frontend Agent Review Presentation

**Files:**
- Create: `frontend/src/agentReviewPresentation.js`
- Create: `frontend/src/agentReviewPresentation.test.js`
- Modify: `frontend/src/pages/ReviewMapping.jsx`
- Modify: `frontend/src/pages/TaskDetail.jsx`

**UI Behavior:**
- [ ] Show latest agent decision.
- [ ] Decision labels: `Passed`, `Review required`, `Blocked`.
- [ ] Show summary and item count.
- [ ] Do not show raw prompts.
- [ ] Button labels: `Run safety review`, `Run mapping review`, `Run verification review`.

**Tests:**
- [ ] Decision labels are stable.
- [ ] Unknown role is humanized.
- [ ] Review items summarize correctly.
- [ ] Run: `cd frontend; npm test -- agentReviewPresentation.test.js`

**Acceptance Criteria:**
- Users can benefit from agent review without seeing noisy internals.

---

### Task 9: End-To-End Verification

**Commands:**
- [ ] Run: `cd backend; pytest -v`
- [ ] Run: `cd frontend; npm run lint`
- [ ] Run: `cd frontend; npm test`
- [ ] Run: `cd frontend; npm run build`

**Manual Verification:**
- [ ] Run mapping review on a mapped task.
- [ ] Run safety review on a task with a consent field.
- [ ] Run execution verification review after fill.
- [ ] Confirm final submission still requires explicit approval.

**Done Criteria:**
- Multi-agent review is controlled, auditable, and bounded.
- Agent roles improve review and verification, not autonomous execution.

