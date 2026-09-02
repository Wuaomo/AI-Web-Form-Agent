"""Integration tests for the task submission confirmation endpoint."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import (
    ActionLog,
    AgentPlan,
    AgentProposal,
    AgentReviewDecision,
    AgentRun,
    AgentToolCall,
    AgentToolResult,
    AgentVerificationResult,
    ApprovalRequest,
    FormField,
    Profile,
    Task,
)
from app.routers.approvals import router as approvals_router
from app.routers.tasks import router as tasks_router
from app.services.agent_runtime.schemas import GovernanceDecision, ToolResult
from app.services.agent_runtime.governed_agent_graph import (
    _reset_governed_runtime_for_tests,
    start_governed_runtime,
)
from app.services.agent_runtime.state_store import (
    save_fill_form_runtime_state,
    save_governed_runtime_state,
)
from app.services.agent_runtime.tools import build_default_tool_runtime


@pytest.fixture
def test_environment() -> Generator[tuple[TestClient, Session], None, None]:
    """Provide an isolated API client and in-memory database session."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    test_app = FastAPI()
    test_app.include_router(tasks_router)
    test_app.include_router(approvals_router)
    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app) as client:
        yield client, session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def create_task(session: Session, task_status: str) -> Task:
    """Create a task and its required profile for an endpoint test."""

    profile = Profile(profile_name=f"{task_status} profile")
    session.add(profile)
    session.flush()

    task = Task(
        url="https://example.com/form",
        profile_id=profile.id,
        status=task_status,
    )
    session.add(task)
    session.flush()
    field = FormField(
        task_id=task.id,
        label="Email",
        selector="#email",
        field_type="email",
        required=True,
        mapped_profile_key="email",
        mapped_value="user@example.com",
        confidence=1.0,
    )
    session.add(field)
    session.commit()
    return task


