# Phase 03 - Policy Engine And Approval Gates

## Goal

Introduce a deterministic policy engine and approval request system so risky AI/browser actions are explicitly allowed, reviewed, or blocked.

This phase makes human-in-the-loop behavior a first-class workflow concept instead of a few route-specific checks.

## Why This Matters

Professional AI workflow automation needs guardrails. This phase proves that:

- AI proposals are not automatically trusted.
- Risk is classified before execution.
- Human approval is required for sensitive actions.
- Dangerous actions are blocked by deterministic rules.
- Approval decisions are persisted and traceable.

## Current Code To Read

- `backend/app/routers/tasks.py`
- `backend/app/services/safety_review_agent.py`
- `backend/app/services/browser_executor.py`
- `backend/app/services/agent_coordinator.py`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `frontend/src/pages/TaskDetail.jsx`
- `frontend/src/pages/ReviewMapping.jsx`
- `frontend/src/api.js`

## Scope

Add:

- policy decision service
- approval request table
- API to list/approve/reject requests
- integration with mapping confirmation and final submission
- frontend approval center card/page

## Out Of Scope

- Do not implement planner.
- Do not implement arbitrary tool approval yet.
- Do not add authentication.
- Do not replace existing form review page.
- Do not allow approval to bypass blocked policies.

## Policy Decisions

Add constants to `backend/app/workflow_constants.py`:

```python
POLICY_DECISION_ALLOW = "ALLOW"
POLICY_DECISION_REVIEW_REQUIRED = "REVIEW_REQUIRED"
POLICY_DECISION_BLOCK = "BLOCK"

RISK_LEVEL_LOW = "LOW"
RISK_LEVEL_MEDIUM = "MEDIUM"
RISK_LEVEL_HIGH = "HIGH"

APPROVAL_STATUS_PENDING = "PENDING"
APPROVAL_STATUS_APPROVED = "APPROVED"
APPROVAL_STATUS_REJECTED = "REJECTED"
APPROVAL_STATUS_EXPIRED = "EXPIRED"
```

## Risk Types

Add:

```python
RISK_TYPE_SUBMIT_ACTION = "SUBMIT_ACTION"
RISK_TYPE_PASSWORD_FIELD = "PASSWORD_FIELD"
RISK_TYPE_OTP_FIELD = "OTP_FIELD"
RISK_TYPE_PAYMENT_FIELD = "PAYMENT_FIELD"
RISK_TYPE_DESTRUCTIVE_ACTION = "DESTRUCTIVE_ACTION"
RISK_TYPE_LOW_CONFIDENCE_MAPPING = "LOW_CONFIDENCE_MAPPING"
RISK_TYPE_EXTERNAL_NAVIGATION = "EXTERNAL_NAVIGATION"
RISK_TYPE_MEMORY_WRITE = "MEMORY_WRITE"
RISK_TYPE_TERMS_CONSENT = "TERMS_CONSENT"
```

## Data Model

Add `ApprovalRequest` in `backend/app/models.py`:

```python
class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    step_name: Mapped[str] = mapped_column(String(150), nullable=False)
    risk_type: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_action_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
```

Add safe property:

```python
proposed_action: dict[str, object]
```

## Policy Engine

Create `backend/app/services/policy_engine.py`.

Required dataclass:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    risk_type: str
    risk_level: str
    reason: str
```

Required functions:

```python
def evaluate_field_action(*, label: str | None, name: str | None, field_type: str | None, selector: str | None, confidence: float | None = None) -> PolicyDecision:
    ...

def evaluate_submit_action() -> PolicyDecision:
    ...

def evaluate_memory_write(*, profile_key: str, value: str, field_label: str | None) -> PolicyDecision:
    ...

def evaluate_navigation(*, source_url: str, target_url: str) -> PolicyDecision:
    ...
```

Rules:

- submit action -> `REVIEW_REQUIRED`, risk `SUBMIT_ACTION`, level `HIGH`
- password/OTP/payment/card/billing -> `BLOCK`, level `HIGH`
- delete/purchase/destructive -> `BLOCK`, level `HIGH`
- terms/privacy/consent -> `REVIEW_REQUIRED`, level `MEDIUM`
- confidence below `0.75` -> `REVIEW_REQUIRED`, level `MEDIUM`
- normal field -> `ALLOW`, level `LOW`
- memory write to sensitive token -> `BLOCK`

Sensitive token matching should use case-insensitive text from label/name/type/selector.

## Approval Gate Service

Create `backend/app/services/approval_gate_service.py`.

Required functions:

```python
def create_approval_request(
    db: Session,
    *,
    task_id: int,
    step_name: str,
    policy_decision: PolicyDecision,
    proposed_action: dict[str, object],
) -> ApprovalRequest:
    ...

def list_pending_approvals(db: Session, task_id: int | None = None) -> list[ApprovalRequest]:
    ...

def approve_request(db: Session, approval_id: int, *, resolved_by: str = "local_user") -> ApprovalRequest:
    ...

def reject_request(db: Session, approval_id: int, *, resolved_by: str = "local_user") -> ApprovalRequest:
    ...

