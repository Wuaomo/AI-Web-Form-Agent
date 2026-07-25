"""Tests for workflow tool metadata registry."""

import pytest

from app.services.tool_registry import get_tool, list_tools, require_tool


def test_get_tool_returns_known_tool() -> None:
    """Verify known workflow tools can be looked up."""

    tool = get_tool("map_fields")

    assert tool is not None
    assert tool.name == "map_fields"
    assert tool.implemented is True


def test_require_tool_raises_for_unknown_tool() -> None:
    """Verify unknown workflow tools are rejected."""

    with pytest.raises(ValueError, match="Unknown workflow tool: does_not_exist"):
        require_tool("does_not_exist")


def test_submit_form_requires_approval() -> None:
    """Verify high-risk submit metadata stays explicit."""

    tool = require_tool("submit_form")

    assert tool.requires_approval is True


def test_implemented_tools_expose_runtime_schema_metadata() -> None:
    """Verify executable tools publish the metadata needed by planners and UI."""

    for tool in list_tools(include_unimplemented=False):
        assert tool.params_schema["type"] == "object"
        assert isinstance(tool.params_schema["properties"], dict)
        assert isinstance(tool.preconditions, list)
        assert isinstance(tool.produces, list)


def test_implemented_tools_expose_failure_and_safety_metadata() -> None:
    """Verify executable tools publish failure modes, recovery hints, and evidence requirements."""

    for tool in list_tools(include_unimplemented=False):
        assert isinstance(tool.failure_modes, list)
        assert len(tool.failure_modes) > 0, f"Tool {tool.name} should have failure_modes defined"
        assert isinstance(tool.recovery_hint, str)
        assert tool.recovery_hint, f"Tool {tool.name} should have recovery_hint defined"
        assert isinstance(tool.evidence_required, list)
        assert len(tool.evidence_required) > 0, f"Tool {tool.name} should have evidence_required defined"
        if tool.requires_approval:
            assert tool.approval_reason, f"Tool {tool.name} requires approval but has no approval_reason"


def test_unimplemented_tools_lack_executable_metadata() -> None:
    """Verify unimplemented tools remain inspectable but don't pretend to be executable."""

    for tool in list_tools(include_unimplemented=True):
        if not tool.implemented:
            assert tool.params_schema == {}
            assert tool.preconditions == []
            assert tool.produces == []
            assert tool.failure_modes == []
            assert tool.recovery_hint == ""
            assert tool.evidence_required == []


def test_list_tools_includes_unimplemented_tools() -> None:
    """Verify the registry remains inspectable beyond implemented tools."""

    names = [tool.name for tool in list_tools()]

    assert "click_element" in names
    assert "extract_dom" in names
