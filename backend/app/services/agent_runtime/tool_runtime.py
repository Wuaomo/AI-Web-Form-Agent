"""Executable typed tools for the agent runtime."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from app.services.agent_runtime.governance import GovernanceEngine
from app.services.agent_runtime.schemas import (
    GovernanceDecision,
    Proposal,
    RiskLevel,
    ToolResult,
    VerificationCandidate,
)
from app.services.workflow_trace_service import create_span, finish_span
from app.workflow_constants import SPAN_STATUS_FAILED, SPAN_STATUS_SUCCESS


ToolHandler = Callable[["ToolExecutionContext", dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolExecutionContext:
    """Minimal execution context shared by runtime tools."""

    run_id: str | None = None
    plan_step_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentTool:
    """One executable runtime tool."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk_level: RiskLevel
    mutates_browser: bool
    mutates_external_system: bool
    trace_phase: str
    handler: ToolHandler


class ToolRuntime:
    """Validate and execute registered agent runtime tools."""

    def __init__(
        self,
        tools: Iterable[AgentTool] = (),
        governance_engine: GovernanceEngine | None = None,
    ) -> None:
        self._tools = {tool.name: tool for tool in tools}
        self._governance_engine = governance_engine or GovernanceEngine()

    def register(self, tool: AgentTool) -> None:
        """Register or replace one runtime tool."""

        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> AgentTool | None:
        """Return a registered runtime tool, if available."""

        return self._tools.get(name)

    def list_tool_metadata(self) -> list[dict[str, Any]]:
        """Return planner-visible metadata for registered runtime tools."""

        return [
            {
                "name": tool.name,
                "description": tool.description,
                "risk_level": tool.risk_level,
                "mutates_browser": tool.mutates_browser,
                "mutates_external_system": tool.mutates_external_system,
                "input_schema": tool.input_schema,
            }
            for tool in self._tools.values()
        ]

    def validate_tool_input(self, tool_name: str, tool_input: dict[str, Any]) -> str | None:
        """Return a validation error for a tool call, if one exists."""

        tool = self.get_tool(tool_name)
        if tool is None:
            return f"Unknown runtime tool: {tool_name}"
        return _validate_input(tool.input_schema, tool_input)

    async def execute(
        self,
        *,
        tool_call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        context: ToolExecutionContext | None = None,
    ) -> ToolResult:
        """Execute one runtime tool and normalize failures."""

        tool = self.get_tool(tool_name)
        if tool is None:
            return _failed_result(
                tool_call_id,
                f"Unknown runtime tool: {tool_name}",
            )

        error = _validate_input(tool.input_schema, tool_input)
        if error:
            return _failed_result(tool_call_id, error)

        execution_context = context or ToolExecutionContext()
        governance_decision = self._governance_engine.evaluate_tool_call(
            tool,
            tool_input,
            tool_call_id=tool_call_id,
            context=execution_context,
        )
        span = _create_trace_span(
            execution_context,
            tool=tool,
            tool_call_id=tool_call_id,
            tool_input=tool_input,
            governance_decision=governance_decision,
        )
        if governance_decision.decision == "BLOCKED":
            error_message = f"Tool call blocked by governance: {governance_decision.reason}"
            _finish_trace_span(
                execution_context,
                span,
                status=SPAN_STATUS_FAILED,
                output={},
                error=error_message,
                latency_ms=0,
            )
            return _failed_result(
                tool_call_id,
                error_message,
                governance_decision=governance_decision,
            )

        if governance_decision.decision in {"REVIEW_REQUIRED", "APPROVAL_REQUIRED"}:
            error_message = f"Tool call paused by governance: {governance_decision.reason}"
            _finish_trace_span(
                execution_context,
                span,
                status=SPAN_STATUS_FAILED,
                output={},
                error=error_message,
                latency_ms=0,
            )
            return _failed_result(
                tool_call_id,
                error_message,
                governance_decision=governance_decision,
            )

        started_at = time.monotonic()
        try:
            output = await tool.handler(execution_context, tool_input)
        except Exception as exc:
            _finish_trace_span(
                execution_context,
                span,
                status=SPAN_STATUS_FAILED,
                output={},
                error=str(exc),
                latency_ms=int((time.monotonic() - started_at) * 1000),
            )
            return _failed_result(
                tool_call_id,
                str(exc),
                governance_decision=governance_decision,
            )

        created_proposals = _pop_created_proposals(output)
        verification_candidates = _pop_verification_candidates(output)
        _finish_trace_span(
            execution_context,
            span,
            status=SPAN_STATUS_SUCCESS,
            output=_summarize_output(output),
            latency_ms=int((time.monotonic() - started_at) * 1000),
        )
        return ToolResult(
            tool_call_id=tool_call_id,
            status="SUCCEEDED",
            governance_decision=governance_decision,
            output_json=output,
            created_proposals=created_proposals,
            verification_candidates=verification_candidates,
        )


