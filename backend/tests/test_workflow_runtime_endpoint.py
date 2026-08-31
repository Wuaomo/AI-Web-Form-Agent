"""Tests for workflow runtime API (start/get/review)."""

import json
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import (
    AgentProposal,
    AgentReviewDecision,
    AgentRun,
    AgentVerificationResult,
    FormField,
    Profile,
    Task,
    WorkflowMemoryItem,
)
from app.routers.workflows import router as workflows_router
from app.services.agent_runtime.security_questionnaire_graph import (
    _reset_runtime_for_tests,
)
from app.services.agent_runtime.governed_agent_graph import (
    _reset_governed_runtime_for_tests,
)
from app.services.agent_runtime.tool_runtime import AgentTool, ToolExecutionContext, ToolRuntime
from app.services.agent_runtime.state_store import save_governed_runtime_state


def _clear_runtime_state() -> None:
    """Clear all in-memory graph state between tests."""

    _reset_runtime_for_tests()
    _reset_governed_runtime_for_tests()


def build_environment() -> tuple[TestClient, Session]:
    """Build an isolated API environment for workflow runtime tests."""

    _clear_runtime_state()

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    app = FastAPI()
    app.include_router(workflows_router)
    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app), session


def create_profile(session: Session) -> Profile:
    profile = Profile(
        profile_name="Runtime test profile",
        full_name="Ada Lovelace",
        email="ada@example.com",
    )
    session.add(profile)
    session.commit()
    return profile


def create_security_questionnaire_task(
    session: Session, profile: Profile
) -> Task:
    task = Task(
        url="https://example.com/security-questionnaire",
        profile_id=profile.id,
        workflow_type="security_questionnaire",
        status="READY",
        workflow_status="READY",
    )
    session.add(task)
    session.flush()

    field1 = FormField(
        task_id=task.id,
        label="What is your employee ID?",
        name="employee_id",
        field_type="text",
        selector="#employee_id",
    )
    field2 = FormField(
        task_id=task.id,
        label="What department do you work in?",
        name="department",
        field_type="text",
        selector="#department",
    )
    session.add_all([field1, field2])
    session.commit()
    session.refresh(task)
    return task


def create_form_fill_task(session: Session, profile: Profile) -> Task:
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


def create_governed_proposal(
    session: Session,
    task: Task,
    *,
    proposal_id: str,
    proposal_type: str = "field_value",
    target_type: str = "form_field",
    target_ref: str = "1",
    proposed_value: str = "old@example.com",
) -> AgentProposal:
    run = AgentRun(
        id=f"task-{task.id}",
        legacy_task_id=task.id,
        goal="Review governed proposal.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=proposal_id,
        run=run,
        proposal_type=proposal_type,
        target_type=target_type,
        target_ref=target_ref,
        proposed_value=proposed_value,
        rationale="Review governed proposal.",
        confidence=0.8,
        risk_level="medium",
        status="PENDING",
    )
    session.add_all([run, proposal])
    session.commit()
    return proposal


def add_pending_sibling_proposal(
    session: Session,
    proposal: AgentProposal,
    *,
    proposal_id: str,
) -> None:
    proposal.run.pending_review_count = 2
    session.add(
        AgentProposal(
            id=proposal_id,
            run_id=proposal.run_id,
            proposal_type="field_value",
            target_type="form_field",
            target_ref="1",
            proposed_value="other@example.com",
            rationale="Still pending.",
            confidence=0.8,
            risk_level="medium",
            status="PENDING",
        )
    )
    session.commit()


async def noop_handler(
    _context: ToolExecutionContext,
    _tool_input: dict[str, object],
) -> dict[str, object]:
    return {}


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


# ---------------------------------------------------------------------------
# Start endpoint tests
# ---------------------------------------------------------------------------


def test_start_endpoint_runs_to_review_interrupt() -> None:
    """POST /workflows/{task_id}/start returns state paused at review."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_security_questionnaire_task(session, profile)

    response = client.post(f"/workflows/{task.id}/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == task.id
    assert payload["workflow_type"] == "security_questionnaire"
    assert payload["interrupt_at"] == "review"
    assert payload["current_node"] == "apply_review_decision"
    assert len(payload["suggestions"]) > 0
    assert "policy_result" in payload
    session.close()


def test_start_endpoint_rejects_unsupported_workflow() -> None:
    """POST /workflows/{task_id}/start returns 400 for form_fill."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)

    response = client.post(f"/workflows/{task.id}/start")

    assert response.status_code == 400
    assert "security_questionnaire" in response.json()["detail"]
    session.close()


def test_start_endpoint_returns_404_for_missing_task() -> None:
    """POST /workflows/{task_id}/start returns 404 if task doesn't exist."""

    client, session = build_environment()

    response = client.post("/workflows/9999/start")

    assert response.status_code == 404
    session.close()


