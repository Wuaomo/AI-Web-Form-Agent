"""Tests for the primary AgentRun read API boundary."""

import json
from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import (
    AgentProposal,
    AgentReviewDecision,
    AgentRun,
    AgentToolCall,
    AgentToolResult,
    FormField,
    Job,
    Profile,
    Task,
)
from app import config
from app.job_constants import JOB_TYPE_FILL_FORM
from app.services.agent_runtime.tool_runtime import AgentTool, ToolExecutionContext, ToolRuntime


def build_environment() -> tuple[TestClient, Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), session


def create_task(session: Session) -> Task:
    profile = Profile(profile_name="Agent run test", email="ada@example.com")
    session.add(profile)
    session.flush()
    task = Task(
        url="https://example.com/form",
        profile_id=profile.id,
        workflow_type="form_fill",
        status="READY",
        workflow_status="READY",
    )
    session.add(task)
    session.commit()
    return task


def make_runtime_tool(name: str, output: dict[str, object]) -> AgentTool:
    async def handler(
        _context: ToolExecutionContext,
        _tool_input: dict[str, object],
    ) -> dict[str, object]:
        return output

    return AgentTool(
        name=name,
        description=f"{name} test tool",
        input_schema={"type": "object", "properties": {}},
        output_schema={},
        risk_level="low",
        mutates_browser=False,
        mutates_external_system=False,
        trace_phase="test",
        handler=handler,
    )


