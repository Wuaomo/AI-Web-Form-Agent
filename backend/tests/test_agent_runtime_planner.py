"""Tests for optional structured agent planning."""

import pytest
from types import SimpleNamespace

from app.services.agent_runtime.planner import (
    AgentPlanner,
    FakeStructuredPlannerAdapter,
    OpenAIStructuredPlannerAdapter,
    STRUCTURED_PLANNER_SCHEMA,
)
from app.services.agent_runtime.tool_runtime import AgentTool, ToolExecutionContext, ToolRuntime


async def noop_handler(
    _context: ToolExecutionContext,
    _tool_input: dict[str, object],
) -> dict[str, object]:
    return {}


def make_tool(name: str, input_schema: dict[str, object]) -> AgentTool:
    return AgentTool(
        name=name,
        description=f"{name} test tool",
        input_schema=input_schema,
        output_schema={},
        risk_level="low",
        mutates_browser=False,
        mutates_external_system=False,
        trace_phase="test",
        handler=noop_handler,
    )


def make_runtime() -> ToolRuntime:
    return ToolRuntime(
        [
            make_tool(
                "extract_form",
                {
                    "type": "object",
                    "required": ["url", "profile_id"],
                    "properties": {
                        "url": {"type": "string"},
                        "profile_id": {"type": "integer"},
                    },
                },
            ),
            make_tool(
                "map_fields",
                {
                    "type": "object",
                    "required": ["task_id"],
                    "properties": {"task_id": {"type": "integer"}},
                },
            ),
        ]
    )


def test_llm_structured_output_becomes_agent_plan() -> None:
    """Verify fake structured planner output is normalized into AgentPlan."""

    planner = AgentPlanner(
        runtime=make_runtime(),
        structured_adapter=FakeStructuredPlannerAdapter(
            {
                "steps": [
                    {
                        "step_id": "inspect",
                        "tool_name": "extract_form",
                        "reason": "Inspect the target page.",
                        "input_json": {
                            "url": "https://example.com/form",
                            "profile_id": 7,
                        },
                    },
                    {
                        "step_id": "map",
                        "tool_name": "map_fields",
                        "reason": "Map fields with local rules.",
                        "input_json": {"task_id": 42},
                        "depends_on": ["inspect"],
                    },
                ]
            }
        ),
    )

    plan = planner.create_plan(
        {
            "run_id": "run-1",
            "goal": "Complete this form after review.",
            "target_url": "https://example.com/form",
            "profile_id": 7,
            "task_id": 42,
        },
        mode="llm_structured",
    )

    assert plan.created_by == "llm"
    assert plan.run_id == "run-1"
    assert [step.tool_name for step in plan.steps] == ["extract_form", "map_fields"]


def test_deterministic_planner_keeps_no_key_path_without_adapter() -> None:
    """Verify deterministic planning works without any LLM adapter."""

    plan = AgentPlanner(runtime=make_runtime()).create_plan(
        {
            "run_id": "run-2",
            "goal": "Complete this form after review.",
            "target_url": "https://example.com/form",
            "profile_id": 7,
            "task_id": 42,
        },
        mode="deterministic",
    )

    assert plan.created_by == "deterministic"
    assert [step.tool_name for step in plan.steps] == ["extract_form", "map_fields"]


def test_template_guided_mode_uses_local_plan_contract() -> None:
    """Verify template_guided is exposed without requiring an LLM adapter."""

    plan = AgentPlanner(runtime=make_runtime()).create_plan(
        {
            "run_id": "run-template",
            "goal": "Complete this vendor onboarding form.",
            "target_url": "https://example.com/vendor",
            "profile_id": 7,
            "task_id": 42,
        },
        mode="template_guided",
    )

    assert plan.created_by == "template"
    assert [step.tool_name for step in plan.steps] == ["extract_form", "map_fields"]


