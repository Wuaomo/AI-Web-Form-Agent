"""Generic governed agent graph skeleton.

This Phase 5 slice prepares typed tool calls, checks action-level governance,
and can execute allowed read-only steps. Review, approval, and blocked decisions
still stop before tool execution.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.services.agent_runtime.governance import GovernanceEngine
from app.services.agent_runtime.planner import AgentPlanner
from app.services.agent_runtime.schemas import (
    AgentRunState,
    GovernanceDecision,
    ToolCall,
)
from app.services.agent_runtime.tool_runtime import ToolRuntime
from app.services.agent_runtime.tool_runtime import ToolExecutionContext
from app.services.workflow_trace_service import create_span, finish_span
from app.workflow_constants import (
    SPAN_PHASE_PLANNING,
    SPAN_STATUS_FAILED,
    SPAN_STATUS_SUCCESS,
)

_memory_saver = MemorySaver()
_graph_instance = None


class GovernedAgentGraphState(TypedDict, total=False):
    """Serializable state for the generic governed agent graph."""

    run_id: str
    task_id: int
    goal: str
    target_url: str
    profile_id: int
    workflow_type: str
    planner_mode: str
    plan_steps: list[dict[str, Any]]
    available_tools: list[dict[str, Any]]

    run: dict[str, Any]
    plan: dict[str, Any]
    current_step_index: int
    current_tool_call: dict[str, Any]
    governance_decision: dict[str, Any]
    tool_results: list[dict[str, Any]]
    verification_result: dict[str, Any]
    approved_tool_call_ids: list[str]
    stop_after_governance: bool
    stop_after_one_tool: bool
    interrupt_at: str | None
    error: str | None


def _runtime(config: RunnableConfig) -> ToolRuntime:
    runtime = config.get("configurable", {}).get("runtime")
    return runtime if runtime is not None else ToolRuntime()


def _planner(config: RunnableConfig) -> AgentPlanner:
    planner = config.get("configurable", {}).get("planner")
    if planner is not None:
        return planner
    return AgentPlanner(runtime=_runtime(config))


def _thread_id(run_id: str) -> str:
    return f"governed-agent:{run_id}"


def _get_graph():
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_governed_agent_graph(checkpointer=_memory_saver)
    return _graph_instance


def _reset_governed_runtime_for_tests() -> None:
    global _graph_instance
    _graph_instance = None
    _memory_saver.storage.clear()
    if hasattr(_memory_saver, "writes"):
        _memory_saver.writes.clear()


def _initialize_run_node(
    state: GovernedAgentGraphState,
    config: RunnableConfig,
) -> GovernedAgentGraphState:
    run_id = state.get("run_id") or f"task-{state.get('task_id')}"
    run = AgentRunState(
        id=run_id,
        goal=state.get("goal") or "Complete the requested browser workflow.",
        target_url=state.get("target_url"),
        profile_id=state.get("profile_id"),
        status="PLANNING",
        mode=state.get("planner_mode", "deterministic"),
        context={
            "task_id": state.get("task_id"),
            "workflow_type": state.get("workflow_type"),
        },
    )

    return {
        **state,
        "run_id": run_id,
        "run": run.model_dump(mode="json"),
        "current_step_index": state.get("current_step_index", 0),
        "interrupt_at": None,
        "error": None,
    }


def _plan_next_step_node(
    state: GovernedAgentGraphState,
    config: RunnableConfig,
) -> GovernedAgentGraphState:
    run_id = state["run_id"]
    planner_context = {
        **state,
        "run_id": run_id,
        "goal": state["run"]["goal"],
        "target_url": state.get("target_url"),
        "profile_id": state.get("profile_id"),
        "planner_mode": state["run"]["mode"],
    }
    span = _create_planning_trace_span(config, planner_context)
    try:
        plan = _planner(config).create_plan(
            planner_context,
            mode=state["run"]["mode"],
        )
    except Exception as exc:
        _finish_planning_trace_span(
            config,
            span,
            status=SPAN_STATUS_FAILED,
            output={},
            error=str(exc),
        )
        return {
            **state,
            "run": {**state["run"], "status": "FAILED"},
            "error": str(exc),
        }

    _finish_planning_trace_span(
        config,
        span,
        status=SPAN_STATUS_SUCCESS,
        output={
            "created_by": plan.created_by,
            "step_count": len(plan.steps),
            "step_ids": [step.step_id for step in plan.steps],
        },
    )

    return {
        **state,
        "plan": plan.model_dump(mode="json"),
        "run": {**state["run"], "status": "RUNNING", "current_plan_id": plan.id},
    }


def _prepare_tool_call_node(
    state: GovernedAgentGraphState,
    config: RunnableConfig,
) -> GovernedAgentGraphState:
    steps = state["plan"]["steps"]
    step = steps[state.get("current_step_index", 0)]
    tool_call = ToolCall(
        id=f"{state['run_id']}:{step['step_id']}",
        run_id=state["run_id"],
        plan_step_id=step["step_id"],
        tool_name=step["tool_name"],
        input_json=step.get("input_json", {}),
        status="PENDING",
        risk_level=step.get("risk_level", "low"),
    )

    return {**state, "current_tool_call": tool_call.model_dump(mode="json")}


def _check_governance_node(
    state: GovernedAgentGraphState,
    config: RunnableConfig,
) -> GovernedAgentGraphState:
    runtime = _runtime(config)
    tool_call = state["current_tool_call"]
    tool = runtime.get_tool(tool_call["tool_name"])
    if tool is None:
        decision = GovernanceDecision(
            decision="BLOCKED",
            reason=f"Unknown runtime tool: {tool_call['tool_name']}",
            risk_level="blocked",
            blocked_reason=f"Unknown runtime tool: {tool_call['tool_name']}",
        )
    else:
        decision = GovernanceEngine().evaluate_tool_call(
            tool,
            tool_call.get("input_json", {}),
        )
        if (
            decision.decision == "REVIEW_REQUIRED"
            and tool_call["id"] in state.get("approved_tool_call_ids", [])
        ):
            decision = GovernanceDecision(
                decision="VERIFY_REQUIRED",
                reason="Tool call was approved during human review.",
                risk_level=tool.risk_level,
            )

    status, call_status, interrupt_at = _status_for_decision(decision)
    return {
        **state,
        "run": {**state["run"], "status": status},
        "current_tool_call": {**tool_call, "status": call_status},
        "governance_decision": decision.model_dump(mode="json"),
        "interrupt_at": interrupt_at,
    }


async def _execute_tool_node(
    state: GovernedAgentGraphState,
    config: RunnableConfig,
) -> GovernedAgentGraphState:
    runtime = _runtime(config)
    tool_call = state["current_tool_call"]
    metadata = config.get("configurable", {}).get("metadata", {})
    context = ToolExecutionContext(
        run_id=state["run_id"],
        plan_step_id=tool_call.get("plan_step_id"),
        metadata={
            **metadata,
            "approved_tool_call_ids": state.get("approved_tool_call_ids", []),
        },
    )

    result = await runtime.execute(
        tool_call_id=tool_call["id"],
        tool_name=tool_call["tool_name"],
        tool_input=tool_call.get("input_json", {}),
        context=context,
    )
    return {
        **state,
        "current_tool_call": {**tool_call, "status": result.status},
        "tool_results": [
            *state.get("tool_results", []),
            result.model_dump(mode="json"),
        ],
    }


def _observe_result_node(
    state: GovernedAgentGraphState,
    config: RunnableConfig,
) -> GovernedAgentGraphState:
    result = state["tool_results"][-1]
    state = _record_verification_result(state, result)
    if result["status"] == "FAILED":
        return {
            **state,
            "run": {**state["run"], "status": "FAILED"},
            "error": result.get("error"),
        }

    next_index = state.get("current_step_index", 0) + 1
    if _is_login_required_result(state, result):
        return {
            **state,
            "current_step_index": next_index,
            "run": {**state["run"], "status": "BLOCKED"},
            "error": "Login required before governed workflow can continue.",
        }
    if _has_pending_proposals(result):
        return {
            **state,
            "current_step_index": next_index,
            "run": {**state["run"], "status": "WAITING_REVIEW"},
            "interrupt_at": "review",
        }

    return {
        **state,
        "current_step_index": next_index,
        "run": {**state["run"], "status": "RUNNING"},
    }


def _decide_next_step_node(
    state: GovernedAgentGraphState,
    config: RunnableConfig,
) -> GovernedAgentGraphState:
    return state


def _interrupt_for_review_node(
    state: GovernedAgentGraphState,
    config: RunnableConfig,
) -> GovernedAgentGraphState:
    return state


def _verify_result_node(
    state: GovernedAgentGraphState,
    config: RunnableConfig,
) -> GovernedAgentGraphState:
    return state


def _finish_node(
    state: GovernedAgentGraphState,
    config: RunnableConfig,
) -> GovernedAgentGraphState:
    return {**state, "run": {**state["run"], "status": "COMPLETED"}}


def _fail_node(
    state: GovernedAgentGraphState,
    config: RunnableConfig,
) -> GovernedAgentGraphState:
    return {
        **state,
        "run": {**state["run"], "status": "FAILED"},
        "error": state.get("error") or "Governed agent graph failed.",
    }


def _route_after_governance(state: GovernedAgentGraphState) -> str:
    if state.get("stop_after_governance"):
        return "end"
    decision = state.get("governance_decision", {}).get("decision")
    if decision in {"ALLOW", "RECORD_ONLY", "VERIFY_REQUIRED"}:
        return "execute_tool"
    if decision in {"REVIEW_REQUIRED", "APPROVAL_REQUIRED", "BLOCKED"}:
        return "interrupt_for_review"
    return "end"


def _route_after_plan(state: GovernedAgentGraphState) -> str:
    if state["run"]["status"] == "FAILED":
        return "fail"
    return "prepare_tool_call"


def _route_after_observe(state: GovernedAgentGraphState) -> str:
    if state["run"]["status"] == "FAILED":
        return "fail"
    if state["run"]["status"] == "BLOCKED":
        return "end"
    if state.get("interrupt_at") == "review":
        return "end"
    if state.get("stop_after_one_tool"):
        return "end"
    if state.get("current_tool_call", {}).get("tool_name") == "verify_browser_state":
        return "verify_result"
    if state.get("current_step_index", 0) < len(state["plan"]["steps"]):
        return "prepare_tool_call"
    return "finish"


def _route_after_verify(state: GovernedAgentGraphState) -> str:
    if state.get("current_step_index", 0) < len(state["plan"]["steps"]):
        return "prepare_tool_call"
    return "finish"


def _record_verification_result(
    state: GovernedAgentGraphState,
    result: dict[str, Any],
) -> GovernedAgentGraphState:
    if state.get("current_tool_call", {}).get("tool_name") != "verify_browser_state":
        return state
    return {
        **state,
        "verification_result": result.get("output_json", {}),
    }


def _has_pending_proposals(result: dict[str, Any]) -> bool:
    return any(
        proposal.get("status") == "PENDING"
        for proposal in result.get("created_proposals", [])
        if isinstance(proposal, dict)
    )


def _is_login_required_result(
    state: GovernedAgentGraphState,
    result: dict[str, Any],
) -> bool:
    return (
        state.get("current_tool_call", {}).get("tool_name")
        in {"extract_form", "extract_form_fields"}
        and result.get("output_json", {}).get("login_required") is True
    )


def _create_planning_trace_span(config: RunnableConfig, planner_context: dict[str, Any]):
    metadata = config.get("configurable", {}).get("metadata", {})
    db = metadata.get("db")
    task_id = metadata.get("task_id") or planner_context.get("task_id")
    if db is None or not isinstance(task_id, int):
        return None

    try:
        return create_span(
            db,
            task_id=task_id,
            phase=SPAN_PHASE_PLANNING,
            name="agent_planner",
            input={
                "run_id": planner_context["run_id"],
                "goal": planner_context["goal"],
                "planner_mode": planner_context["planner_mode"],
            },
            metadata={"planner_mode": planner_context["planner_mode"]},
        )
    except Exception:
        return None


def _finish_planning_trace_span(
    config: RunnableConfig,
    span,
    *,
    status: str,
    output: dict[str, Any],
    error: str | None = None,
) -> None:
    if span is None:
        return

    db = config.get("configurable", {}).get("metadata", {}).get("db")
    if db is None:
        return

    try:
        finish_span(db, span, status=status, output=output, error_message=error)
    except Exception:
        return


def _status_for_decision(decision: GovernanceDecision) -> tuple[str, str, str | None]:
    if decision.decision == "REVIEW_REQUIRED":
        return "WAITING_REVIEW", "WAITING_REVIEW", "review"
    if decision.decision == "APPROVAL_REQUIRED":
        return "WAITING_APPROVAL", "WAITING_APPROVAL", "approval"
    if decision.decision == "BLOCKED":
        return "BLOCKED", "BLOCKED", None
    return "RUNNING", "PENDING", None


def build_governed_agent_graph(*, checkpointer=None):
    """Build the generic governed agent graph skeleton."""

    workflow = StateGraph(GovernedAgentGraphState)
    workflow.add_node("initialize_run", _initialize_run_node)
    workflow.add_node("plan_next_step", _plan_next_step_node)
    workflow.add_node("prepare_tool_call", _prepare_tool_call_node)
    workflow.add_node("check_governance", _check_governance_node)
    workflow.add_node("interrupt_for_review", _interrupt_for_review_node)
    workflow.add_node("execute_tool", _execute_tool_node)
    workflow.add_node("observe_result", _observe_result_node)
    workflow.add_node("decide_next_step", _decide_next_step_node)
    workflow.add_node("verify_result", _verify_result_node)
    workflow.add_node("finish", _finish_node)
    workflow.add_node("fail", _fail_node)

    workflow.add_edge(START, "initialize_run")
    workflow.add_edge("initialize_run", "plan_next_step")
    workflow.add_conditional_edges(
        "plan_next_step",
        _route_after_plan,
        {
            "prepare_tool_call": "prepare_tool_call",
            "fail": "fail",
        },
    )
    workflow.add_edge("prepare_tool_call", "check_governance")
    workflow.add_conditional_edges(
        "check_governance",
        _route_after_governance,
        {
            "interrupt_for_review": "interrupt_for_review",
            "execute_tool": "execute_tool",
            "end": END,
        },
    )
    workflow.add_edge("interrupt_for_review", END)
    workflow.add_edge("execute_tool", "observe_result")
    workflow.add_edge("observe_result", "decide_next_step")
    workflow.add_conditional_edges(
        "decide_next_step",
        _route_after_observe,
        {
            "prepare_tool_call": "prepare_tool_call",
            "verify_result": "verify_result",
            "finish": "finish",
            "fail": "fail",
            "end": END,
        },
    )
    workflow.add_conditional_edges(
        "verify_result",
        _route_after_verify,
        {
            "prepare_tool_call": "prepare_tool_call",
            "finish": "finish",
        },
    )
    workflow.add_edge("finish", END)
    workflow.add_edge("fail", END)

    return workflow.compile(checkpointer=checkpointer)


def run_to_governance(
    initial_state: GovernedAgentGraphState,
    *,
    runtime: ToolRuntime | None = None,
    planner: AgentPlanner | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the generic graph through governance without executing tools."""

    graph = build_governed_agent_graph()
    config = {
        "configurable": {
            "runtime": runtime or ToolRuntime(),
            "planner": planner,
            "metadata": metadata or {},
        }
    }
    return graph.invoke({**initial_state, "stop_after_governance": True}, config=config)