def test_get_agent_run_returns_compact_persisted_state() -> None:
    client, session = build_environment()
    task = create_task(session)
    runtime = ToolRuntime(
        [
            make_runtime_tool(
                "extract_form",
                {
                    "fields": [],
                    "field_count": 0,
                    "raw_output_json": "do not expose me",
                },
            ),
            make_runtime_tool(
                "map_fields",
                {"fields": [], "field_count": 0, "mapped_count": 0},
            ),
        ]
    )

    try:
        with patch("app.routers.workflows.build_default_tool_runtime", return_value=runtime):
            start_response = client.post(
                f"/workflows/{task.id}/governed/start?planner_mode=deterministic"
            )
        assert start_response.status_code == 200

        response = client.get(f"/agent-runs/task-{task.id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["run_id"] == f"task-{task.id}"
        assert payload["task_id"] == task.id
        assert payload["workflow_type"] == "form_fill"
        assert payload["planner_mode"] == "deterministic"
        assert payload["status"] == "COMPLETED"
        assert payload["tool_result_count"] == 2
        assert "raw_output_json" not in json.dumps(payload)
        assert "output_json" not in json.dumps(payload)
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_get_agent_run_returns_404_for_missing_run() -> None:
    client, session = build_environment()

    try:
        response = client.get("/agent-runs/missing-run")

        assert response.status_code == 404
        assert response.json()["detail"] == "No agent run state found for missing-run."
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_continue_agent_run_delegates_reviewed_fill_to_shared_task_path() -> None:
    client, session = build_environment()
    task = create_task(session)
    task.status = "READY_TO_FILL"
    task.workflow_status = "READY_TO_FILL"
    field = FormField(
        task_id=task.id,
        label="Email",
        selector="#email",
        field_type="email",
        mapped_profile_key="email",
        mapped_value="ada@example.com",
        confidence=0.99,
        required=True,
    )
    run = AgentRun(
        id=f"task-{task.id}",
        legacy_task_id=task.id,
        goal="Fill reviewed fields.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="READY_TO_FILL",
        mode="deterministic",
    )
    run.final_result = {}
    session.add_all([field, run])
    session.commit()

    try:
        with patch(
            "app.routers.tasks.fill_form_and_capture_screenshot",
            new_callable=AsyncMock,
        ) as browser_fill:
            browser_fill.return_value = (SimpleNamespace(id=7), [])
            response = client.post(f"/agent-runs/task-{task.id}/continue")

        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == task.id
        assert payload["status"] == "WAITING_APPROVAL"
        browser_fill.assert_awaited_once()
        call = session.get(AgentToolCall, f"task-{task.id}:fill_form")
        assert call is not None
        assert call.governance_decision["decision"] == "VERIFY_REQUIRED"
        result = session.get(AgentToolResult, f"task-{task.id}:fill_form")
        assert result is not None
        assert result.output_json == {
            "filled_count": 1,
            "screenshot_id": 7,
            "verification_count": 0,
        }
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_continue_agent_run_enqueues_async_fill_with_run_id() -> None:
    client, session = build_environment()
    task = create_task(session)
    task.status = "READY_TO_FILL"
    task.workflow_status = "READY_TO_FILL"
    field = FormField(
        task_id=task.id,
        label="Email",
        selector="#email",
        field_type="email",
        mapped_profile_key="email",
        mapped_value="ada@example.com",
        confidence=0.99,
        required=True,
    )
    run = AgentRun(
        id=f"task-{task.id}",
        legacy_task_id=task.id,
        goal="Fill reviewed fields.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="READY_TO_FILL",
        mode="deterministic",
    )
    run.final_result = {}
    session.add_all([field, run])
    session.commit()
    original_async = config.ASYNC_JOBS_ENABLED
    config.ASYNC_JOBS_ENABLED = True

    try:
        response = client.post(f"/agent-runs/task-{task.id}/continue")

        assert response.status_code == 200
        payload = response.json()
        assert payload["job_type"] == JOB_TYPE_FILL_FORM
        job = session.get(Job, payload["id"])
        assert job is not None
        assert job.payload == {"agent_run_id": f"task-{task.id}"}
    finally:
        config.ASYNC_JOBS_ENABLED = original_async
        app.dependency_overrides.clear()
        session.close()


def test_continue_agent_run_delegates_submit_to_shared_task_path() -> None:
    client, session = build_environment()
    task = create_task(session)
    task.status = "WAITING_APPROVAL"
    task.workflow_status = "WAITING_APPROVAL"
    field = FormField(
        task_id=task.id,
        label="Email",
        selector="#email",
        field_type="email",
        mapped_profile_key="email",
        mapped_value="ada@example.com",
        confidence=0.99,
        required=True,
    )
    run = AgentRun(
        id=f"task-{task.id}",
        legacy_task_id=task.id,
        goal="Submit reviewed form.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_APPROVAL",
        mode="deterministic",
    )
    run.final_result = {}
    session.add_all([field, run])
    session.commit()

    try:
        with patch(
            "app.routers.tasks.submit_form_and_capture_screenshot",
            new_callable=AsyncMock,
        ) as submit_form:
            first_response = client.post(
                f"/agent-runs/task-{task.id}/continue",
                json={"action": "submit_form"},
            )

        assert first_response.status_code == 409
        assert first_response.json()["detail"]["message"] == "Final submission requires approval"
        submit_form.assert_not_awaited()

        approval_id = first_response.json()["detail"]["approval_id"]
        approve_response = client.post(f"/approvals/{approval_id}/approve")
        assert approve_response.status_code == 200

        with patch(
            "app.routers.tasks.submit_form_and_capture_screenshot",
            new_callable=AsyncMock,
        ) as submit_form:
            submit_form.return_value = SimpleNamespace(id=8)
            response = client.post(
                f"/agent-runs/task-{task.id}/continue",
                json={"action": "submit_form"},
            )

        assert response.status_code == 200
        assert response.json() == {
            "task_id": task.id,
            "status": "COMPLETED",
            "approval_id": approval_id,
        }
        submit_form.assert_awaited_once()
        call = session.get(AgentToolCall, f"task-{task.id}:submit_form")
        assert call is not None
        assert call.governance_decision["decision"] == "VERIFY_REQUIRED"
        result = session.get(AgentToolResult, f"task-{task.id}:submit_form")
        assert result is not None
        assert result.output_json == {
            "submitted": True,
            "field_count": 1,
            "screenshot_id": 8,
        }
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_continue_agent_run_returns_404_for_missing_run() -> None:
    client, session = build_environment()

    try:
        response = client.post("/agent-runs/missing-run/continue")

        assert response.status_code == 404
        assert response.json()["detail"] == "No agent run state found for missing-run."
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_get_agent_run_review_items_prefers_persisted_proposals() -> None:
    client, session = build_environment()
    task = create_task(session)
    field = FormField(
        task_id=task.id,
        label="Email",
        selector="#email",
        field_type="email",
        mapped_profile_key="email",
        mapped_value="legacy@example.com",
        confidence=0.99,
    )
    run = AgentRun(
        id=f"task-{task.id}",
        legacy_task_id=task.id,
        goal="Review proposal-backed queue.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=f"task-{task.id}-field-999",
        run=run,
        proposal_type="field_value",
        target_type="form_field",
        target_ref="999",
        proposed_value="proposal@example.com",
        rationale="Persisted proposal wins.",
        confidence=0.42,
        risk_level="medium",
        status="PENDING",
    )
    session.add_all([field, run, proposal])
    session.commit()

    try:
        response = client.get(f"/agent-runs/task-{task.id}/review-items")

        assert response.status_code == 200
        payload = response.json()
        assert [item["id"] for item in payload] == [
            proposal.id,
            f"task-{task.id}-field-{field.id}",
            f"task-{task.id}-field-{field.id}-memory-mapping",
        ]
        assert payload[0]["proposed_value"] == "proposal@example.com"
        assert payload[1]["proposed_value"] == "legacy@example.com"
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_get_agent_run_review_items_strips_nested_raw_tool_payloads() -> None:
    client, session = build_environment()
    task = create_task(session)
    run = AgentRun(
        id=f"task-{task.id}",
        legacy_task_id=task.id,
        goal="Review compact action proposal.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=f"task-{task.id}-browser-action",
        run=run,
        proposal_type="browser_click",
        target_type="browser_action",
        target_ref="#continue",
        proposed_value={
            "action": "click",
            "selector": "#continue",
            "payload": {
                "tool_results": [{"output_json": {"raw_output_json": "do not expose"}}],
            },
        },
        rationale="Compact browser action.",
        confidence=None,
        risk_level="medium",
        status="PENDING",
    )
    session.add_all([run, proposal])
    session.commit()

    try:
        response = client.get(f"/agent-runs/task-{task.id}/review-items")

        assert response.status_code == 200
        payload = response.json()
        assert payload[0]["proposed_value"] == {
            "action": "click",
            "selector": "#continue",
            "payload": {},
        }
        serialized = json.dumps(payload)
        assert "tool_results" not in serialized
        assert "output_json" not in serialized
        assert "raw_output_json" not in serialized
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_agent_run_review_item_decision_persists_decision_and_syncs_field() -> None:
    client, session = build_environment()
    task = create_task(session)
    field = FormField(
        task_id=task.id,
        label="Email",
        selector="#email",
        field_type="email",
        mapped_profile_key="email",
        mapped_value="legacy@example.com",
        confidence=0.5,
    )
    run = AgentRun(
        id=f"task-{task.id}",
        legacy_task_id=task.id,
        goal="Review proposal-backed queue.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
        pending_review_count=1,
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=f"task-{task.id}-field-primary",
        run=run,
        proposal_type="field_value",
        target_type="form_field",
        target_ref="1",
        proposed_value="proposal@example.com",
        rationale="Persisted proposal wins.",
        confidence=0.42,
        risk_level="medium",
        status="PENDING",
    )
    session.add_all([field, run, proposal])
    session.flush()
    proposal.target_ref = str(field.id)
    session.commit()

    try:
        response = client.post(
            f"/agent-runs/task-{task.id}/review-items/{proposal.id}/decision",
            json={"decision": "approved", "reviewer_note": "looks right"},
        )

        assert response.status_code == 200
        assert response.json()["proposal_id"] == proposal.id
        decision = session.get(AgentReviewDecision, f"decision-{proposal.id}")
        assert decision is not None
        assert decision.decision == "approved"
        assert decision.reviewer_note == "looks right"
        session.refresh(proposal)
        session.refresh(field)
        session.refresh(run)
        assert proposal.status == "APPROVED"
        assert field.mapped_value == "proposal@example.com"
        assert field.confidence == 1.0
        assert run.pending_review_count == 0
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_agent_run_review_item_decision_keeps_non_field_proposals_runtime_only() -> None:
    client, session = build_environment()
    task = create_task(session)
    field = FormField(
        task_id=task.id,
        label="Email",
        selector="#email",
        field_type="email",
        mapped_profile_key="email",
        mapped_value="legacy@example.com",
        confidence=0.5,
    )
    run = AgentRun(
        id=f"task-{task.id}",
        legacy_task_id=task.id,
        goal="Review memory proposal.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
        pending_review_count=1,
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=f"task-{task.id}-memory-write",
        run=run,
        proposal_type="memory_write",
        target_type="workflow_memory",
        target_ref=str(field.id),
        proposed_value="email",
        rationale="Save reusable mapping.",
        confidence=0.5,
        risk_level="medium",
        status="PENDING",
    )
    session.add_all([field, run, proposal])
    session.commit()

    try:
        response = client.post(
            f"/agent-runs/task-{task.id}/review-items/{proposal.id}/decision",
            json={"decision": "edited", "edited_value": "contact_email"},
        )

        assert response.status_code == 200
        decision = session.get(AgentReviewDecision, f"decision-{proposal.id}")
        assert decision is not None
        assert decision.decision == "edited"
        session.refresh(proposal)
        session.refresh(field)
        session.refresh(run)
        assert proposal.status == "EDITED"
        assert proposal.proposed_value == "contact_email"
        assert field.mapped_profile_key == "email"
        assert field.mapped_value == "legacy@example.com"
        assert field.confidence == 0.5
        assert run.pending_review_count == 0
    finally:
        app.dependency_overrides.clear()
        session.close()
