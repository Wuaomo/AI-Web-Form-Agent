"""Planner adapters for the governed agent runtime."""

from __future__ import annotations

from typing import Any, Protocol

from app.services.agent_runtime.schemas import AgentPlan, PlannedToolCall, RunMode
from app.services.agent_runtime.tool_runtime import ToolRuntime
from app.services.llm_client import get_llm_client


STRUCTURED_PLANNER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "step_id": {"type": "string"},
                    "tool_name": {"type": "string"},
                    "reason": {"type": "string"},
                    "input_json": {"type": "object"},
                    "risk_level": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "blocked"],
                    },
                    "expected_evidence": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "depends_on": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["step_id", "tool_name", "reason", "input_json"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["steps"],
    "additionalProperties": False,
}


class StructuredPlannerAdapter(Protocol):
    """Adapter contract for model-driven structured planning."""

    def plan(self, context: dict[str, Any]) -> dict[str, Any]:
        """Return a structured plan payload."""


class FakeStructuredPlannerAdapter:
    """Schema-shaped planner test double for llm_structured mode."""

    def __init__(self, output: dict[str, Any]) -> None:
        self._output = output

    def plan(self, _context: dict[str, Any]) -> dict[str, Any]:
        """Return the configured fake model output."""

        return self._output


class OpenAIStructuredPlannerAdapter:
    """OpenAI structured planner adapter using the existing LLM client boundary."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        llm_client: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model or "gpt-5.6-terra"
        self._llm_client = llm_client

    def plan(self, context: dict[str, Any]) -> dict[str, Any]:
        """Request a structured plan from OpenAI through LLMClient."""

        if not self.api_key:
            raise RuntimeError("OpenAI structured planner is not configured")

        result = (self._llm_client or get_llm_client(provider="openai")).complete_json(
            _planner_prompt(context),
            STRUCTURED_PLANNER_SCHEMA,
            task_id=context.get("task_id"),
            db=context.get("db"),
            instructions=(
                "You create safe, minimal, schema-valid browser workflow plans. "
                "Use only listed tools. Browser writes still require governance."
            ),
            schema_name="agent_plan",
        )
        if not result.success:
            raise RuntimeError(result.reason or "OpenAI structured planner failed")
        if not isinstance(result.content, dict):
            raise RuntimeError("OpenAI structured planner returned invalid content")
        return result.content


class AgentPlanner:
    """Create AgentPlan objects from deterministic or structured planner modes."""

    def __init__(
        self,
        *,
        runtime: ToolRuntime | None = None,
        allowed_tool_names: set[str] | None = None,
        structured_adapter: StructuredPlannerAdapter | None = None,
    ) -> None:
        self._runtime = runtime or ToolRuntime()
        self._allowed_tool_names = allowed_tool_names
        self._structured_adapter = structured_adapter

    def create_plan(
        self,
        context: dict[str, Any],
        *,
        mode: RunMode = "deterministic",
    ) -> AgentPlan:
        """Create a validated plan for the selected planner mode."""

        if mode == "llm_structured":
            return self._create_structured_plan(context)
        return self._create_deterministic_plan({**context, "planner_mode": mode})

    def _create_deterministic_plan(self, context: dict[str, Any]) -> AgentPlan:
        plan_steps = context.get("plan_steps") or default_plan_steps(context)
        created_by = (
            "template" if context.get("planner_mode") == "template_guided" else "deterministic"
        )
        plan = AgentPlan(
            id=f"{context['run_id']}:plan:1",
            run_id=context["run_id"],
            version=1,
            goal=context["goal"],
            steps=[PlannedToolCall(**step) for step in plan_steps],
            created_by=created_by,
        )
        return plan

    def _create_structured_plan(self, context: dict[str, Any]) -> AgentPlan:
        if self._structured_adapter is None:
            raise ValueError("llm_structured planner requires a structured adapter")

        output = self._structured_adapter.plan(context)
        if not isinstance(output, dict):
            raise ValueError("structured planner output must be an object")

        plan = AgentPlan(
            **{
                **output,
                "id": output.get("id") or f"{context['run_id']}:plan:1",
                "run_id": context["run_id"],
                "version": output.get("version", 1),
                "goal": output.get("goal") or context["goal"],
                "created_by": "llm",
            }
        )
        self._validate_plan_tools(plan)
        return plan

    def _validate_plan_tools(self, plan: AgentPlan) -> None:
        step_ids = {step.step_id for step in plan.steps}
        for step in plan.steps:
            for dependency in step.depends_on:
                if dependency not in step_ids:
                    raise ValueError(f"Unknown plan dependency: {dependency}")
            if (
                self._allowed_tool_names is not None
                and step.tool_name not in self._allowed_tool_names
            ):
                raise ValueError(f"Tool {step.tool_name} is not allowed for this planner")
            error = self._runtime.validate_tool_input(step.tool_name, step.input_json)
            if error:
                raise ValueError(error)


def default_plan_steps(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the local no-key default plan."""

    return [
        {
            "step_id": "extract_form",
            "tool_name": "extract_form",
            "reason": "Inspect the page structure before proposing any browser changes.",
            "input_json": {
                "task_id": context.get("task_id"),
                "url": context.get("target_url") or "",
                "profile_id": context.get("profile_id"),
            },
            "risk_level": "low",
            "expected_evidence": ["fields", "login_required"],
        },
        {
            "step_id": "map_fields",
            "tool_name": "map_fields",
            "reason": "Map extracted fields with deterministic local rules.",
            "input_json": {"task_id": context.get("task_id")},
            "risk_level": "medium",
            "expected_evidence": ["mapped_count"],
            "depends_on": ["extract_form"],
        },
    ]


def _planner_prompt(context: dict[str, Any]) -> str:
    tools = context.get("available_tools") or []
    return (
        f"Goal: {context.get('goal', '')}\n"
        f"Target URL: {context.get('target_url', '')}\n"
        f"Workflow type: {context.get('workflow_type', '')}\n"
        f"Task ID: {context.get('task_id', '')}\n"
        f"Profile ID: {context.get('profile_id', '')}\n"
        f"Available tools: {tools}\n"
        "Return the shortest safe plan as JSON."
    )


__all__ = [
    "AgentPlanner",
    "FakeStructuredPlannerAdapter",
    "OpenAIStructuredPlannerAdapter",
    "STRUCTURED_PLANNER_SCHEMA",
    "StructuredPlannerAdapter",
    "default_plan_steps",
]