def test_governed_start_accepts_template_guided_planner_mode() -> None:
    """POST /workflows/{task_id}/governed/start selects the generic planner mode."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    runtime = ToolRuntime(
        [
            make_runtime_tool(
                "extract_form",
                {"fields": [], "field_count": 0, "login_required": False},
            ),
            make_runtime_tool(
                "map_fields",
                {"fields": [], "field_count": 0, "mapped_count": 0},
            ),
        ]
    )

    from unittest.mock import patch

    with patch("app.routers.workflows.build_default_tool_runtime", return_value=runtime):
        response = client.post(
            f"/workflows/{task.id}/governed/start?planner_mode=template_guided"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == task.id
    assert payload["workflow_type"] == "form_fill"
    assert payload["planner_mode"] == "template_guided"
    assert payload["plan"]["created_by"] == "template"
    assert payload["status"] == "COMPLETED"
    session.close()


def test_governed_start_keeps_deterministic_mode_without_openai_key() -> None:
    """POST /workflows/{task_id}/governed/start keeps no-key deterministic mode."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    runtime = ToolRuntime(
        [
            make_runtime_tool(
                "extract_form",
                {"fields": [], "field_count": 0, "login_required": False},
            ),
            make_runtime_tool(
                "map_fields",
                {"fields": [], "field_count": 0, "mapped_count": 0},
            ),
        ]
    )

    from unittest.mock import patch

    with patch("app.routers.workflows.config.OPENAI_API_KEY", None), patch(
        "app.routers.workflows.build_default_tool_runtime",
        return_value=runtime,
    ):
        response = client.post(
            f"/workflows/{task.id}/governed/start?planner_mode=deterministic"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["planner_mode"] == "deterministic"
    assert payload["plan"]["created_by"] == "deterministic"
    assert payload["status"] == "COMPLETED"
    session.close()


def test_governed_start_persists_agent_run_and_plan() -> None:
    """POST /governed/start double-writes the compact AgentRun and AgentPlan."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    runtime = ToolRuntime(
        [
            make_runtime_tool(
                "extract_form",
                {"fields": [], "field_count": 0, "login_required": False},
            ),
            make_runtime_tool(
                "map_fields",
                {"fields": [], "field_count": 0, "mapped_count": 0},
            ),
        ]
    )

    from unittest.mock import patch

    with patch("app.routers.workflows.build_default_tool_runtime", return_value=runtime):
        response = client.post(
            f"/workflows/{task.id}/governed/start?planner_mode=deterministic"
        )

    assert response.status_code == 200

    run_row = session.execute(
        text(
            """
            SELECT id, legacy_task_id, goal, target_url, profile_id,
                   workflow_hint, status, mode, current_plan_id
            FROM agent_runs
            WHERE legacy_task_id = :task_id
            """
        ),
        {"task_id": task.id},
    ).mappings().one()
    assert run_row["id"] == f"task-{task.id}"
    assert run_row["legacy_task_id"] == task.id
    assert run_row["goal"] == "Complete the requested browser workflow."
    assert run_row["target_url"] == task.url
    assert run_row["profile_id"] == profile.id
    assert run_row["workflow_hint"] == "form_fill"
    assert run_row["status"] == "COMPLETED"
    assert run_row["mode"] == "deterministic"
    assert run_row["current_plan_id"] == f"task-{task.id}:plan:1"

    plan_row = session.execute(
        text(
            """
            SELECT id, run_id, version, goal, steps_json, created_by
            FROM agent_plans
            WHERE run_id = :run_id
            """
        ),
        {"run_id": f"task-{task.id}"},
    ).mappings().one()
    assert plan_row["id"] == f"task-{task.id}:plan:1"
    assert plan_row["run_id"] == f"task-{task.id}"
    assert plan_row["version"] == 1
    assert plan_row["goal"] == "Complete the requested browser workflow."
    assert plan_row["created_by"] == "deterministic"
    assert [step["step_id"] for step in json.loads(plan_row["steps_json"])] == [
        "extract_form",
        "map_fields",
    ]
    session.close()


def test_governed_start_persists_tool_calls_and_results() -> None:
    """POST /governed/start double-writes compact ToolCall and raw ToolResult rows."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    runtime = ToolRuntime(
        [
            make_runtime_tool(
                "extract_form",
                {
                    "fields": [],
                    "field_count": 0,
                    "login_required": False,
                    "raw_output_json": "persist but do not expose",
                },
            ),
            make_runtime_tool(
                "map_fields",
                {"fields": [], "field_count": 0, "mapped_count": 0},
            ),
        ]
    )

    from unittest.mock import patch

    with patch("app.routers.workflows.build_default_tool_runtime", return_value=runtime):
        response = client.post(
            f"/workflows/{task.id}/governed/start?planner_mode=deterministic"
        )

    assert response.status_code == 200

    call_rows = session.execute(
        text(
            """
            SELECT id, run_id, plan_step_id, tool_name, status,
                   risk_level, governance_decision_json, error
            FROM agent_tool_calls
            WHERE run_id = :run_id
            ORDER BY plan_step_id
            """
        ),
        {"run_id": f"task-{task.id}"},
    ).mappings().all()
    assert [
        {
            "id": row["id"],
            "plan_step_id": row["plan_step_id"],
            "tool_name": row["tool_name"],
            "status": row["status"],
            "risk_level": row["risk_level"],
            "governance_decision": json.loads(row["governance_decision_json"])["decision"],
            "error": row["error"],
        }
        for row in call_rows
    ] == [
        {
            "id": f"task-{task.id}:extract_form",
            "plan_step_id": "extract_form",
            "tool_name": "extract_form",
            "status": "SUCCEEDED",
            "risk_level": "low",
            "governance_decision": "ALLOW",
            "error": None,
        },
        {
            "id": f"task-{task.id}:map_fields",
            "plan_step_id": "map_fields",
            "tool_name": "map_fields",
            "status": "SUCCEEDED",
            "risk_level": "medium",
            "governance_decision": "RECORD_ONLY",
            "error": None,
        },
    ]

    result_row = session.execute(
        text(
            """
            SELECT tool_call_id, status, output_json, error
            FROM agent_tool_results
            WHERE tool_call_id = :tool_call_id
            """
        ),
        {"tool_call_id": f"task-{task.id}:extract_form"},
    ).mappings().one()
    assert result_row["status"] == "SUCCEEDED"
    assert json.loads(result_row["output_json"])["raw_output_json"] == "persist but do not expose"
    assert result_row["error"] is None
    session.close()


