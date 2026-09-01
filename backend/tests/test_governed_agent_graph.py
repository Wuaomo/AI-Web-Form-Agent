"""Contract tests for the generic governed agent graph skeleton."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FormField, Profile, Task
from app.services.agent_runtime.governed_agent_graph import (
    _reset_governed_runtime_for_tests,
    build_governed_agent_graph,
    get_governed_runtime_state,
    run_allowed_tool_once,
    run_allowed_tools_until_pause,
    run_to_governance,
    resume_governed_runtime_from_approval,
    resume_governed_runtime_from_review,
    start_governed_runtime,
)
from app.services.agent_runtime.planner import AgentPlanner, FakeStructuredPlannerAdapter
from app.services.agent_runtime.tool_runtime import AgentTool, ToolExecutionContext, ToolRuntime
from app.services.agent_runtime.tools import build_default_tool_runtime
from app.services.workflow_trace_service import list_spans_for_task


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_governed_runtime() -> None:
    _reset_governed_runtime_for_tests()


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


async def noop_handler(
    _context: ToolExecutionContext,
    _tool_input: dict[str, object],
) -> dict[str, object]:
    return {}


def make_tool(
    name: str,
    *,
    mutates_browser: bool = False,
    risk_level: str = "low",
    handler=None,
) -> AgentTool:
    return AgentTool(
        name=name,
        description=f"{name} test tool",
        input_schema={"type": "object", "properties": {}},
        output_schema={},
        risk_level=risk_level,
        mutates_browser=mutates_browser,
        mutates_external_system=False,
        trace_phase="test",
        handler=handler or noop_handler,
    )


def test_build_governed_agent_graph_has_minimal_phase_5_nodes() -> None:
    """Verify the first generic graph slice exposes the RFC node names."""

    graph = build_governed_agent_graph()

    graph_nodes = graph.get_graph().nodes
    for node_name in [
        "initialize_run",
        "plan_next_step",
        "prepare_tool_call",
        "check_governance",
        "interrupt_for_review",
        "execute_tool",
        "observe_result",
        "decide_next_step",
        "verify_result",
        "finish",
        "fail",
    ]:
        assert node_name in graph_nodes


def test_run_to_governance_prepares_default_no_key_readonly_tool_call() -> None:
    """Verify deterministic mode prepares extract_form without executing it."""

    handler = AsyncMock(return_value={})
    runtime = ToolRuntime([make_tool("extract_form", handler=handler)])

    state = run_to_governance(
        {
            "run_id": "task-1",
            "task_id": 1,
            "goal": "Complete this page from my profile.",
            "target_url": "https://example.com/form",
            "profile_id": 7,
            "workflow_type": "vendor_onboarding",
        },
        runtime=runtime,
    )

    assert state["run"]["mode"] == "deterministic"
    assert state["run"]["status"] == "RUNNING"
    assert state["plan"]["steps"][0]["tool_name"] == "extract_form"
    assert state["current_tool_call"]["tool_name"] == "extract_form"
    assert state["current_tool_call"]["input_json"] == {
        "task_id": 1,
        "url": "https://example.com/form",
        "profile_id": 7,
    }
    assert state["governance_decision"]["decision"] == "ALLOW"
    assert state["interrupt_at"] is None
    handler.assert_not_awaited()


def test_run_to_governance_uses_llm_structured_planner_without_bypassing_review() -> None:
    """Verify LLM-planned browser writes still pause at governance."""

    handler = AsyncMock(return_value={"filled": True})
    runtime = ToolRuntime(
        [
            make_tool(
                "fill_browser_fields",
                mutates_browser=True,
                risk_level="medium",
                handler=handler,
            )
        ]
    )
    planner = AgentPlanner(
        runtime=runtime,
        structured_adapter=FakeStructuredPlannerAdapter(
            {
                "steps": [
                    {
                        "step_id": "fill",
                        "tool_name": "fill_browser_fields",
                        "reason": "Apply reviewed values.",
                        "input_json": {"task_id": 2},
                        "risk_level": "medium",
                    }
                ]
            }
        ),
    )

    state = run_to_governance(
        {
            "run_id": "task-llm-review",
            "task_id": 2,
            "goal": "Fill approved values.",
            "target_url": "https://example.com/form",
            "profile_id": 7,
            "planner_mode": "llm_structured",
        },
        runtime=runtime,
        planner=planner,
    )

    assert state["run"]["mode"] == "llm_structured"
    assert state["plan"]["created_by"] == "llm"
    assert state["run"]["status"] == "WAITING_REVIEW"
    assert state["current_tool_call"]["tool_name"] == "fill_browser_fields"
    assert state["governance_decision"]["decision"] == "REVIEW_REQUIRED"
    handler.assert_not_awaited()


def test_run_to_governance_returns_failed_state_for_invalid_llm_plan() -> None:
    """Verify invalid structured plans fail before tool preparation."""

    session = make_session()
    try:
        profile = Profile(profile_name="Trace profile")
        task = Task(url="https://example.com/form", profile=profile)
        session.add(task)
        session.commit()

        runtime = ToolRuntime()
        planner = AgentPlanner(
            runtime=runtime,
            structured_adapter=FakeStructuredPlannerAdapter(
                {
                    "steps": [
                        {
                            "step_id": "unknown",
                            "tool_name": "steal_password",
                            "reason": "Try an unregistered tool.",
                            "input_json": {},
                        }
                    ]
                }
            ),
        )

        state = run_to_governance(
            {
                "run_id": f"task-{task.id}",
                "task_id": task.id,
                "goal": "Inspect safely.",
                "target_url": task.url,
                "profile_id": profile.id,
                "planner_mode": "llm_structured",
            },
            runtime=runtime,
            planner=planner,
            metadata={"db": session, "task_id": task.id},
        )

        assert state["run"]["status"] == "FAILED"
        assert state["error"] == "Unknown runtime tool: steal_password"
        assert "current_tool_call" not in state

        spans = list_spans_for_task(session, task.id)
        assert len(spans) == 1
        assert spans[0].phase == "planning"
        assert spans[0].name == "agent_planner"
        assert spans[0].status == "FAILED"
        assert spans[0].span_metadata["planner_mode"] == "llm_structured"
        assert spans[0].error_message == "Unknown runtime tool: steal_password"
    finally:
        session.close()


def test_run_to_governance_records_planning_success_trace() -> None:
    """Verify successful planning records planner source and step evidence."""

    session = make_session()
    try:
        profile = Profile(profile_name="Trace profile")
        task = Task(url="https://example.com/form", profile=profile)
        session.add(task)
        session.commit()

        runtime = ToolRuntime([make_tool("extract_form")])

        state = run_to_governance(
            {
                "run_id": f"task-{task.id}",
                "task_id": task.id,
                "goal": "Inspect safely.",
                "target_url": task.url,
                "profile_id": profile.id,
                "plan_steps": [
                    {
                        "step_id": "inspect",
                        "tool_name": "extract_form",
                        "reason": "Read page.",
                        "input_json": {"task_id": task.id},
                    }
                ],
            },
            runtime=runtime,
            metadata={"db": session, "task_id": task.id},
        )

        spans = list_spans_for_task(session, task.id)
        assert state["plan"]["created_by"] == "deterministic"
        assert len(spans) == 1
        assert spans[0].phase == "planning"
        assert spans[0].name == "agent_planner"
        assert spans[0].status == "SUCCESS"
        assert spans[0].output["created_by"] == "deterministic"
        assert spans[0].output["step_ids"] == ["inspect"]
    finally:
        session.close()


def test_run_to_governance_pauses_browser_writes_before_execution() -> None:
    """Verify review-required tools stop before their handler can run."""

    handler = AsyncMock(return_value={})
    runtime = ToolRuntime(
        [
            make_tool(
                "fill_browser_fields",
                mutates_browser=True,
                risk_level="medium",
                handler=handler,
            )
        ]
    )

    state = run_to_governance(
        {
            "run_id": "task-2",
            "task_id": 2,
            "goal": "Fill approved values.",
            "target_url": "https://example.com/form",
            "profile_id": 7,
            "plan_steps": [
                {
                    "step_id": "fill_approved_values",
                    "tool_name": "fill_browser_fields",
                    "reason": "Apply values after review.",
                    "input_json": {"task_id": 2},
                    "risk_level": "medium",
                }
            ],
        },
        runtime=runtime,
    )

    assert state["run"]["status"] == "WAITING_REVIEW"
    assert state["current_tool_call"]["status"] == "WAITING_REVIEW"
    assert state["governance_decision"]["decision"] == "REVIEW_REQUIRED"
    assert state["interrupt_at"] == "review"
    handler.assert_not_awaited()


async def extract_handler(
    _context: ToolExecutionContext,
    tool_input: dict[str, object],
) -> dict[str, object]:
    return {
        "task_id": tool_input["task_id"],
        "fields": [{"selector": "#email"}],
        "field_count": 1,
        "login_required": False,
    }


def test_run_to_governance_still_stops_before_allowed_tool_execution() -> None:
    """Verify the original helper remains a governance-only contract."""

    handler = AsyncMock(side_effect=extract_handler)
    runtime = ToolRuntime([make_tool("extract_form", handler=handler)])

    state = run_to_governance(
        {
            "run_id": "task-3",
            "task_id": 3,
            "goal": "Inspect this form.",
            "target_url": "https://example.com/form",
            "profile_id": 7,
        },
        runtime=runtime,
    )

    assert "tool_results" not in state
    assert state["current_tool_call"]["status"] == "PENDING"
    handler.assert_not_awaited()


@pytest.mark.anyio
async def test_run_allowed_tool_once_executes_allowed_readonly_tool() -> None:
    """Verify allowed tools execute only after passing governance."""

    handler = AsyncMock(side_effect=extract_handler)
    runtime = ToolRuntime([make_tool("extract_form", handler=handler)])

    state = await run_allowed_tool_once(
        {
            "run_id": "task-4",
            "task_id": 4,
            "goal": "Inspect this form.",
            "target_url": "https://example.com/form",
            "profile_id": 7,
        },
        runtime=runtime,
    )

    assert state["run"]["status"] == "RUNNING"
    assert state["current_tool_call"]["status"] == "SUCCEEDED"
    assert state["current_step_index"] == 1
    assert state["tool_results"][0]["status"] == "SUCCEEDED"
    assert state["tool_results"][0]["output_json"]["field_count"] == 1
    handler.assert_awaited_once()


@pytest.mark.anyio
async def test_run_allowed_tools_until_pause_completes_default_readonly_plan() -> None:
    """Verify default no-key plan can run extract_form then map_fields."""

    calls = []

    async def extract(
        _context: ToolExecutionContext,
        tool_input: dict[str, object],
    ) -> dict[str, object]:
        calls.append(("extract_form", tool_input))
        return {"fields": [{"selector": "#email"}], "field_count": 1, "login_required": False}

    async def map_fields(
        _context: ToolExecutionContext,
        tool_input: dict[str, object],
    ) -> dict[str, object]:
        calls.append(("map_fields", tool_input))
        return {"fields": [{"selector": "#email"}], "field_count": 1, "mapped_count": 1}

    runtime = ToolRuntime(
        [
            make_tool("extract_form", handler=extract),
            make_tool("map_fields", risk_level="medium", handler=map_fields),
        ]
    )

    state = await run_allowed_tools_until_pause(
        {
            "run_id": "task-5",
            "task_id": 5,
            "goal": "Inspect and map this form.",
            "target_url": "https://example.com/form",
            "profile_id": 7,
        },
        runtime=runtime,
    )

    assert state["run"]["status"] == "COMPLETED"
    assert state["current_step_index"] == 2
    assert [result["tool_call_id"] for result in state["tool_results"]] == [
        "task-5:extract_form",
        "task-5:map_fields",
    ]
    assert [name for name, _tool_input in calls] == ["extract_form", "map_fields"]
    assert calls[1][1] == {"task_id": 5}


@pytest.mark.anyio
async def test_run_allowed_tools_until_pause_stops_at_review_required_step() -> None:
    """Verify the generic loop stops before executing browser mutations."""

    read_handler = AsyncMock(return_value={"ok": True})
    write_handler = AsyncMock(return_value={"filled": True})
    runtime = ToolRuntime(
        [
            make_tool("extract_form", handler=read_handler),
            make_tool(
                "fill_browser_fields",
                mutates_browser=True,
                risk_level="medium",
                handler=write_handler,
            ),
        ]
    )

    state = await run_allowed_tools_until_pause(
        {
            "run_id": "task-6",
            "task_id": 6,
            "goal": "Inspect then fill.",
            "target_url": "https://example.com/form",
            "profile_id": 7,
            "plan_steps": [
                {
                    "step_id": "inspect",
                    "tool_name": "extract_form",
                    "reason": "Read page first.",
                    "input_json": {"task_id": 6},
                    "risk_level": "low",
                },
                {
                    "step_id": "fill",
                    "tool_name": "fill_browser_fields",
                    "reason": "Write approved values.",
                    "input_json": {"task_id": 6},
                    "risk_level": "medium",
                },
            ],
        },
        runtime=runtime,
    )

    assert state["run"]["status"] == "WAITING_REVIEW"
    assert state["current_step_index"] == 1
    assert state["current_tool_call"]["tool_name"] == "fill_browser_fields"
    assert state["current_tool_call"]["status"] == "WAITING_REVIEW"
    assert state["interrupt_at"] == "review"
    assert len(state["tool_results"]) == 1
    read_handler.assert_awaited_once()
    write_handler.assert_not_awaited()


@pytest.mark.anyio
async def test_run_allowed_tools_until_pause_stops_when_login_is_required() -> None:
    """Verify generic graph does not continue past a login gate."""

    extract_handler = AsyncMock(
        return_value={"fields": [], "field_count": 0, "login_required": True}
    )
    map_handler = AsyncMock(return_value={"fields": [], "field_count": 0})
    runtime = ToolRuntime(
        [
            make_tool("extract_form", handler=extract_handler),
            make_tool("map_fields", risk_level="medium", handler=map_handler),
        ]
    )

    state = await run_allowed_tools_until_pause(
        {
            "run_id": "task-login-required",
            "task_id": 11,
            "goal": "Inspect and map this form.",
            "target_url": "https://example.com/login-first",
            "profile_id": 7,
        },
        runtime=runtime,
    )

    assert state["run"]["status"] == "BLOCKED"
    assert state["error"] == "Login required before governed workflow can continue."
    assert state["current_step_index"] == 1
    extract_handler.assert_awaited_once()
    map_handler.assert_not_awaited()


def test_get_governed_runtime_state_returns_none_before_start() -> None:
    """Verify unknown generic runtime state is reported as absent."""

    assert get_governed_runtime_state("task-missing") is None


@pytest.mark.anyio
async def test_start_governed_runtime_persists_review_pause_state() -> None:
    """Verify a paused generic graph state can be queried by run ID."""

    read_handler = AsyncMock(return_value={"field_count": 1})
    write_handler = AsyncMock(return_value={"filled": True})
    runtime = ToolRuntime(
        [
            make_tool("extract_form", handler=read_handler),
            make_tool(
                "fill_browser_fields",
                mutates_browser=True,
                risk_level="medium",
                handler=write_handler,
            ),
        ]
    )

    started = await start_governed_runtime(
        {
            "run_id": "task-7",
            "task_id": 7,
            "goal": "Inspect then pause before fill.",
            "target_url": "https://example.com/form",
            "profile_id": 7,
            "plan_steps": [
                {
                    "step_id": "inspect",
                    "tool_name": "extract_form",
                    "reason": "Read page first.",
                    "input_json": {"task_id": 7},
                    "risk_level": "low",
                },
                {
                    "step_id": "fill",
                    "tool_name": "fill_browser_fields",
                    "reason": "Write approved values.",
                    "input_json": {"task_id": 7},
                    "risk_level": "medium",
                },
            ],
        },
        runtime=runtime,
    )

    stored = get_governed_runtime_state("task-7")

    assert stored is not None
    assert stored["run"]["status"] == "WAITING_REVIEW"
    assert stored["interrupt_at"] == "review"
    assert stored["current_tool_call"]["tool_name"] == "fill_browser_fields"
    assert stored["tool_results"][0]["output_json"] == {"field_count": 1}
    assert stored["run"] == started["run"]
    write_handler.assert_not_awaited()


@pytest.mark.anyio
async def test_resume_governed_runtime_rejects_missing_state() -> None:
    """Verify resume cannot invent runtime state."""

    runtime = ToolRuntime([make_tool("fill_browser_fields", mutates_browser=True)])

    with pytest.raises(ValueError, match="No governed runtime state found"):
        await resume_governed_runtime_from_review("task-missing", runtime=runtime)


@pytest.mark.anyio
async def test_resume_governed_runtime_requires_review_pause() -> None:
    """Verify completed runs cannot be resumed through the review path."""

    runtime = ToolRuntime([make_tool("extract_form")])
    await start_governed_runtime(
        {
            "run_id": "task-complete",
            "task_id": 8,
            "goal": "Inspect once.",
            "target_url": "https://example.com/form",
            "profile_id": 7,
            "plan_steps": [
                {
                    "step_id": "inspect",
                    "tool_name": "extract_form",
                    "reason": "Read page.",
                    "input_json": {"task_id": 8},
                    "risk_level": "low",
                }
            ],
        },
        runtime=runtime,
    )

    with pytest.raises(ValueError, match="not waiting for review"):
        await resume_governed_runtime_from_review("task-complete", runtime=runtime)


@pytest.mark.anyio
async def test_resume_governed_runtime_executes_approved_write_then_verifies() -> None:
    """Verify review resume runs the approved browser write and verification step."""

    fill_handler = AsyncMock(return_value={"filled_count": 1})
    verify_handler = AsyncMock(return_value={"verified": True, "mismatches": []})
    runtime = ToolRuntime(
        [
            make_tool(
                "fill_browser_fields",
                mutates_browser=True,
                risk_level="medium",
                handler=fill_handler,
            ),
            make_tool("verify_browser_state", handler=verify_handler),
        ]
    )

    await start_governed_runtime(
        {
            "run_id": "task-resume",
            "task_id": 9,
            "goal": "Fill then verify.",
            "target_url": "https://example.com/form",
            "profile_id": 7,
            "plan_steps": [
                {
                    "step_id": "fill",
                    "tool_name": "fill_browser_fields",
                    "reason": "Write reviewed values.",
                    "input_json": {"task_id": 9},
                    "risk_level": "medium",
                },
                {
                    "step_id": "verify",
                    "tool_name": "verify_browser_state",
                    "reason": "Verify filled browser state.",
                    "input_json": {"task_id": 9},
                    "risk_level": "low",
                },
            ],
        },
        runtime=runtime,
    )

    state = await resume_governed_runtime_from_review("task-resume", runtime=runtime)

    assert state["run"]["status"] == "COMPLETED"
    assert state["verification_result"] == {"verified": True, "mismatches": []}
    assert [result["tool_call_id"] for result in state["tool_results"]] == [
        "task-resume:fill",
        "task-resume:verify",
    ]
    fill_handler.assert_awaited_once()
    verify_handler.assert_awaited_once()


@pytest.mark.anyio
async def test_resume_governed_runtime_executes_approved_submit() -> None:
    """Verify approval resume runs an explicitly approved submit tool."""

    submit_handler = AsyncMock(return_value={"submitted": True})
    runtime = ToolRuntime(
        [
            make_tool(
                "submit_form",
                mutates_browser=True,
                risk_level="high",
                handler=submit_handler,
            ),
        ]
    )

    await start_governed_runtime(
        {
            "run_id": "task-submit",
            "task_id": 12,
            "goal": "Submit after explicit approval.",
            "target_url": "https://example.com/form",
            "profile_id": 7,
            "plan_steps": [
                {
                    "step_id": "submit",
                    "tool_name": "submit_form",
                    "reason": "Submit reviewed form.",
                    "input_json": {"task_id": 12},
                    "risk_level": "high",
                }
            ],
        },
        runtime=runtime,
    )

    state = await resume_governed_runtime_from_approval(
        "task-submit",
        runtime=runtime,
    )

    assert state["run"]["status"] == "COMPLETED"
    assert state["current_tool_call"]["status"] == "SUCCEEDED"
    assert state["tool_results"][0]["governance_decision"]["decision"] == "VERIFY_REQUIRED"
    assert state["tool_results"][0]["output_json"] == {"submitted": True}
    submit_handler.assert_awaited_once()


@pytest.mark.anyio
async def test_verify_browser_state_mismatch_fails_governed_run() -> None:
    """Verify failed browser-state verification does not finish the run."""

    verify_handler = AsyncMock(
        return_value={
            "verified": False,
            "mismatches": [{"reason": "email field stayed blank"}],
        }
    )
    runtime = ToolRuntime(
        [make_tool("verify_browser_state", handler=verify_handler)]
    )

    state = await run_allowed_tools_until_pause(
        {
            "run_id": "task-verify-failed",
            "task_id": 13,
            "goal": "Verify browser state.",
            "target_url": "https://example.com/form",
            "profile_id": 7,
            "plan_steps": [
                {
                    "step_id": "verify",
                    "tool_name": "verify_browser_state",
                    "reason": "Verify filled browser state.",
                    "input_json": {"task_id": 13},
                    "risk_level": "low",
                }
            ],
        },
        runtime=runtime,
    )

    assert state["run"]["status"] == "FAILED"
    assert state["error"] == "email field stayed blank"
    assert state["verification_result"]["verified"] is False
    verify_handler.assert_awaited_once()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "workflow_type",
    ["security_questionnaire", "vendor_onboarding"],
)
async def test_generic_graph_supports_security_and_vendor_readonly_parity(
    workflow_type: str,
) -> None:
    """Verify both key demos can run the generic deterministic read-only path."""

    runtime = ToolRuntime(
        [
            make_tool("extract_form", handler=extract_handler),
            make_tool(
                "map_fields",
                risk_level="medium",
                handler=AsyncMock(
                    return_value={"fields": [], "field_count": 0, "mapped_count": 0}
                ),
            ),
        ]
    )

    state = await run_allowed_tools_until_pause(
        {
            "run_id": f"task-{workflow_type}",
            "task_id": 10,
            "goal": "Inspect and map this demo.",
            "target_url": "https://example.com/demo",
            "profile_id": 7,
            "workflow_type": workflow_type,
        },
        runtime=runtime,
    )

    assert state["run"]["status"] == "COMPLETED"
    assert state["run"]["context"]["workflow_type"] == workflow_type
    assert [step["tool_name"] for step in state["plan"]["steps"]] == [
        "extract_form",
        "map_fields",
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "workflow_type",
    ["security_questionnaire", "vendor_onboarding"],
)
async def test_generic_graph_maps_security_and_vendor_tasks_with_real_rules(
    workflow_type: str,
) -> None:
    """Verify key demos can use the generic graph with the real local mapper."""

    session = make_session()
    try:
        profile = Profile(profile_name="Demo", email="ada@example.com")
        task = Task(
            url="https://example.com/demo",
            profile=profile,
            workflow_type=workflow_type,
            status="MAPPING_READY",
            workflow_status="MAPPING_READY",
        )
        field = FormField(
            task=task,
            label="Email address",
            selector="#email",
            field_type="email",
            required=True,
        )
        session.add_all([task, field])
        session.commit()

        analysis = type(
            "Analysis",
            (),
            {"fields": [], "login_required": False},
        )()
        extractor = AsyncMock(return_value=analysis)
        runtime = build_default_tool_runtime(extract_form_analysis_handler=extractor)

        state = await run_allowed_tools_until_pause(
            {
                "run_id": f"task-{task.id}",
                "task_id": task.id,
                "goal": "Inspect and map this demo.",
                "target_url": task.url,
                "profile_id": task.profile_id,
                "workflow_type": workflow_type,
            },
            runtime=runtime,
            metadata={"db": session, "task_id": task.id},
        )

        session.refresh(field)
        assert state["run"]["status"] == "WAITING_REVIEW"
        assert state["interrupt_at"] == "review"
        assert state["run"]["context"]["workflow_type"] == workflow_type
        assert field.mapped_profile_key == "email"
        assert state["tool_results"][1]["output_json"]["mapped_count"] == 1
        assert state["tool_results"][1]["created_proposals"][0]["target_ref"] == str(
            field.id
        )
    finally:
        session.close()