def test_llm_structured_planner_rejects_unknown_tools() -> None:
    """Verify model-planned tools must exist in the runtime registry."""

    planner = AgentPlanner(
        runtime=make_runtime(),
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

    with pytest.raises(ValueError, match="Unknown runtime tool: steal_password"):
        planner.create_plan({"run_id": "run-3", "goal": "Inspect safely."}, mode="llm_structured")


def test_llm_structured_planner_rejects_invalid_tool_arguments() -> None:
    """Verify model-planned tool args must match registered input schemas."""

    planner = AgentPlanner(
        runtime=make_runtime(),
        structured_adapter=FakeStructuredPlannerAdapter(
            {
                "steps": [
                    {
                        "step_id": "inspect",
                        "tool_name": "extract_form",
                        "reason": "Inspect the page.",
                        "input_json": {"url": "https://example.com/form"},
                    }
                ]
            }
        ),
    )

    with pytest.raises(ValueError, match="profile_id is required"):
        planner.create_plan({"run_id": "run-4", "goal": "Inspect safely."}, mode="llm_structured")


def test_llm_structured_planner_rejects_tools_outside_allowlist() -> None:
    """Verify model output cannot choose registered tools outside the policy allowlist."""

    planner = AgentPlanner(
        runtime=make_runtime(),
        allowed_tool_names={"extract_form"},
        structured_adapter=FakeStructuredPlannerAdapter(
            {
                "steps": [
                    {
                        "step_id": "map",
                        "tool_name": "map_fields",
                        "reason": "Map fields.",
                        "input_json": {"task_id": 42},
                    }
                ]
            }
        ),
    )

    with pytest.raises(ValueError, match="not allowed for this planner"):
        planner.create_plan({"run_id": "run-5", "goal": "Inspect safely."}, mode="llm_structured")


def test_llm_structured_planner_rejects_unknown_dependencies() -> None:
    """Verify model output cannot depend on a missing plan step."""

    planner = AgentPlanner(
        runtime=make_runtime(),
        structured_adapter=FakeStructuredPlannerAdapter(
            {
                "steps": [
                    {
                        "step_id": "map",
                        "tool_name": "map_fields",
                        "reason": "Map fields.",
                        "input_json": {"task_id": 42},
                        "depends_on": ["inspect"],
                    }
                ]
            }
        ),
    )

    with pytest.raises(ValueError, match="Unknown plan dependency: inspect"):
        planner.create_plan({"run_id": "run-6", "goal": "Inspect safely."}, mode="llm_structured")


def test_openai_structured_planner_adapter_fails_closed_without_api_key() -> None:
    """Verify the OpenAI adapter shell never performs planning when unconfigured."""

    adapter = OpenAIStructuredPlannerAdapter(api_key=None)

    with pytest.raises(RuntimeError, match="not configured"):
        adapter.plan({"goal": "Inspect safely."})


def test_openai_structured_planner_adapter_returns_structured_content() -> None:
    """Verify configured OpenAI adapter delegates to the existing LLM JSON boundary."""

    calls = []

    class FakeLLMClient:
        def complete_json(self, prompt, schema, **kwargs):
            calls.append((prompt, schema, kwargs))
            return SimpleNamespace(
                success=True,
                content={
                    "steps": [
                        {
                            "step_id": "inspect",
                            "tool_name": "extract_form",
                            "reason": "Inspect the page.",
                            "input_json": {
                                "url": "https://example.com/form",
                                "profile_id": 7,
                            },
                        }
                    ]
                },
                reason="ok",
            )

    adapter = OpenAIStructuredPlannerAdapter(api_key="test-key", llm_client=FakeLLMClient())

    output = adapter.plan(
        {
            "goal": "Inspect safely.",
            "target_url": "https://example.com/form",
            "profile_id": 7,
            "task_id": 42,
            "workflow_type": "form_fill",
            "available_tools": [{"name": "extract_form"}],
        }
    )

    assert output["steps"][0]["tool_name"] == "extract_form"
    assert calls[0][1] == STRUCTURED_PLANNER_SCHEMA
    assert calls[0][2]["schema_name"] == "agent_plan"
    assert "Inspect safely." in calls[0][0]
    assert "extract_form" in calls[0][0]


def test_openai_structured_planner_adapter_raises_on_llm_failure() -> None:
    """Verify provider failures do not silently produce an empty plan."""

    class FakeLLMClient:
        def complete_json(self, *_args, **_kwargs):
            return SimpleNamespace(success=False, content=None, reason="rate limited")

    adapter = OpenAIStructuredPlannerAdapter(api_key="test-key", llm_client=FakeLLMClient())

    with pytest.raises(RuntimeError, match="rate limited"):
        adapter.plan({"goal": "Inspect safely."})
