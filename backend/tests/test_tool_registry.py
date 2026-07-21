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


def test_list_tools_includes_unimplemented_tools() -> None:
    """Verify the registry remains inspectable beyond implemented tools."""

    names = [tool.name for tool in list_tools()]

    assert "click_element" in names
    assert "extract_dom" in names