def has_pending_approval(db: Session, *, task_id: int, step_name: str) -> bool:
    ...

def latest_approved_request(db: Session, *, task_id: int, step_name: str) -> ApprovalRequest | None:
    ...
```

Approval requests must also write workflow spans when Phase 02 exists. If Phase 02 is not implemented yet, skip span writing but keep service tests.

## API Contract

Create `backend/app/routers/approvals.py`.

### GET `/approvals`

Optional query:

```text
?task_id=42&status=PENDING
```

Response:

```json
[
  {
    "id": 1,
    "task_id": 42,
    "step_name": "submit_form",
    "risk_type": "SUBMIT_ACTION",
    "risk_level": "HIGH",
    "decision": "REVIEW_REQUIRED",
    "reason": "Final submission always requires approval.",
    "proposed_action": {"action": "submit_form"},
    "status": "PENDING",
    "resolved_by": null,
    "created_at": "...",
    "resolved_at": null
  }
]
```

### POST `/approvals/{approval_id}/approve`

Marks a pending request approved.

### POST `/approvals/{approval_id}/reject`

Marks a pending request rejected.

Register router in `backend/app/main.py`.

## Integration Points

### Confirm Mapping

When confirming mapping:

- evaluate each memory write with `evaluate_memory_write()`.
- if BLOCK: skip profile write and include skip reason `force_save_blocked` or new `policy_blocked`.
- if REVIEW_REQUIRED for memory write: create approval request and skip write until approved.

Keep existing behavior for one-time/sensitive fields, but route new decisions through policy service.

### Fill Form

Before filling each field:

- evaluate field action.
- BLOCK: do not fill field.
- REVIEW_REQUIRED: if there is no latest approved request for that field/step, create approval request and do not fill field.
- ALLOW: fill.

The first implementation can enforce this only at confirm/fill boundaries. Do not make browser executor call the policy engine directly unless it remains simple.

### Confirm Submit

Before final submission:

1. call `evaluate_submit_action()`.
2. if no approved request exists for `submit_form`, create approval request and return HTTP `409`.
3. response detail:

```json
{
  "detail": "Final submission requires approval",
  "approval_id": 123
}
```

4. after approval, `confirm-submit` may submit.

This replaces implicit button confirmation with a persisted approval object.

## Schema

Add `ApprovalRequestResponse`:

```python
class ApprovalRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    step_name: str
    risk_type: str
    risk_level: str
    decision: str
    reason: str
    proposed_action: dict[str, object] = Field(default_factory=dict)
    status: str
    resolved_by: str | None
    created_at: datetime
    resolved_at: datetime | None
```

## Frontend API

Update `frontend/src/api.js`:

```js
listApprovals: (params = {}) => ...
approveRequest: (approvalId) => request(`/approvals/${approvalId}/approve`, { method: "POST" })
rejectRequest: (approvalId) => request(`/approvals/${approvalId}/reject`, { method: "POST" })
```

## Frontend UI

### Task Detail

Add `Approval Requests` card:

- show pending approvals for current task
- show risk level
- show reason
- approve/reject buttons

### Approval Center Page

Add route:

```text
/approvals
```

Page:

- list all pending approvals
- group by task
- approve/reject
- link to task

Keep styling consistent with existing cards.

## Tests Required

### Backend

Create `backend/tests/test_policy_engine.py`:

- submit requires review.
- password blocks.
- OTP blocks.
- payment blocks.
- terms requires review.
- low confidence requires review.
- normal text field allows.
- sensitive memory write blocks.

Create `backend/tests/test_approval_gate_service.py`:

- create approval request serializes proposed action.
- approve pending request.
- reject pending request.
- approving already resolved request raises or returns stable error.

Create `backend/tests/test_approval_endpoint.py`:

- list approvals.
- approve request.
- reject request.
- missing approval returns 404.

Update `backend/tests/test_confirm_submit.py`:

- first confirm submit creates pending approval and returns 409.
- after approving request, confirm submit succeeds.

### Frontend

Create `frontend/src/approvalPresentation.test.js` if helper logic is added:

- risk labels.
- approval sorting.
- status labels.

## Acceptance Criteria

- Policy engine is deterministic and tested.
- Approval requests are persisted.
- Final submit is impossible without approved request.
- Password/OTP/payment actions are blocked.
- Frontend can approve/reject pending requests.
- Existing review mapping flow still works.

## Implementation Order

1. Add constants.
2. Add `ApprovalRequest` model and migration helper.
3. Add schema.
4. Add policy engine service and tests.
5. Add approval gate service and tests.
6. Add approvals router and tests.
7. Register router.
8. Integrate final submit approval.
9. Integrate field/memory policy checks conservatively.
10. Add frontend API and UI.
11. Run tests.

## Trae Prompt

Implement Phase 03. Add a deterministic policy engine, persisted approval requests, approval APIs, final submission approval enforcement, conservative field/memory policy integration, and frontend approval UI. Do not implement planner or arbitrary tool approval yet. Preserve existing human review mapping behavior and existing safety boundaries.