def test_confirm_submit_first_request_creates_approval_and_returns_409(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session, "WAITING_APPROVAL")

    with patch(
        "app.routers.tasks.submit_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as submit_form:
        response = client.post(f"/tasks/{task.id}/confirm-submit")

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "Final submission requires approval"
    approval_id = response.json()["detail"]["approval_id"]
    submit_form.assert_not_awaited()

    approval = session.get(ApprovalRequest, approval_id)
    assert approval is not None
    assert approval.status == "PENDING"


def test_confirm_submit_first_request_persists_submit_proposal(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session, "WAITING_APPROVAL")

    response = client.post(f"/tasks/{task.id}/confirm-submit")

    assert response.status_code == 409
    approval_id = response.json()["detail"]["approval_id"]
    proposal = session.get(AgentProposal, f"task-{task.id}-submit-{approval_id}")
    assert proposal is not None
    assert proposal.run_id == f"task-{task.id}"
    assert proposal.proposal_type == "form_submit"
    assert proposal.target_type == "approval_request"
    assert proposal.target_ref == str(approval_id)
    assert proposal.risk_level == "high"
    assert proposal.status == "PENDING"
    assert proposal.proposed_value["action"] == "submit_form"
    assert session.get(AgentRun, f"task-{task.id}") is not None


def test_confirm_submit_existing_pending_approval_persists_submit_proposal(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session, "WAITING_APPROVAL")
    field = session.scalar(select(FormField).where(FormField.task_id == task.id))
    approval = ApprovalRequest(
        task_id=task.id,
        step_name="submit_form",
        risk_type="final_submit",
        risk_level="high",
        decision="REVIEW_REQUIRED",
        reason="Final submission requires explicit approval.",
        status="PENDING",
    )
    approval.proposed_action = {
        "action": "submit_form",
        "fields": [{"field_id": field.id, "mapped_value": field.mapped_value}],
    }
    session.add(approval)
    session.commit()

    response = client.post(f"/tasks/{task.id}/confirm-submit")

    assert response.status_code == 409
    assert response.json()["detail"]["approval_id"] == approval.id
    assert (
        session.get(AgentProposal, f"task-{task.id}-submit-{approval.id}")
        is not None
    )


def test_approve_submit_approval_syncs_submit_proposal(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session, "WAITING_APPROVAL")
    first_response = client.post(f"/tasks/{task.id}/confirm-submit")
    approval_id = first_response.json()["detail"]["approval_id"]
    proposal_id = f"task-{task.id}-submit-{approval_id}"

    response = client.post(f"/approvals/{approval_id}/approve")

    assert response.status_code == 200
    proposal = session.get(AgentProposal, proposal_id)
    assert proposal is not None
    assert proposal.status == "APPROVED"
    decision = session.get(AgentReviewDecision, f"decision-{proposal_id}")
    assert decision is not None
    assert decision.decision == "approved"


def test_reject_submit_approval_syncs_submit_proposal(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session, "WAITING_APPROVAL")
    first_response = client.post(f"/tasks/{task.id}/confirm-submit")
    approval_id = first_response.json()["detail"]["approval_id"]
    proposal_id = f"task-{task.id}-submit-{approval_id}"

    response = client.post(f"/approvals/{approval_id}/reject")

    assert response.status_code == 200
    proposal = session.get(AgentProposal, proposal_id)
    assert proposal is not None
    assert proposal.status == "REJECTED"
    decision = session.get(AgentReviewDecision, f"decision-{proposal_id}")
    assert decision is not None
    assert decision.decision == "rejected"


def test_confirm_submit_second_request_submits_after_approval(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session, "WAITING_APPROVAL")

    first_response = client.post(f"/tasks/{task.id}/confirm-submit")
    approval_id = first_response.json()["detail"]["approval_id"]
    approve_response = client.post(f"/approvals/{approval_id}/approve")
    assert approve_response.status_code == 200

    with patch(
        "app.routers.tasks.submit_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as submit_form:
        response = client.post(f"/tasks/{task.id}/confirm-submit")

    assert response.status_code == 200
    assert response.json() == {"task_id": task.id, "status": "COMPLETED", "approval_id": approval_id}
    submit_form.assert_awaited_once()

    session.refresh(task)
    assert task.status == "COMPLETED"

    logs = list(
        session.scalars(
            select(ActionLog)
            .where(ActionLog.task_id == task.id)
            .order_by(ActionLog.step)
        )
    )
    assert len(logs) == 2
    assert logs[0].step == 1
    assert logs[0].action == "confirm_submit"
    assert logs[0].message == "User approved final form submission."
    assert logs[0].status == "STARTED"
    assert logs[1].step == 2
    assert logs[1].action == "submit_form"
    assert logs[1].message == "Submitted the reviewed form after user approval."
    assert logs[1].status == "SUCCESS"


def test_confirm_submit_records_submit_runtime_tool_call(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session, "WAITING_APPROVAL")

    first_response = client.post(f"/tasks/{task.id}/confirm-submit")
    approval_id = first_response.json()["detail"]["approval_id"]
    approve_response = client.post(f"/approvals/{approval_id}/approve")
    assert approve_response.status_code == 200

    with patch(
        "app.routers.tasks.submit_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as submit_form:
        submit_form.return_value = type("Screenshot", (), {"id": 5})()
        response = client.post(f"/tasks/{task.id}/confirm-submit")

    assert response.status_code == 200

    call = session.get(AgentToolCall, f"task-{task.id}:submit_form")
    assert call is not None
    assert call.tool_name == "submit_form"
    assert call.status == "SUCCEEDED"
    assert call.risk_level == "high"
    assert call.governance_decision["decision"] == "VERIFY_REQUIRED"

    result = session.get(AgentToolResult, f"task-{task.id}:submit_form")
    assert result is not None
    assert result.status == "SUCCEEDED"
    assert result.output_json == {
        "submitted": True,
        "field_count": 1,
        "screenshot_id": 5,
    }

    verification = session.get(
        AgentVerificationResult,
        f"task-{task.id}:submit_form:verification:0",
    )
    assert verification is not None
    assert verification.tool_call_id == f"task-{task.id}:submit_form"
    assert verification.target_type == "form_submit"
    assert verification.target_ref == "submit_form"
    assert verification.verification_type == "page_state"
    assert verification.status == "VERIFIED"
    assert verification.actual == {"screenshot_id": 5, "submitted": True}


def test_confirm_submit_resumes_persisted_governed_submit_approval_without_plan_overwrite(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    _reset_governed_runtime_for_tests()
    task = create_task(session, "WAITING_APPROVAL")
    field = session.scalar(select(FormField).where(FormField.task_id == task.id))
    fields = [
        {
            "id": field.id,
            "selector": field.selector,
            "mapped_value": field.mapped_value,
        }
    ]

    first_response = client.post(f"/tasks/{task.id}/confirm-submit")
    approval_id = first_response.json()["detail"]["approval_id"]

    paused_state = asyncio.run(
        start_governed_runtime(
            {
                "run_id": f"task-{task.id}",
                "task_id": task.id,
                "goal": "Submit through governed graph.",
                "target_url": task.url,
                "profile_id": task.profile_id,
                "plan_steps": [
                    {
                        "step_id": "submit_form",
                        "tool_name": "submit_form",
                        "reason": "Submit reviewed form after explicit approval.",
                        "input_json": {
                            "task_id": task.id,
                            "url": task.url,
                            "profile_id": task.profile_id,
                            "fields": fields,
                        },
                        "risk_level": "high",
                    }
                ],
            },
            runtime=build_default_tool_runtime(
                submit_form_handler=AsyncMock(
                    return_value=type("Screenshot", (), {"id": 8})()
                )
            ),
        )
    )
    save_governed_runtime_state(session, task=task, raw_state=paused_state)
    approve_response = client.post(f"/approvals/{approval_id}/approve")
    assert approve_response.status_code == 200
    _reset_governed_runtime_for_tests()

    with patch(
        "app.routers.tasks.submit_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as submit_form:
        submit_form.return_value = type("Screenshot", (), {"id": 9})()
        response = client.post(f"/tasks/{task.id}/confirm-submit")

    assert response.status_code == 200
    submit_form.assert_awaited_once()
    session.expire_all()
    run = session.get(AgentRun, f"task-{task.id}")
    assert run is not None
    assert run.status == "COMPLETED"
    assert run.current_plan_id == f"task-{task.id}:plan:1"


def test_confirm_submit_skips_persisted_governed_submit_when_snapshot_differs(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    _reset_governed_runtime_for_tests()
    task = create_task(session, "WAITING_APPROVAL")
    field = session.scalar(select(FormField).where(FormField.task_id == task.id))

    first_response = client.post(f"/tasks/{task.id}/confirm-submit")
    approval_id = first_response.json()["detail"]["approval_id"]
    approve_response = client.post(f"/approvals/{approval_id}/approve")
    assert approve_response.status_code == 200

    stale_fields = [
        {
            "id": field.id,
            "selector": field.selector,
            "mapped_value": "stale@example.com",
        }
    ]
    save_governed_runtime_state(
        session,
        task=task,
        raw_state={
            "run_id": f"task-{task.id}",
            "task_id": task.id,
            "workflow_type": task.workflow_type,
            "planner_mode": "deterministic",
            "interrupt_at": "approval",
            "run": {
                "id": f"task-{task.id}",
                "goal": "Submit through governed graph.",
                "target_url": task.url,
                "profile_id": task.profile_id,
                "status": "WAITING_APPROVAL",
                "mode": "deterministic",
            },
            "plan": {
                "id": f"task-{task.id}:plan:1",
                "version": 1,
                "goal": "Submit through governed graph.",
                "steps": [
                    {
                        "step_id": "submit_form",
                        "tool_name": "submit_form",
                        "reason": "Submit reviewed form after explicit approval.",
                        "input_json": {
                            "task_id": task.id,
                            "url": task.url,
                            "profile_id": task.profile_id,
                            "fields": stale_fields,
                        },
                        "risk_level": "high",
                    }
                ],
                "created_by": "deterministic",
            },
            "current_tool_call": {
                "id": f"task-{task.id}:submit_form",
                "run_id": f"task-{task.id}",
                "plan_step_id": "submit_form",
                "tool_name": "submit_form",
                "input_json": {
                    "task_id": task.id,
                    "url": task.url,
                    "profile_id": task.profile_id,
                    "fields": stale_fields,
                },
                "status": "WAITING_APPROVAL",
                "risk_level": "high",
                "governance_decision": {"decision": "APPROVAL_REQUIRED"},
            },
        },
    )
    _reset_governed_runtime_for_tests()

    with patch(
        "app.routers.tasks.submit_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as submit_form:
        submit_form.return_value = type("Screenshot", (), {"id": 9})()
        response = client.post(f"/tasks/{task.id}/confirm-submit")

    assert response.status_code == 200
    submitted_fields = submit_form.await_args.kwargs["fields"]
    assert submitted_fields[0].mapped_value == "user@example.com"


def test_confirm_submit_skips_persisted_governed_submit_when_selector_differs(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    _reset_governed_runtime_for_tests()
    task = create_task(session, "WAITING_APPROVAL")
    field = session.scalar(select(FormField).where(FormField.task_id == task.id))

    first_response = client.post(f"/tasks/{task.id}/confirm-submit")
    approval_id = first_response.json()["detail"]["approval_id"]
    approve_response = client.post(f"/approvals/{approval_id}/approve")
    assert approve_response.status_code == 200

    stale_fields = [
        {
            "id": field.id,
            "selector": "#stale-email",
            "mapped_value": field.mapped_value,
        }
    ]
    field.selector = "#email"
    session.commit()
    save_governed_runtime_state(
        session,
        task=task,
        raw_state={
            "run_id": f"task-{task.id}",
            "task_id": task.id,
            "workflow_type": task.workflow_type,
            "planner_mode": "deterministic",
            "interrupt_at": "approval",
            "run": {
                "id": f"task-{task.id}",
                "goal": "Submit through governed graph.",
                "target_url": task.url,
                "profile_id": task.profile_id,
                "status": "WAITING_APPROVAL",
                "mode": "deterministic",
            },
            "plan": {
                "id": f"task-{task.id}:plan:1",
                "version": 1,
                "goal": "Submit through governed graph.",
                "steps": [
                    {
                        "step_id": "submit_form",
                        "tool_name": "submit_form",
                        "reason": "Submit reviewed form after explicit approval.",
                        "input_json": {
                            "task_id": task.id,
                            "url": task.url,
                            "profile_id": task.profile_id,
                            "fields": stale_fields,
                        },
                        "risk_level": "high",
                    }
                ],
                "created_by": "deterministic",
            },
            "current_tool_call": {
                "id": f"task-{task.id}:submit_form",
                "run_id": f"task-{task.id}",
                "plan_step_id": "submit_form",
                "tool_name": "submit_form",
                "input_json": {
                    "task_id": task.id,
                    "url": task.url,
                    "profile_id": task.profile_id,
                    "fields": stale_fields,
                },
                "status": "WAITING_APPROVAL",
                "risk_level": "high",
                "governance_decision": {"decision": "APPROVAL_REQUIRED"},
            },
        },
    )
    _reset_governed_runtime_for_tests()

    with patch(
        "app.routers.tasks.submit_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as submit_form:
        submit_form.return_value = type("Screenshot", (), {"id": 9})()
        response = client.post(f"/tasks/{task.id}/confirm-submit")

    assert response.status_code == 200
    submitted_fields = submit_form.await_args.kwargs["fields"]
    assert submitted_fields[0].selector == "#email"


def test_confirm_submit_keeps_fill_and_submit_runtime_plan_steps(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session, "WAITING_APPROVAL")
    save_fill_form_runtime_state(
        session,
        task=task,
        tool_result=ToolResult(
            tool_call_id=f"task-{task.id}:fill_form",
            status="SUCCEEDED",
            governance_decision=GovernanceDecision(
                decision="VERIFY_REQUIRED",
                reason="Approved browser write requires verification after execution.",
                risk_level="medium",
            ),
            output_json={
                "filled_count": 1,
                "screenshot_id": 4,
                "verification_count": 0,
            },
        ),
    )

    first_response = client.post(f"/tasks/{task.id}/confirm-submit")
    approval_id = first_response.json()["detail"]["approval_id"]
    approve_response = client.post(f"/approvals/{approval_id}/approve")
    assert approve_response.status_code == 200

    with patch(
        "app.routers.tasks.submit_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as submit_form:
        submit_form.return_value = type("Screenshot", (), {"id": 5})()
        response = client.post(f"/tasks/{task.id}/confirm-submit")

    assert response.status_code == 200
    plan = session.get(AgentPlan, f"task-{task.id}:browser-write-plan:1")
    assert plan is not None
    assert [step["step_id"] for step in plan.steps] == ["fill_form", "submit_form"]


def test_confirm_submit_rejects_task_not_waiting_for_approval(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session, "CREATED")

    with patch(
        "app.routers.tasks.submit_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as submit_form:
        response = client.post(f"/tasks/{task.id}/confirm-submit")

    assert response.status_code == 409
    assert response.json() == {"detail": "Task is not waiting for approval"}
    submit_form.assert_not_awaited()

    session.refresh(task)
    assert task.status == "CREATED"
    assert session.scalar(
        select(ActionLog).where(ActionLog.task_id == task.id)
    ) is None


def test_confirm_submit_rejected_approval_blocks_submission(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task(session, "WAITING_APPROVAL")

    first_response = client.post(f"/tasks/{task.id}/confirm-submit")
    approval_id = first_response.json()["detail"]["approval_id"]
    approval = session.get(ApprovalRequest, approval_id)
    approval.status = "REJECTED"
    session.commit()

    with patch(
        "app.routers.tasks.submit_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as submit_form:
        response = client.post(f"/tasks/{task.id}/confirm-submit")

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "Final submission approval was rejected"
    assert response.json()["detail"]["approval_id"] == approval_id
    submit_form.assert_not_awaited()


def test_confirm_submit_requires_new_approval_after_field_snapshot_changes(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify an approved submit gate becomes stale after mapped values change."""

    client, session = test_environment
    task = create_task(session, "WAITING_APPROVAL")

    first_response = client.post(f"/tasks/{task.id}/confirm-submit")
    first_approval_id = first_response.json()["detail"]["approval_id"]
    approve_response = client.post(f"/approvals/{first_approval_id}/approve")
    assert approve_response.status_code == 200

    field = session.scalar(select(FormField).where(FormField.task_id == task.id))
    field.mapped_value = "updated@example.com"
    session.commit()

    with patch(
        "app.routers.tasks.submit_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as submit_form:
        response = client.post(f"/tasks/{task.id}/confirm-submit")

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "Final submission requires approval"
    assert response.json()["detail"]["approval_id"] != first_approval_id
    submit_form.assert_not_awaited()
