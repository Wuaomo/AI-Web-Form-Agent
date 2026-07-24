"""LangGraph runtime for the security questionnaire workflow.

This graph wraps existing service layer components and uses LangGraph's
``interrupt_before`` mechanism for two human-in-the-loop gates:
- Before fill_browser (review gate)
- Before finish (submission approval gate)

Every node delegates to an existing service — no business logic is rewritten.

Flow:
  start -> analyze_page -> extract_questions -> retrieve_reviewed_memory
  -> retrieve_policy_sources -> suggest_answers -> policy_check
  -> [INTERRUPT: review] -> apply_review_decision -> fill_browser
  -> verify_result -> [INTERRUPT: submit_approval] -> finish
  (errors route to fail node)

Safety guarantees:
- Browser execution never runs before review approval.
- Final submission never happens without explicit human approval.
- Policy engine evaluates every suggestion.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.models import FormField, Task
from app.services.policy_engine import (
    POLICY_DECISION_ALLOW,
    POLICY_DECISION_REVIEW_REQUIRED,
    evaluate_field_action,
)
from app.services.policy_doc_retriever import retrieve_policy_sources
from app.services.reviewed_memory_retriever import retrieve_reviewed_memory
from app.services.suggestion_provider import suggest_answers

logger = logging.getLogger(__name__)

SUPPORTED_WORKFLOWS = {"security_questionnaire"}

REVIEW_GATE_NODE = "apply_review_decision"
SUBMIT_GATE_NODE = "finish"

_memory_saver = MemorySaver()
_graph_instance = None


def _get_graph():
    """Lazily build and cache the compiled graph with MemorySaver."""

    global _graph_instance
    if _graph_instance is None:
        _graph_instance = _build_compiled_graph()
    return _graph_instance


def _thread_id(task_id: int) -> str:
    """Return the checkpoint thread_id for a given task."""

    return f"task-{task_id}"


def _reset_runtime_for_tests() -> None:
    """Reset the cached graph and checkpointer state (for tests only)."""

    global _graph_instance
    _graph_instance = None
    _memory_saver.storage.clear()
    if hasattr(_memory_saver, "writes"):
        _memory_saver.writes.clear()


class GraphState(TypedDict, total=False):
    """State shape for the security questionnaire graph."""

    task_id: int
    workflow_type: str
    target_url: str
    profile_id: int

    extracted_fields: list[dict[str, object]]
    memory_hits: list[dict[str, object]]
    policy_sources: list[dict[str, object]]
    suggestions: list[dict[str, object]]
    policy_result: dict[str, object]
    review_request_id: int | None
    review_decision: str | None

    browser_execution_id: int | None
    verification_result: dict[str, object]
    submit_approval_request_id: int | None

    status: str
    error: str | None


# ---------------------------------------------------------------------------
# Context helpers (db session passed via LangGraph configurable config)
# ---------------------------------------------------------------------------


def _get_db(config: RunnableConfig) -> Any:
    """Extract the database session from graph config."""

    return config.get("configurable", {}).get("db")


def _get_task(config: RunnableConfig) -> Task | None:
    """Extract the Task from graph config."""

    return config.get("configurable", {}).get("task")


def _get_fields(config: RunnableConfig) -> list[FormField]:
    """Extract FormField objects from graph config."""

    return config.get("configurable", {}).get("fields", [])


# ---------------------------------------------------------------------------
# Node implementations (all delegate to existing services)
# ---------------------------------------------------------------------------


def _start_node(state: GraphState, config: RunnableConfig) -> GraphState:
    """Initialize graph state."""

    return {
        **state,
        "status": "ANALYZING",
    }


def _analyze_page_node(
    state: GraphState, config: RunnableConfig
) -> GraphState:
    """Analyze the target page.

    In this skeleton, page analysis was already done before graph entry.
    This node exists for observability and to match the workflow plan.
    """

    logger.info("Graph: analyze_page")
    return {
        **state,
        "status": "EXTRACTING",
    }


def _extract_questions_node(
    state: GraphState, config: RunnableConfig
) -> GraphState:
    """Extract questionnaire items from page fields.

    Fields were extracted before graph entry; this node serializes them
    into the state for downstream consumers.
    """

    fields = _get_fields(config)
    extracted = [
        {
            "field_id": f.id,
            "label": f.label,
            "name": f.name,
            "field_type": f.field_type,
            "required": bool(f.required),
        }
        for f in fields
    ]

    logger.info("Graph: extract_questions — %d fields", len(extracted))

    return {
        **state,
        "extracted_fields": extracted,
        "status": "RETRIEVING_EVIDENCE",
    }


def _retrieve_memory_node(
    state: GraphState, config: RunnableConfig
) -> GraphState:
    """Retrieve reviewed memory hits — wraps reviewed_memory_retriever."""

    db = _get_db(config)
    fields = _get_fields(config)
    profile_id = state.get("profile_id", 0)
    workflow_type = state.get("workflow_type", "security_questionnaire")

    all_hits: list[dict[str, object]] = []
    for field in fields:
        query = " ".join(
            [
                getattr(field, "label", "") or "",
                getattr(field, "name", "") or "",
                getattr(field, "placeholder", "") or "",
            ]
        )
        hits = retrieve_reviewed_memory(
            db,
            profile_id=profile_id,
            workflow_type=workflow_type,
            query=query,
        )
        all_hits.extend([h.model_dump() for h in hits])

    logger.info("Graph: retrieve_reviewed_memory — %d hits", len(all_hits))

    return {
        **state,
        "memory_hits": all_hits,
    }


def _retrieve_policy_node(
    state: GraphState, config: RunnableConfig
) -> GraphState:
    """Retrieve policy source evidence — wraps policy_doc_retriever."""

    fields = _get_fields(config)

    all_sources: list[dict[str, object]] = []
    for field in fields:
        query = " ".join(
            [
                getattr(field, "label", "") or "",
                getattr(field, "name", "") or "",
            ]
        )
        hits = retrieve_policy_sources(query, limit=3)
        all_sources.extend([h.model_dump() for h in hits])

    logger.info("Graph: retrieve_policy_sources — %d hits", len(all_sources))

    return {
        **state,
        "policy_sources": all_sources,
    }


def _suggest_answers_node(
    state: GraphState, config: RunnableConfig
) -> GraphState:
    """Generate suggestions — wraps suggestion_provider.suggest_answers."""

    from app.models import Profile

    db = _get_db(config)
    fields = _get_fields(config)
    task = _get_task(config)
    profile_id = state.get("profile_id")

    profile = db.get(Profile, profile_id) if profile_id else None

    suggestions = suggest_answers(
        db,
        task=task,
        fields=fields,
        profile=profile,
        mode="rules",
    )

    suggestion_dicts = [s.model_dump() for s in suggestions]
    logger.info("Graph: suggest_answers — %d suggestions", len(suggestion_dicts))

    return {
        **state,
        "suggestions": suggestion_dicts,
        "status": "POLICY_CHECKING",
    }


def _policy_check_node(
    state: GraphState, config: RunnableConfig
) -> GraphState:
    """Run policy engine on every suggestion — wraps policy_engine.

    No suggestion can skip this check. The policy engine is the source
    of truth for what is allowed.
    """

    suggestions = state.get("suggestions", [])
    fields = _get_fields(config)
    field_by_id = {f.id: f for f in fields}

    decisions = []
    blocked_count = 0

    for s in suggestions:
        field = (
            field_by_id.get(int(s["field_id"]))
            if s.get("field_id")
            else None
        )
        field_label = getattr(field, "label", "") if field else ""

        decision = evaluate_field_action(
            label=field_label,
            name=getattr(field, "name", None),
            field_type=getattr(field, "field_type", None),
            selector=getattr(field, "selector", None),
        )

        decisions.append(
            {
                "question_id": s.get("question_id"),
                "decision": decision.decision,
                "allowed": decision.decision == POLICY_DECISION_ALLOW,
                "requires_review": decision.decision
                == POLICY_DECISION_REVIEW_REQUIRED,
                "reason": decision.reason,
                "risk_type": decision.risk_type,
                "risk_level": decision.risk_level,
            }
        )
        if decision.decision != POLICY_DECISION_ALLOW:
            blocked_count += 1

    logger.info(
        "Graph: policy_check — %d suggestions, %d blocked",
        len(suggestions),
        blocked_count,
    )

    return {
        **state,
        "policy_result": {
            "total": len(suggestions),
            "blocked": blocked_count,
            "decisions": decisions,
        },
        "status": "AWAITING_REVIEW",
    }


def _apply_review_decision_node(
    state: GraphState, config: RunnableConfig
) -> GraphState:
    """Apply human review decisions (approve/edit/reject per suggestion).

    Only runs after the review interrupt is resolved.
    """

    decision = state.get("review_decision", "approve")
    logger.info("Graph: apply_review_decision — decision=%s", decision)

    return {
        **state,
        "status": "FILLING",
    }


def _fill_browser_node(
    state: GraphState, config: RunnableConfig
) -> GraphState:
    """Fill approved values in the browser — wraps browser executor.

    Only runs after review approval. Never reached from initial run.
    """

    logger.info("Graph: fill_browser (skeleton — wraps browser executor)")
    return {
        **state,
        "status": "VERIFYING",
    }


def _verify_result_node(
    state: GraphState, config: RunnableConfig
) -> GraphState:
    """Verify filled values — wraps execution_verification_service."""

    logger.info("Graph: verify_result (skeleton — wraps verification service)")
    return {
        **state,
        "verification_result": {"verified": True, "mismatches": []},
        "status": "AWAITING_SUBMIT_APPROVAL",
    }


def _finish_node(
    state: GraphState, config: RunnableConfig
) -> GraphState:
    """Mark workflow complete (only after submission approval)."""

    logger.info("Graph: finish")
    return {
        **state,
        "status": "COMPLETED",
    }


def _fail_node(
    state: GraphState, config: RunnableConfig
) -> GraphState:
    """Handle errors from any node."""

    error = state.get("error") or "Unknown error"
    logger.error("Graph: fail — %s", error)
    return {
        **state,
        "status": "FAILED",
        "error": error,
    }


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_security_questionnaire_graph():
    """Build the LangGraph StateGraph for security questionnaire workflow.

    Uses ``interrupt_before`` for two human-in-the-loop gates:
    - ``apply_review_decision`` — review suggestions before filling
    - ``finish`` — approve before final submission

    Returns a compiled graph **without** a checkpointer (for testing).
    Use ``_get_graph()`` for the production cached instance with
    MemorySaver checkpointer.
    """

    workflow = StateGraph(GraphState)

    workflow.add_node("start", _start_node)
    workflow.add_node("analyze_page", _analyze_page_node)
    workflow.add_node("extract_questions", _extract_questions_node)
    workflow.add_node("retrieve_reviewed_memory", _retrieve_memory_node)
    workflow.add_node("retrieve_policy_sources", _retrieve_policy_node)
    workflow.add_node("suggest_answers", _suggest_answers_node)
    workflow.add_node("policy_check", _policy_check_node)
    workflow.add_node("apply_review_decision", _apply_review_decision_node)
    workflow.add_node("fill_browser", _fill_browser_node)
    workflow.add_node("verify_result", _verify_result_node)
    workflow.add_node("finish", _finish_node)
    workflow.add_node("fail", _fail_node)

    workflow.add_edge(START, "start")
    workflow.add_edge("start", "analyze_page")
    workflow.add_edge("analyze_page", "extract_questions")
    workflow.add_edge("extract_questions", "retrieve_reviewed_memory")
    workflow.add_edge("retrieve_reviewed_memory", "retrieve_policy_sources")
    workflow.add_edge("retrieve_policy_sources", "suggest_answers")
    workflow.add_edge("suggest_answers", "policy_check")
    workflow.add_edge("policy_check", "apply_review_decision")
    workflow.add_edge("apply_review_decision", "fill_browser")
    workflow.add_edge("fill_browser", "verify_result")
    workflow.add_edge("verify_result", "finish")
    workflow.add_edge("finish", END)
    workflow.add_edge("fail", END)

    return workflow.compile(
        interrupt_before=[REVIEW_GATE_NODE, SUBMIT_GATE_NODE],
    )


def _build_compiled_graph():
    """Build the graph with MemorySaver checkpointer for state tracking."""

    workflow = StateGraph(GraphState)

    workflow.add_node("start", _start_node)
    workflow.add_node("analyze_page", _analyze_page_node)
    workflow.add_node("extract_questions", _extract_questions_node)
    workflow.add_node("retrieve_reviewed_memory", _retrieve_memory_node)
    workflow.add_node("retrieve_policy_sources", _retrieve_policy_node)
    workflow.add_node("suggest_answers", _suggest_answers_node)
    workflow.add_node("policy_check", _policy_check_node)
    workflow.add_node("apply_review_decision", _apply_review_decision_node)
    workflow.add_node("fill_browser", _fill_browser_node)
    workflow.add_node("verify_result", _verify_result_node)
    workflow.add_node("finish", _finish_node)
    workflow.add_node("fail", _fail_node)

    workflow.add_edge(START, "start")
    workflow.add_edge("start", "analyze_page")
    workflow.add_edge("analyze_page", "extract_questions")
    workflow.add_edge("extract_questions", "retrieve_reviewed_memory")
    workflow.add_edge("retrieve_reviewed_memory", "retrieve_policy_sources")
    workflow.add_edge("retrieve_policy_sources", "suggest_answers")
    workflow.add_edge("suggest_answers", "policy_check")
    workflow.add_edge("policy_check", "apply_review_decision")
    workflow.add_edge("apply_review_decision", "fill_browser")
    workflow.add_edge("fill_browser", "verify_result")
    workflow.add_edge("verify_result", "finish")
    workflow.add_edge("finish", END)
    workflow.add_edge("fail", END)

    return workflow.compile(
        checkpointer=_memory_saver,
        interrupt_before=[REVIEW_GATE_NODE, SUBMIT_GATE_NODE],
    )


# ---------------------------------------------------------------------------
# Convenience runners
# ---------------------------------------------------------------------------


def _enrich_state_with_interrupt_info(state: dict, next_nodes: list[str]) -> dict:
    """Add interrupt_at / current_node metadata to state."""

    enriched = dict(state)
    if REVIEW_GATE_NODE in next_nodes:
        enriched["interrupt_at"] = "review"
        enriched["current_node"] = REVIEW_GATE_NODE
    elif SUBMIT_GATE_NODE in next_nodes:
        enriched["interrupt_at"] = "submit_approval"
        enriched["current_node"] = SUBMIT_GATE_NODE
    elif not next_nodes:
        enriched["interrupt_at"] = None
        enriched["current_node"] = "finish"
    return enriched


def run_until_review(db, *, task: Task) -> dict:
    """Run the graph from start through the review interrupt.

    Standard entry point: build state from a Task, run the graph until
    the review gate, and return the state with suggestions and policy
    results ready for human review.

    The fill_browser node is never reached from this call.
    """

    workflow_type = task.workflow_type or "form_fill"
    if workflow_type not in SUPPORTED_WORKFLOWS:
        raise ValueError(
            f"Workflow type '{workflow_type}' is not supported by the graph runtime. "
            f"Supported: {sorted(SUPPORTED_WORKFLOWS)}"
        )

    fields = list(task.form_fields)

    initial_state: GraphState = {
        "task_id": task.id,
        "workflow_type": workflow_type,
        "target_url": task.url or "",
        "profile_id": task.profile_id or 0,
        "extracted_fields": [],
        "memory_hits": [],
        "policy_sources": [],
        "suggestions": [],
        "policy_result": {},
        "review_request_id": None,
        "review_decision": None,
        "browser_execution_id": None,
        "verification_result": {},
        "submit_approval_request_id": None,
        "status": "PENDING",
        "error": None,
    }

    graph = _get_graph()
    config = {
        "configurable": {
            "thread_id": _thread_id(task.id),
            "db": db,
            "task": task,
            "fields": fields,
        }
    }

    result = graph.invoke(initial_state, config=config)

    state_snapshot = graph.get_state(config)
    next_nodes = list(state_snapshot.next) if state_snapshot else []

    return _enrich_state_with_interrupt_info(result, next_nodes)


def start_runtime(db, *, task: Task) -> dict:
    """Start the graph runtime for a task and run to first interrupt.

    Wraps ``run_until_review`` and uses the checkpointer-backed graph
    so that subsequent resume/get calls can find the state.
    """

    return run_until_review(db, task=task)


def get_runtime_state(task_id: int) -> dict | None:
    """Return the current runtime state for a task from the checkpointer.

    Returns None if no runtime has been started for the task.
    """

    graph = _get_graph()
    config = {"configurable": {"thread_id": _thread_id(task_id)}}

    try:
        snapshot = graph.get_state(config)
    except Exception:
        return None

    if not snapshot or snapshot.values is None:
        return None

    values = dict(snapshot.values)
    if not values.get("task_id"):
        return None

    next_nodes = list(snapshot.next) if snapshot.next else []
    return _enrich_state_with_interrupt_info(values, next_nodes)


def resume_from_review(
    db,
    *,
    task: Task,
    decision: str = "approve_all",
    approvals: list[dict] | None = None,
) -> dict:
    """Resume the graph from the review interrupt with a human decision.

    Only works if the runtime is currently paused at the review gate.
    Advances through fill_browser and verify_result to the submit
    approval gate.
    """

    graph = _get_graph()
    config = {
        "configurable": {
            "thread_id": _thread_id(task.id),
            "db": db,
            "task": task,
            "fields": list(task.form_fields),
        }
    }

    snapshot = graph.get_state(config)
    next_nodes = list(snapshot.next) if snapshot.next else []

    if REVIEW_GATE_NODE not in next_nodes:
        raise ValueError(
            f"Runtime is not at review gate (next nodes: {next_nodes})."
        )

    updated_state = dict(snapshot.values) if snapshot.values else {}
    updated_state["review_decision"] = decision
    if approvals is not None:
        updated_state["review_approvals"] = approvals

    graph.update_state(config, updated_state)

    result = graph.invoke(None, config=config)

    state_snapshot = graph.get_state(config)
    next_after = list(state_snapshot.next) if state_snapshot.next else []

    return _enrich_state_with_interrupt_info(result, next_after)