def _failed_result(
    tool_call_id: str,
    error: str,
    *,
    governance_decision: GovernanceDecision | None = None,
) -> ToolResult:
    return ToolResult(
        tool_call_id=tool_call_id,
        status="FAILED",
        governance_decision=governance_decision,
        error=error,
    )


def _validate_input(schema: dict[str, Any], tool_input: dict[str, Any]) -> str | None:
    if schema.get("type") == "object" and not isinstance(tool_input, dict):
        return "tool_input must be an object"

    for required_name in schema.get("required", []):
        if required_name not in tool_input:
            return f"{required_name} is required"

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return None

    for name, definition in properties.items():
        if name not in tool_input or not isinstance(definition, dict):
            continue
        expected_type = definition.get("type")
        if expected_type == "string" and not isinstance(tool_input[name], str):
            return f"{name} must be a string"
        if expected_type == "integer" and (
            not isinstance(tool_input[name], int) or isinstance(tool_input[name], bool)
        ):
            return f"{name} must be an integer"

    return None


def _create_trace_span(
    context: ToolExecutionContext,
    *,
    tool: AgentTool,
    tool_call_id: str,
    tool_input: dict[str, Any],
    governance_decision: GovernanceDecision,
):
    db = context.metadata.get("db")
    task_id = _task_id(tool_input, context)
    if db is None or task_id is None:
        return None

    try:
        return create_span(
            db,
            task_id=task_id,
            phase=tool.trace_phase,
            name=tool.name,
            input={"tool_call_id": tool_call_id, **tool_input},
            metadata={
                "risk_level": tool.risk_level,
                "mutates_browser": tool.mutates_browser,
                "mutates_external_system": tool.mutates_external_system,
                "governance_decision": governance_decision.model_dump(mode="json"),
            },
        )
    except Exception:
        return None


def _finish_trace_span(
    context: ToolExecutionContext,
    span,
    *,
    status: str,
    output: dict[str, Any],
    latency_ms: int,
    error: str | None = None,
) -> None:
    if span is None:
        return

    db = context.metadata.get("db")
    if db is None:
        return

    try:
        finish_span(
            db,
            span,
            status=status,
            output=output,
            latency_ms=latency_ms,
            error_message=error,
        )
    except Exception:
        return


def _task_id(
    tool_input: dict[str, Any],
    context: ToolExecutionContext,
) -> int | None:
    raw_task_id = tool_input.get("task_id", context.metadata.get("task_id"))
    if isinstance(raw_task_id, int) and not isinstance(raw_task_id, bool):
        return raw_task_id
    return None


def _summarize_output(output: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in output.items()
        if isinstance(value, str | int | float | bool) or value is None
    }


def _pop_verification_candidates(output: dict[str, Any]) -> list[VerificationCandidate]:
    raw = output.pop("_verification_candidates", [])
    if not isinstance(raw, list):
        return []
    return [
        VerificationCandidate.model_validate(item)
        for item in raw
        if isinstance(item, dict)
    ]


def _pop_created_proposals(output: dict[str, Any]) -> list[Proposal]:
    raw = output.pop("_created_proposals", [])
    if not isinstance(raw, list):
        return []
    return [Proposal.model_validate(item) for item in raw if isinstance(item, dict)]


__all__ = [
    "AgentTool",
    "ToolExecutionContext",
    "ToolRuntime",
]