async def run_allowed_tool_once(
    initial_state: GovernedAgentGraphState,
    *,
    runtime: ToolRuntime | None = None,
    planner: AgentPlanner | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one governed tool step when governance allows it."""

    graph = build_governed_agent_graph()
    config = {
        "configurable": {
            "runtime": runtime or ToolRuntime(),
            "planner": planner,
            "metadata": metadata or {},
        }
    }
    return await graph.ainvoke(
        {**initial_state, "stop_after_one_tool": True},
        config=config,
    )


async def run_allowed_tools_until_pause(
    initial_state: GovernedAgentGraphState,
    *,
    runtime: ToolRuntime | None = None,
    planner: AgentPlanner | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run allowed plan steps until completion or a governance pause."""

    graph = build_governed_agent_graph()
    config = {
        "configurable": {
            "runtime": runtime or ToolRuntime(),
            "planner": planner,
            "metadata": metadata or {},
        }
    }
    return await graph.ainvoke(initial_state, config=config)


async def start_governed_runtime(
    initial_state: GovernedAgentGraphState,
    *,
    runtime: ToolRuntime | None = None,
    planner: AgentPlanner | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Start the checkpointer-backed generic graph until completion or pause."""

    run_id = initial_state.get("run_id") or f"task-{initial_state.get('task_id')}"
    config = {
        "configurable": {
            "thread_id": _thread_id(run_id),
            "runtime": runtime or ToolRuntime(),
            "planner": planner,
            "metadata": metadata or {},
        }
    }
    return await _get_graph().ainvoke(initial_state, config=config)


def get_governed_runtime_state(run_id: str) -> dict[str, Any] | None:
    """Return checkpointer-backed generic graph state for a run, if present."""

    config = {"configurable": {"thread_id": _thread_id(run_id)}}
    try:
        snapshot = _get_graph().get_state(config)
    except Exception:
        return None

    if not snapshot or snapshot.values is None:
        return None

    values = dict(snapshot.values)
    if not values.get("run_id"):
        return None
    return values


async def resume_governed_runtime_from_review(
    run_id: str,
    *,
    runtime: ToolRuntime | None = None,
    planner: AgentPlanner | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resume a checkpointer-backed generic graph from a review pause."""

    state = get_governed_runtime_state(run_id)
    if state is None:
        raise ValueError(f"No governed runtime state found for run {run_id}.")
    if state.get("interrupt_at") != "review":
        raise ValueError(f"Governed runtime {run_id} is not waiting for review.")

    tool_call = state["current_tool_call"]
    approved_ids = list(state.get("approved_tool_call_ids", []))
    if tool_call["id"] not in approved_ids:
        approved_ids.append(tool_call["id"])

    resume_state = {
        **state,
        "approved_tool_call_ids": approved_ids,
        "current_tool_call": {**tool_call, "status": "PENDING"},
        "run": {**state["run"], "status": "RUNNING"},
        "interrupt_at": None,
    }
    config = {
        "configurable": {
            "thread_id": _thread_id(run_id),
            "runtime": runtime or ToolRuntime(),
            "planner": planner,
            "metadata": metadata or {},
        }
    }
    _get_graph().update_state(config, resume_state, as_node="prepare_tool_call")
    return await _get_graph().ainvoke(None, config=config)


__all__ = [
    "GovernedAgentGraphState",
    "_reset_governed_runtime_for_tests",
    "build_governed_agent_graph",
    "get_governed_runtime_state",
    "resume_governed_runtime_from_review",
    "run_allowed_tool_once",
    "run_allowed_tools_until_pause",
    "run_to_governance",
    "start_governed_runtime",
]
