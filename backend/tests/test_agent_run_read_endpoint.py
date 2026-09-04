"""Tests for the primary AgentRun read API boundary."""

import json
from collections.abc import Generator

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
    FormField,
    Profile,
    Task,
)
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

    from unittest.mock import patch

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