def test_save_governed_runtime_state_counts_pending_tool_created_proposals() -> None:
    """Persisted AgentRun count tracks pending tool-created proposals only."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    proposal_statuses = ["PENDING", "PENDING", "APPROVED", "EDITED", "REJECTED"]
    raw_state = {
        "run_id": f"task-{task.id}",
        "task_id": task.id,
        "workflow_type": task.workflow_type,
        "planner_mode": "deterministic",
        "run": {
            "id": f"task-{task.id}",
            "goal": "Count pending proposals.",
            "target_url": task.url,
            "profile_id": task.profile_id,
            "status": "WAITING_REVIEW",
            "mode": "deterministic",
        },
        "tool_results": [
            {
                "tool_call_id": f"task-{task.id}:map_fields",
                "status": "SUCCEEDED",
                "created_proposals": [
                    {
                        "id": f"{status.lower()}-{index}-{task.id}",
                        "proposal_type": "field_value",
                        "target_type": "form_field",
                        "target_ref": str(index),
                        "proposed_value": f"{status.lower()}@example.com",
                        "rationale": "Review tool-created value.",
                        "confidence": 0.8,
                        "risk_level": "low",
                        "status": status,
                    }
                    for index, status in enumerate(proposal_statuses, start=1)
                ],
            }
        ],
    }

    save_governed_runtime_state(session, task=task, raw_state=raw_state)
    save_governed_runtime_state(session, task=task, raw_state=raw_state)

    run = session.get(AgentRun, f"task-{task.id}")
    assert run is not None
    assert run.pending_review_count == 2
    assert session.query(AgentProposal).count() == 5
    client.close()
    session.close()


def test_save_governed_runtime_state_preserves_existing_pending_proposal_count() -> None:
    """Persisted AgentRun count keeps tracking proposals absent from raw state."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    run = AgentRun(
        id=f"task-{task.id}",
        legacy_task_id=task.id,
        goal="Review existing proposal.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
        pending_review_count=1,
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=f"existing-pending-{task.id}",
        run=run,
        proposal_type="field_value",
        target_type="form_field",
        target_ref="1",
        proposed_value="pending@example.com",
        rationale="Already persisted proposal.",
        confidence=0.8,
        risk_level="low",
        status="PENDING",
    )
    session.add_all([run, proposal])
    session.commit()
    raw_state = {
        "run_id": run.id,
        "task_id": task.id,
        "workflow_type": task.workflow_type,
        "planner_mode": "deterministic",
        "run": {
            "id": run.id,
            "goal": "Review existing proposal.",
            "target_url": task.url,
            "profile_id": task.profile_id,
            "status": "COMPLETED",
            "mode": "deterministic",
        },
        "tool_results": [],
    }

    save_governed_runtime_state(session, task=task, raw_state=raw_state)

    session.refresh(run)
    assert run.pending_review_count == 1
    client.close()
    session.close()


