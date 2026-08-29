"""Tests for action-level runtime governance."""

from app.services.agent_runtime.governance import GovernanceEngine
from app.services.agent_runtime.tool_runtime import AgentTool, ToolExecutionContext


async def noop_handler(
    _context: ToolExecutionContext,
    _tool_input: dict[str, object],
) -> dict[str, object]:
    return {}


def make_tool(
    name: str,
    *,
    risk_level: str = "low",
    mutates_browser: bool = False,
    mutates_external_system: bool = False,
) -> AgentTool:
    return AgentTool(
        name=name,
        description=f"{name} test tool",
        input_schema={"type": "object", "properties": {}},
        output_schema={},
        risk_level=risk_level,
        mutates_browser=mutates_browser,
        mutates_external_system=mutates_external_system,
        trace_phase="test",
        handler=noop_handler,
    )


def test_governance_allows_read_only_extraction_tools() -> None:
    """Verify read-only page inspection can execute without review."""

    decision = GovernanceEngine().evaluate_tool_call(
        make_tool("extract_form"),
        {"url": "https://example.com/form", "profile_id": 1},
    )

    assert decision.decision == "ALLOW"
    assert decision.requires_review is False
    assert decision.requires_approval is False


def test_governance_records_mapping_tools_without_blocking() -> None:
    """Verify mapping is tracked as record-only work."""

    decision = GovernanceEngine().evaluate_tool_call(
        make_tool("map_fields", risk_level="medium"),
        {"task_id": 1},
    )

    assert decision.decision == "RECORD_ONLY"
    assert decision.risk_level == "medium"
    assert "mapping" in decision.reason.lower()


def test_governance_requires_review_for_browser_mutations() -> None:
    """Verify browser writes cannot silently execute in the runtime."""

    decision = GovernanceEngine().evaluate_tool_call(
        make_tool("fill_form", risk_level="medium", mutates_browser=True),
        {"task_id": 1},
    )

    assert decision.decision == "REVIEW_REQUIRED"
    assert decision.requires_review is True


def test_governance_requires_approval_for_submit_tools() -> None:
    """Verify final submissions require explicit approval."""

    decision = GovernanceEngine().evaluate_tool_call(
        make_tool("submit_form", risk_level="high", mutates_browser=True),
        {"task_id": 1},
    )

    assert decision.decision == "APPROVAL_REQUIRED"
    assert decision.requires_approval is True


def test_governance_blocks_sensitive_browser_mutations() -> None:
    """Verify sensitive browser writes are blocked before execution."""

    decision = GovernanceEngine().evaluate_tool_call(
        make_tool("fill_field", risk_level="high", mutates_browser=True),
        {"label": "Account password", "field_type": "password"},
    )

    assert decision.decision == "BLOCKED"
    assert decision.blocked_reason == "Sensitive browser action is not allowed."
