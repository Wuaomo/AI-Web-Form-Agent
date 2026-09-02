"""Tests for executable agent runtime tools."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FormField, Profile, Task
from app.services.agent_runtime.tool_runtime import (
    AgentTool,
    ToolExecutionContext,
    ToolRuntime,
)
from app.services.agent_runtime.tools import build_default_tool_runtime
from app.services.workflow_trace_service import list_spans_for_task


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_tool_runtime_rejects_unknown_tools() -> None:
    """Verify unknown runtime tools return structured failures."""

    runtime = ToolRuntime()

    result = await runtime.execute(
        tool_call_id="call-1",
        tool_name="does_not_exist",
        tool_input={},
    )

    assert result.status == "FAILED"
    assert result.tool_call_id == "call-1"
    assert result.error == "Unknown runtime tool: does_not_exist"


@pytest.mark.anyio
async def test_extract_form_requires_url_and_profile_id() -> None:
    """Verify invalid tool input fails before browser work starts."""

    extractor = AsyncMock()
    runtime = build_default_tool_runtime(extract_form_analysis_handler=extractor)

    result = await runtime.execute(
        tool_call_id="call-1",
        tool_name="extract_form",
        tool_input={"url": "https://example.com/form"},
    )

    assert result.status == "FAILED"
    assert "profile_id is required" in result.error
    extractor.assert_not_awaited()


@pytest.mark.anyio
async def test_extract_form_wraps_form_extractor_result() -> None:
    """Verify extract_form returns normalized ToolResult output."""

    extracted_field = SimpleNamespace(
        element_ref="field_1",
        form_title="Application",
        section_title="Contact",
        label="Email",
        selector="#email",
        field_type="email",
        placeholder="you@example.com",
        name="email",
        html_id="email",
        current_value=None,
        required=True,
        options=[],
    )
    extractor = AsyncMock(
        return_value=SimpleNamespace(fields=[extracted_field], login_required=False)
    )
    runtime = build_default_tool_runtime(extract_form_analysis_handler=extractor)

    result = await runtime.execute(
        tool_call_id="call-1",
        tool_name="extract_form",
        tool_input={"url": "https://example.com/form", "profile_id": 7},
    )

    assert result.status == "SUCCEEDED"
    assert result.output_json == {
        "fields": [
            {
                "element_ref": "field_1",
                "form_title": "Application",
                "section_title": "Contact",
                "label": "Email",
                "selector": "#email",
                "field_type": "email",
                "placeholder": "you@example.com",
                "name": "email",
                "html_id": "email",
                "current_value": None,
                "required": True,
                "options": [],
            }
        ],
        "field_count": 1,
        "login_required": False,
    }
    extractor.assert_awaited_once_with("https://example.com/form", 7)


@pytest.mark.anyio
async def test_extract_form_fields_is_alias_for_extract_form() -> None:
    """Verify the runtime exposes both RFC tool names for the same wrapper."""

    extractor = AsyncMock(return_value=SimpleNamespace(fields=[], login_required=True))
    runtime = build_default_tool_runtime(extract_form_analysis_handler=extractor)

    result = await runtime.execute(
        tool_call_id="call-1",
        tool_name="extract_form_fields",
        tool_input={"url": "https://example.com/form", "profile_id": 7},
    )

    assert result.status == "SUCCEEDED"
    assert result.output_json == {
        "fields": [],
        "field_count": 0,
        "login_required": True,
    }
    extractor.assert_awaited_once_with("https://example.com/form", 7)


@pytest.mark.anyio
async def test_map_fields_uses_rules_mapper_without_llm() -> None:
    """Verify map_fields wraps the existing local rules mapper."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        profile = Profile(
            profile_name="Runtime profile",
            email="ada@example.com",
        )
        task = Task(
            url="https://example.com/form",
            profile=profile,
            status="MAPPING_READY",
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

        runtime = build_default_tool_runtime()

        result = await runtime.execute(
            tool_call_id="call-1",
            tool_name="map_fields",
            tool_input={"task_id": task.id},
            context=ToolExecutionContext(metadata={"db": session}),
        )

        assert result.status == "SUCCEEDED"
        assert result.output_json["mode"] == "rules"
        assert result.output_json["field_count"] == 1
        assert result.output_json["mapped_count"] == 1
        assert result.output_json["fields"] == [
            {
                "id": field.id,
                "element_ref": None,
                "label": "Email address",
                "selector": "#email",
                "field_type": "email",
                "required": True,
                "mapped_profile_key": "email",
                "mapped_value": "ada@example.com",
                "confidence": 0.99,
            }
        ]
        session.refresh(field)
        assert field.mapped_profile_key == "email"
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.mark.anyio
async def test_generate_field_mappings_is_alias_for_map_fields() -> None:
    """Verify both RFC mapping tool names share the same rules wrapper."""

    mapped_field = SimpleNamespace(
        id=11,
        element_ref="field_1",
        label="Email",
        selector="#email",
        field_type="email",
        required=True,
        mapped_profile_key="email",
        mapped_value="ada@example.com",
        confidence=0.99,
    )

    def mapper(task_id: int, db=None):
        assert task_id == 42
        assert db == "session"
        return [mapped_field]

    runtime = build_default_tool_runtime(map_fields_by_rules_handler=mapper)

    result = await runtime.execute(
        tool_call_id="call-1",
        tool_name="generate_field_mappings",
        tool_input={"task_id": 42},
        context=ToolExecutionContext(metadata={"db": "session"}),
    )

    assert result.status == "SUCCEEDED"
    assert result.output_json["fields"][0]["mapped_profile_key"] == "email"


@pytest.mark.anyio
async def test_fill_form_wraps_browser_executor_after_approval() -> None:
    """Verify fill_form is available as an approved browser-write tool."""

    screenshot = SimpleNamespace(id=12)
    verification = [
        SimpleNamespace(
            field_id=1,
            selector="#email",
            expected_value="ada@example.com",
            status="VERIFIED",
        ),
        SimpleNamespace(
            field_id=2,
            selector="#secret",
            expected_value=None,
            status="SKIPPED",
        ),
    ]
    fill_handler = AsyncMock(return_value=(screenshot, verification))
    fields = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    runtime = build_default_tool_runtime(fill_form_handler=fill_handler)

    result = await runtime.execute(
        tool_call_id="task-7:fill_form",
        tool_name="fill_form",
        tool_input={
            "task_id": 7,
            "url": "https://example.com/form",
            "profile_id": 3,
            "fields": fields,
        },
        context=ToolExecutionContext(
            metadata={"approved_tool_call_ids": ["task-7:fill_form"]}
        ),
    )

    assert result.status == "SUCCEEDED"
    assert result.governance_decision is not None
    assert result.governance_decision.decision == "VERIFY_REQUIRED"
    assert result.output_json == {
        "filled_count": 2,
        "screenshot_id": 12,
        "verification_count": 2,
    }
    assert [candidate.target_ref for candidate in result.verification_candidates] == [
        "1",
        "2",
    ]
    assert result.verification_candidates[0].run_id == "task-7"
    assert result.verification_candidates[0].verification_type == "field_value"
    assert result.verification_candidates[0].expected == "ada@example.com"
    assert result.verification_candidates[0].screenshot_id == 12
    fill_handler.assert_awaited_once_with(
        task_id=7,
        url="https://example.com/form",
        profile_id=3,
        fields=fields,
        stage="filled_form",
        db=None,
    )


@pytest.mark.anyio
async def test_submit_form_wraps_browser_executor_after_approval() -> None:
    """Verify submit_form is available as an approved high-risk browser tool."""

    screenshot = SimpleNamespace(id=13)
    submit_handler = AsyncMock(return_value=screenshot)
    fields = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    runtime = build_default_tool_runtime(submit_form_handler=submit_handler)

    result = await runtime.execute(
        tool_call_id="task-7:submit_form",
        tool_name="submit_form",
        tool_input={
            "task_id": 7,
            "url": "https://example.com/form",
            "profile_id": 3,
            "fields": fields,
        },
        context=ToolExecutionContext(
            metadata={"approved_tool_call_ids": ["task-7:submit_form"]}
        ),
    )

    assert result.status == "SUCCEEDED"
    assert result.governance_decision is not None
    assert result.governance_decision.decision == "VERIFY_REQUIRED"
    assert result.output_json == {
        "submitted": True,
        "field_count": 2,
        "screenshot_id": 13,
    }
    submit_handler.assert_awaited_once_with(
        task_id=7,
        url="https://example.com/form",
        profile_id=3,
        fields=fields,
        stage="submitted_form",
        db=None,
    )


@pytest.mark.anyio
async def test_tool_runtime_records_success_trace_when_task_context_exists() -> None:
    """Verify successful tool calls create and finish workflow trace spans."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        profile = Profile(profile_name="Trace profile")
        task = Task(url="https://example.com/form", profile=profile)
        session.add(task)
        session.commit()

        async def handler(
            _context: ToolExecutionContext,
            _tool_input: dict[str, object],
        ) -> dict[str, object]:
            return {"field_count": 2, "fields": [{"selector": "#email"}]}

        runtime = ToolRuntime(
            [
                AgentTool(
                    name="traceable_tool",
                    description="Traceable read tool.",
                    input_schema={
                        "type": "object",
                        "required": ["task_id"],
                        "properties": {"task_id": {"type": "integer"}},
                    },
                    output_schema={},
                    risk_level="low",
                    mutates_browser=False,
                    mutates_external_system=False,
                    trace_phase="extraction",
                    handler=handler,
                )
            ]
        )

        result = await runtime.execute(
            tool_call_id="call-1",
            tool_name="traceable_tool",
            tool_input={"task_id": task.id},
            context=ToolExecutionContext(metadata={"db": session}),
        )

        assert result.status == "SUCCEEDED"
        spans = list_spans_for_task(session, task.id)
        assert len(spans) == 1
        assert spans[0].phase == "extraction"
        assert spans[0].name == "traceable_tool"
        assert spans[0].status == "SUCCESS"
        assert spans[0].input == {"tool_call_id": "call-1", "task_id": task.id}
        assert spans[0].output == {"field_count": 2}
        assert spans[0].latency_ms >= 0
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.mark.anyio
async def test_tool_runtime_records_failure_trace_when_handler_raises() -> None:
    """Verify tool failures are captured in trace spans without leaking exceptions."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        profile = Profile(profile_name="Trace profile")
        task = Task(url="https://example.com/form", profile=profile)
        session.add(task)
        session.commit()

        async def handler(
            _context: ToolExecutionContext,
            _tool_input: dict[str, object],
        ) -> dict[str, object]:
            raise RuntimeError("tool failed")

        runtime = ToolRuntime(
            [
                AgentTool(
                    name="failing_tool",
                    description="Failing read tool.",
                    input_schema={
                        "type": "object",
                        "required": ["task_id"],
                        "properties": {"task_id": {"type": "integer"}},
                    },
                    output_schema={},
                    risk_level="low",
                    mutates_browser=False,
                    mutates_external_system=False,
                    trace_phase="mapping",
                    handler=handler,
                )
            ]
        )

        result = await runtime.execute(
            tool_call_id="call-1",
            tool_name="failing_tool",
            tool_input={"task_id": task.id},
            context=ToolExecutionContext(metadata={"db": session}),
        )

        assert result.status == "FAILED"
        spans = list_spans_for_task(session, task.id)
        assert len(spans) == 1
        assert spans[0].phase == "mapping"
        assert spans[0].name == "failing_tool"
        assert spans[0].status == "FAILED"
        assert spans[0].error_message == "tool failed"
        assert spans[0].output == {}
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.mark.anyio
async def test_tool_runtime_blocks_handler_when_governance_blocks() -> None:
    """Verify blocked tool calls never reach the tool handler."""

    handler = AsyncMock(return_value={})
    runtime = ToolRuntime(
        [
            AgentTool(
                name="blocked_tool",
                description="Blocked tool.",
                input_schema={"type": "object", "properties": {}},
                output_schema={},
                risk_level="blocked",
                mutates_browser=False,
                mutates_external_system=False,
                trace_phase="test",
                handler=handler,
            )
        ]
    )

    result = await runtime.execute(
        tool_call_id="call-1",
        tool_name="blocked_tool",
        tool_input={},
    )

    assert result.status == "FAILED"
    assert result.error == "Tool call blocked by governance: Tool is marked blocked."
    assert result.governance_decision is not None
    assert result.governance_decision.decision == "BLOCKED"
    handler.assert_not_awaited()


@pytest.mark.anyio
async def test_tool_runtime_pauses_review_required_tools_before_handler() -> None:
    """Verify browser writes do not execute until review has approved them."""

    handler = AsyncMock(return_value={"filled_count": 1})
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

    result = await runtime.execute(
        tool_call_id="call-1",
        tool_name="fill_form",
        tool_input={"task_id": 1},
    )

    assert result.status == "FAILED"
    assert result.governance_decision is not None
    assert result.governance_decision.decision == "REVIEW_REQUIRED"
    assert result.error == "Tool call paused by governance: Tool changes browser state and needs human review first."
    handler.assert_not_awaited()


@pytest.mark.anyio
async def test_tool_runtime_executes_approved_browser_write_tools() -> None:
    """Verify previously approved browser writes can execute through the runtime."""

    handler = AsyncMock(return_value={"filled_count": 1})
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

    result = await runtime.execute(
        tool_call_id="call-1",
        tool_name="fill_form",
        tool_input={"task_id": 1},
        context=ToolExecutionContext(metadata={"approved_tool_call_ids": ["call-1"]}),
    )

    assert result.status == "SUCCEEDED"
    assert result.output_json == {"filled_count": 1}
    assert result.governance_decision is not None
    assert result.governance_decision.decision == "VERIFY_REQUIRED"
    handler.assert_awaited_once()


@pytest.mark.anyio
async def test_tool_runtime_pauses_submit_tools_before_handler() -> None:
    """Verify final submit tools require explicit approval before execution."""

    handler = AsyncMock(return_value={"submitted": True})
    runtime = ToolRuntime(
        [
            AgentTool(
                name="submit_form",
                description="Submit.",
                input_schema={"type": "object", "properties": {}},
                output_schema={},
                risk_level="high",
                mutates_browser=True,
                mutates_external_system=False,
                trace_phase="submit",
                handler=handler,
            )
        ]
    )

    result = await runtime.execute(
        tool_call_id="call-1",
        tool_name="submit_form",
        tool_input={"task_id": 1},
    )

    assert result.status == "FAILED"
    assert result.governance_decision is not None
    assert result.governance_decision.decision == "APPROVAL_REQUIRED"
    assert result.error == "Tool call paused by governance: Tool may commit an external or final browser action."
    handler.assert_not_awaited()
