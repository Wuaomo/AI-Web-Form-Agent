"""Tests for the primary AgentRun read API boundary."""

import json
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Profile, Task
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