def test_governed_get_returns_last_compact_state_after_start() -> None:
    """GET /workflows/{task_id}/governed reloads the latest generic runtime state."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    runtime = ToolRuntime(
        [
            make_runtime_tool(
                "extract_form",
                {"fields": [], "field_count": 0, "login_required": False},
            ),
            make_runtime_tool(
                "map_fields",
                {"fields": [], "field_count": 0, "mapped_count": 0},
            ),
        ]
    )

    from unittest.mock import patch

    with patch("app.routers.workflows.build_default_tool_runtime", return_value=runtime):
        start_response = client.post(
            f"/workflows/{task.id}/governed/start?planner_mode=deterministic"
        )
    assert start_response.status_code == 200

    response = client.get(f"/workflows/{task.id}/governed")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == task.id
    assert payload["workflow_type"] == "form_fill"
    assert payload["planner_mode"] == "deterministic"
    assert payload["status"] == "COMPLETED"
    assert payload["plan"]["created_by"] == "deterministic"
    assert payload["tool_result_count"] == 2
    assert payload["tool_calls"] == [
        {
            "tool_call_id": f"task-{task.id}:extract_form",
            "plan_step_id": "extract_form",
            "tool_name": "extract_form",
            "status": "SUCCEEDED",
            "governance_decision": "ALLOW",
            "error": None,
            "evidence_count": 0,
            "proposal_count": 0,
            "verification_candidate_count": 0,
        },
        {
            "tool_call_id": f"task-{task.id}:map_fields",
            "plan_step_id": "map_fields",
            "tool_name": "map_fields",
            "status": "SUCCEEDED",
            "governance_decision": "RECORD_ONLY",
            "error": None,
            "evidence_count": 0,
            "proposal_count": 0,
            "verification_candidate_count": 0,
        },
    ]
    session.close()


def test_governed_get_restores_compact_state_from_db_when_memory_state_is_missing() -> None:
    """GET /governed falls back to persisted compact runtime state."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    runtime = ToolRuntime(
        [
            make_runtime_tool(
                "extract_form",
                {
                    "fields": [],
                    "field_count": 0,
                    "login_required": False,
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

    with patch("app.routers.workflows.build_default_tool_runtime", return_value=runtime):
        start_response = client.post(
            f"/workflows/{task.id}/governed/start?planner_mode=deterministic"
        )
    assert start_response.status_code == 200

    _reset_governed_runtime_for_tests()
    response = client.get(f"/workflows/{task.id}/governed")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == task.id
    assert payload["workflow_type"] == "form_fill"
    assert payload["planner_mode"] == "deterministic"
    assert payload["status"] == "COMPLETED"
    assert payload["plan"]["created_by"] == "deterministic"
    assert payload["tool_result_count"] == 2
    assert payload["tool_calls"] == [
        {
            "tool_call_id": f"task-{task.id}:extract_form",
            "plan_step_id": "extract_form",
            "tool_name": "extract_form",
            "status": "SUCCEEDED",
            "governance_decision": "ALLOW",
            "error": None,
            "evidence_count": 0,
            "proposal_count": 0,
            "verification_candidate_count": 0,
        },
        {
            "tool_call_id": f"task-{task.id}:map_fields",
            "plan_step_id": "map_fields",
            "tool_name": "map_fields",
            "status": "SUCCEEDED",
            "governance_decision": "RECORD_ONLY",
            "error": None,
            "evidence_count": 0,
            "proposal_count": 0,
            "verification_candidate_count": 0,
        },
    ]
    assert "raw_output_json" not in json.dumps(payload)
    assert "do not expose me" not in json.dumps(payload)
    session.close()


def test_governed_get_restores_paused_tool_call_governance_from_db() -> None:
    """GET /governed restores paused tool-call governance after memory loss."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)

    async def handler(
        _context: ToolExecutionContext,
        _tool_input: dict[str, object],
    ) -> dict[str, object]:
        return {"filled_count": 1}

    runtime = ToolRuntime(
        [
            AgentTool(
                name="fill_form",
                description="Fill fields.",
                input_schema={"type": "object", "properties": {}},
                output_schema={},
                risk_level="medium",
                mutates_browser=True,
                mutates_external_system=False,
                trace_phase="fill",
                handler=handler,
            )
        ]
    )

    class FakeAdapter:
        def __init__(self, **_kwargs):
            pass

        def plan(self, _context):
            return {
                "steps": [
                    {
                        "step_id": "fill_form",
                        "tool_name": "fill_form",
                        "reason": "Fill only after review.",
                        "input_json": {},
                        "risk_level": "medium",
                    }
                ]
            }

    from unittest.mock import patch

    with patch("app.routers.workflows.config.OPENAI_API_KEY", "test-key"), patch(
        "app.routers.workflows.build_default_tool_runtime",
        return_value=runtime,
    ), patch(
        "app.routers.workflows.OpenAIStructuredPlannerAdapter",
        FakeAdapter,
    ):
        start_response = client.post(
            f"/workflows/{task.id}/governed/start?planner_mode=llm_structured"
        )
    assert start_response.status_code == 200
    assert start_response.json()["interrupt_at"] == "review"

    _reset_governed_runtime_for_tests()
    response = client.get(f"/workflows/{task.id}/governed")

    assert response.status_code == 200
    payload = response.json()
    assert payload["interrupt_at"] == "review"
    assert payload["tool_result_count"] == 0
    assert payload["tool_calls"] == [
        {
            "tool_call_id": f"task-{task.id}:fill_form",
            "plan_step_id": "fill_form",
            "tool_name": "fill_form",
            "status": "WAITING_REVIEW",
            "governance_decision": "REVIEW_REQUIRED",
            "error": None,
            "evidence_count": 0,
            "proposal_count": 0,
            "verification_candidate_count": 0,
        }
    ]
    session.close()


def test_governed_get_restores_generic_verification_summary_from_db() -> None:
    """GET /governed returns compact generic verification summary after restore."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)

    save_governed_runtime_state(
        session,
        task=task,
        raw_state={
            "run_id": f"task-{task.id}",
            "task_id": task.id,
            "workflow_type": task.workflow_type,
            "planner_mode": "deterministic",
            "run": {
                "id": f"task-{task.id}",
                "goal": "Fill fields.",
                "target_url": task.url,
                "profile_id": task.profile_id,
                "status": "WAITING_APPROVAL",
                "mode": "deterministic",
            },
            "plan": {
                "id": f"task-{task.id}:plan:1",
                "version": 1,
                "goal": "Fill fields.",
                "steps": [
                    {
                        "step_id": "fill_form",
                        "tool_name": "fill_form",
                        "reason": "Fill fields.",
                        "input_json": {"task_id": task.id},
                        "risk_level": "medium",
                    }
                ],
                "created_by": "deterministic",
            },
            "tool_results": [
                {
                    "tool_call_id": f"task-{task.id}:fill_form",
                    "status": "SUCCEEDED",
                    "governance_decision": {
                        "decision": "VERIFY_REQUIRED",
                        "reason": "Approved write requires verification.",
                        "risk_level": "medium",
                        "requires_verification": True,
                    },
                    "output_json": {
                        "verification_results": [
                            {
                                "target_type": "field_value",
                                "target_ref": "email",
                                "verification_type": "field_value",
                                "expected": "ada@example.com",
                                "actual": "ada@example.com",
                                "status": "VERIFIED",
                            },
                            {
                                "target_type": "field_value",
                                "target_ref": "name",
                                "verification_type": "field_value",
                                "expected": "Ada",
                                "actual": "Grace",
                                "status": "FAILED",
                                "reason": "VALUE_MISMATCH",
                            },
                        ]
                    },
                }
            ],
        },
    )
    assert session.query(AgentVerificationResult).count() == 2

    _reset_governed_runtime_for_tests()
    response = client.get(f"/workflows/{task.id}/governed")

    assert response.status_code == 200
    assert response.json()["verification_result"] == {
        "status": "FAILED",
        "total": 2,
        "verified": 1,
        "failed": 1,
        "skipped": 0,
        "mismatches": [
            {
                "target_type": "field_value",
                "target_ref": "name",
                "verification_type": "field_value",
                "reason": "VALUE_MISMATCH",
            }
        ],
    }
    session.close()


def test_save_governed_runtime_state_persists_verify_browser_state_result() -> None:
    """verify_browser_state tool results become generic verification rows."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)

    save_governed_runtime_state(
        session,
        task=task,
        raw_state={
            "run_id": f"task-{task.id}",
            "task_id": task.id,
            "workflow_type": task.workflow_type,
            "planner_mode": "deterministic",
            "run": {
                "id": f"task-{task.id}",
                "goal": "Verify state.",
                "target_url": task.url,
                "profile_id": task.profile_id,
                "status": "COMPLETED",
                "mode": "deterministic",
            },
            "plan": {
                "id": f"task-{task.id}:plan:1",
                "version": 1,
                "goal": "Verify state.",
                "steps": [
                    {
                        "step_id": "verify",
                        "tool_name": "verify_browser_state",
                        "reason": "Verify browser state.",
                        "input_json": {"task_id": task.id},
                        "risk_level": "low",
                    }
                ],
                "created_by": "deterministic",
            },
            "tool_results": [
                {
                    "tool_call_id": f"task-{task.id}:verify",
                    "status": "SUCCEEDED",
                    "output_json": {
                        "verified": False,
                        "mismatches": [
                            {
                                "target_ref": "email",
                                "reason": "VALUE_MISMATCH",
                            }
                        ],
                    },
                }
            ],
        },
    )

    verification = session.get(
        AgentVerificationResult,
        f"task-{task.id}:verify:verification:0",
    )
    assert verification is not None
    assert verification.tool_call_id == f"task-{task.id}:verify"
    assert verification.target_type == "page_state"
    assert verification.target_ref == "browser_state"
    assert verification.verification_type == "page_state"
    assert verification.status == "FAILED"
    assert verification.reason == "VALUE_MISMATCH"
    assert verification.expected == {"verified": True}
    assert verification.actual == {
        "verified": False,
        "mismatches": [
            {
                "target_ref": "email",
                "reason": "VALUE_MISMATCH",
            }
        ],
    }
    client.close()
    session.close()


def test_governed_get_returns_404_when_no_runtime_state() -> None:
    """GET /workflows/{task_id}/governed returns 404 before a governed run starts."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)

    response = client.get(f"/workflows/{task.id}/governed")

    assert response.status_code == 404
    session.close()


def test_governed_start_rejects_unconfigured_llm_structured_mode() -> None:
    """POST /workflows/{task_id}/governed/start fails closed for unconfigured LLMs."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)

    from unittest.mock import patch

    with patch("app.routers.workflows.config.OPENAI_API_KEY", None):
        response = client.post(
            f"/workflows/{task.id}/governed/start?planner_mode=llm_structured"
        )

    assert response.status_code == 400
    assert "not configured" in response.json()["detail"]
    session.close()


def test_governed_start_uses_configured_llm_structured_planner() -> None:
    """POST /workflows/{task_id}/governed/start can use a configured structured planner."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    runtime = ToolRuntime(
        [
            make_runtime_tool(
                "extract_form",
                {"fields": [], "field_count": 0, "login_required": False},
            )
        ]
    )

    class FakeAdapter:
        def __init__(self, **_kwargs):
            pass

        def plan(self, _context):
            return {
                "steps": [
                    {
                        "step_id": "inspect",
                        "tool_name": "extract_form",
                        "reason": "Inspect the page.",
                        "input_json": {},
                    }
                ]
            }

    from unittest.mock import patch

    with patch("app.routers.workflows.config.OPENAI_API_KEY", "test-key"), patch(
        "app.routers.workflows.build_default_tool_runtime",
        return_value=runtime,
    ), patch(
        "app.routers.workflows.OpenAIStructuredPlannerAdapter",
        FakeAdapter,
    ):
        response = client.post(
            f"/workflows/{task.id}/governed/start?planner_mode=llm_structured"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["planner_mode"] == "llm_structured"
    assert payload["plan"]["created_by"] == "llm"
    assert payload["plan"]["steps"][0]["tool_name"] == "extract_form"
    assert payload["status"] == "COMPLETED"
    session.close()


def test_governed_start_exposes_registered_external_tools_to_llm_planner() -> None:
    """POST /governed/start passes runtime tool metadata into structured planning."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    runtime = ToolRuntime(
        [
            make_runtime_tool(
                "extract_form",
                {"fields": [], "field_count": 0, "login_required": False},
            ),
            make_runtime_tool(
                "mcp.kb.search_documents",
                {"matches": ["SOC2 policy"]},
            ),
        ]
    )
    seen_tools = []

    class FakeAdapter:
        def __init__(self, **_kwargs):
            pass

        def plan(self, context):
            seen_tools.extend(tool["name"] for tool in context["available_tools"])
            return {
                "steps": [
                    {
                        "step_id": "search_policy",
                        "tool_name": "mcp.kb.search_documents",
                        "reason": "Search allowlisted policy evidence.",
                        "input_json": {},
                    }
                ]
            }

    from unittest.mock import patch

    with patch("app.routers.workflows.config.OPENAI_API_KEY", "test-key"), patch(
        "app.routers.workflows.build_default_tool_runtime",
        return_value=runtime,
    ), patch(
        "app.routers.workflows.OpenAIStructuredPlannerAdapter",
        FakeAdapter,
    ):
        response = client.post(
            f"/workflows/{task.id}/governed/start?planner_mode=llm_structured"
        )

    assert response.status_code == 200
    assert "mcp.kb.search_documents" in seen_tools
    assert response.json()["plan"]["steps"][0]["tool_name"] == "mcp.kb.search_documents"
    session.close()


def test_governed_start_registers_configured_openapi_tools_for_planner(monkeypatch) -> None:
    """POST /governed/start includes configured allowlisted OpenAPI read tools."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    runtime = ToolRuntime(
        [
            make_runtime_tool(
                "extract_form",
                {"fields": [], "field_count": 0, "login_required": False},
            )
        ]
    )
    seen_tools = []

    monkeypatch.setattr(
        "app.services.agent_runtime.external_tools.config.EXTERNAL_TOOL_ALLOWLIST",
        '["openapi.crm.read_account"]',
    )
    monkeypatch.setattr(
        "app.services.agent_runtime.external_tools.config.OPENAPI_TOOL_SPECS_JSON",
        (
            "[{"
            '"connector_id":"crm",'
            '"operation_id":"read_account",'
            '"method":"GET",'
            '"path":"/accounts/{account_id}",'
            '"description":"Read account.",'
            '"input_schema":{"type":"object"},'
            '"output_schema":{"type":"object"}'
            "}]"
        ),
    )

    class FakeAdapter:
        def __init__(self, **_kwargs):
            pass

        def plan(self, context):
            seen_tools.extend(tool["name"] for tool in context["available_tools"])
            return {
                "steps": [
                    {
                        "step_id": "inspect",
                        "tool_name": "extract_form",
                        "reason": "Inspect safely.",
                        "input_json": {},
                    }
                ]
            }

    from unittest.mock import patch

    with patch("app.routers.workflows.config.OPENAI_API_KEY", "test-key"), patch(
        "app.routers.workflows.build_default_tool_runtime",
        return_value=runtime,
    ), patch(
        "app.routers.workflows.OpenAIStructuredPlannerAdapter",
        FakeAdapter,
    ):
        response = client.post(
            f"/workflows/{task.id}/governed/start?planner_mode=llm_structured"
        )

    assert response.status_code == 200
    assert "openapi.crm.read_account" in seen_tools
    assert response.json()["plan"]["steps"][0]["tool_name"] == "extract_form"
    session.close()


# ---------------------------------------------------------------------------
# Get endpoint tests
# ---------------------------------------------------------------------------


def test_get_endpoint_returns_compact_state() -> None:
    """GET /workflows/{task_id} returns compact runtime state."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_security_questionnaire_task(session, profile)

    client.post(f"/workflows/{task.id}/start")

    response = client.get(f"/workflows/{task.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == task.id
    assert payload["interrupt_at"] == "review"
    assert "suggestions" in payload
    assert "policy_result" in payload
    session.close()


def test_get_endpoint_returns_404_when_no_runtime_state() -> None:
    """GET /workflows/{task_id} returns 404 if no runtime has been started."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_security_questionnaire_task(session, profile)

    response = client.get(f"/workflows/{task.id}")

    assert response.status_code == 404
    session.close()


def test_governed_review_decision_persists_agent_decision_and_status() -> None:
    """POST /governed review decision double-writes the proposal decision."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    proposal = create_governed_proposal(
        session,
        task,
        proposal_id=f"governed-proposal-{task.id}",
    )

    response = client.post(
        f"/workflows/{task.id}/governed/review-items/{proposal.id}/decision",
        json={"decision": "approved"},
    )

    assert response.status_code == 200
    decision = session.get(AgentReviewDecision, f"decision-{proposal.id}")
    assert decision is not None
    assert decision.decision == "approved"
    session.refresh(proposal)
    assert proposal.status == "APPROVED"
    assert proposal.proposed_value == "old@example.com"
    session.close()


def test_governed_review_decision_edit_updates_proposed_value() -> None:
    """Verify edited governed decisions update the persisted proposal value."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    proposal = create_governed_proposal(
        session,
        task,
        proposal_id=f"governed-edit-{task.id}",
    )

    response = client.post(
        f"/workflows/{task.id}/governed/review-items/{proposal.id}/decision",
        json={"decision": "edited", "edited_value": "new@example.com"},
    )

    assert response.status_code == 200
    session.refresh(proposal)
    assert proposal.status == "EDITED"
    assert proposal.proposed_value == "new@example.com"
    session.close()


def test_governed_review_decision_approve_syncs_form_field_value() -> None:
    """POST /governed decision keeps the legacy fill path in sync."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    field = FormField(
        task_id=task.id,
        label="Email",
        selector="#email",
        field_type="email",
        mapped_value="stale@example.com",
        confidence=0.5,
    )
    session.add(field)
    session.commit()
    proposal = create_governed_proposal(
        session,
        task,
        proposal_id=f"governed-field-sync-{task.id}",
        target_ref=str(field.id),
        proposed_value="persisted@example.com",
    )

    response = client.post(
        f"/workflows/{task.id}/governed/review-items/{proposal.id}/decision",
        json={"decision": "approved"},
    )

    assert response.status_code == 200
    session.refresh(field)
    assert field.mapped_value == "persisted@example.com"
    assert field.confidence == 1.0
    session.close()


@pytest.mark.parametrize("decision", ["approved", "edited", "rejected"])
def test_governed_review_decision_decrements_pending_review_count_for_final_decisions(
    decision: str,
) -> None:
    """POST /governed decision removes approved/edited/rejected items from pending count."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    proposal = create_governed_proposal(
        session,
        task,
        proposal_id=f"governed-count-{task.id}-1",
    )
    add_pending_sibling_proposal(
        session,
        proposal,
        proposal_id=f"governed-count-{task.id}-2",
    )

    response = client.post(
        f"/workflows/{task.id}/governed/review-items/{proposal.id}/decision",
        json={
            "decision": decision,
            "edited_value": "new@example.com" if decision == "edited" else None,
        },
    )

    assert response.status_code == 200
    run = session.get(AgentRun, proposal.run_id)
    assert run is not None
    assert run.pending_review_count == 1
    session.close()


def test_governed_review_decision_needs_more_evidence_decrements_pending_review_count() -> None:
    """POST /governed decision treats needs_more_evidence as no longer pending."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    proposal = create_governed_proposal(
        session,
        task,
        proposal_id=f"governed-evidence-{task.id}-1",
    )
    add_pending_sibling_proposal(
        session,
        proposal,
        proposal_id=f"governed-evidence-{task.id}-2",
    )

    response = client.post(
        f"/workflows/{task.id}/governed/review-items/{proposal.id}/decision",
        json={"decision": "needs_more_evidence"},
    )

    assert response.status_code == 200
    run = session.get(AgentRun, proposal.run_id)
    assert run is not None
    assert run.pending_review_count == 1
    session.close()


def test_governed_review_decision_does_not_write_workflow_memory() -> None:
    """Verify memory-write proposals are only reviewed, not directly saved."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)
    proposal = create_governed_proposal(
        session,
        task,
        proposal_id=f"governed-memory-{task.id}",
        proposal_type="memory_write",
        target_type="workflow_memory",
        proposed_value="email",
    )

    response = client.post(
        f"/workflows/{task.id}/governed/review-items/{proposal.id}/decision",
        json={"decision": "approved"},
    )

    assert response.status_code == 200
    assert session.query(WorkflowMemoryItem).count() == 0
    session.close()


# ---------------------------------------------------------------------------
# Review endpoint tests
# ---------------------------------------------------------------------------


def test_review_endpoint_requires_prior_start() -> None:
    """POST /workflows/{task_id}/review returns 409 if not at review gate."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_security_questionnaire_task(session, profile)

    response = client.post(
        f"/workflows/{task.id}/review",
        json={"decision": "approve_all", "approvals": []},
    )

    assert response.status_code == 409
    session.close()


def test_review_endpoint_advances_past_review_gate() -> None:
    """POST /workflows/{task_id}/review resumes graph past review."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_security_questionnaire_task(session, profile)

    client.post(f"/workflows/{task.id}/start")

    response = client.post(
        f"/workflows/{task.id}/review",
        json={"decision": "approve_all", "approvals": []},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["interrupt_at"] == "submit_approval"
    assert payload["status"] in ("AWAITING_SUBMIT_APPROVAL", "VERIFYING")
    session.close()


def test_review_endpoint_rejects_unsupported_workflow() -> None:
    """POST /workflows/{task_id}/review returns 400 for non-security workflows."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_form_fill_task(session, profile)

    response = client.post(
        f"/workflows/{task.id}/review",
        json={"decision": "approve_all", "approvals": []},
    )

    assert response.status_code == 400
    session.close()


# ---------------------------------------------------------------------------
# Security: no sensitive values in response
# ---------------------------------------------------------------------------


def test_response_does_not_leak_sensitive_values() -> None:
    """API response does not include raw sensitive field values."""

    client, session = build_environment()
    profile = create_profile(session)
    task = create_security_questionnaire_task(session, profile)

    response = client.post(f"/workflows/{task.id}/start")

    assert response.status_code == 200
    payload = response.json()

    assert "memory_hits" in payload
    for hit in payload.get("memory_hits", []):
        assert "value" not in hit or hit.get("value") is None or hit.get("value") == ""

    assert "profile_values" not in payload
    session.close()


# ---------------------------------------------------------------------------
# No generic resume exposed
# ---------------------------------------------------------------------------


def test_no_generic_resume_endpoint_exists() -> None:
    """Generic /resume endpoint is not exposed — only /review."""

    client, session = build_environment()

    resume_response = client.post("/workflows/1/resume")
    assert resume_response.status_code == 404

    state_response = client.post("/workflows/1/state")
    assert state_response.status_code == 404

    session.close()
