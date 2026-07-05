"""Static metadata for supported workflow tools."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolDefinition:
    """One inspectable workflow tool definition."""

    name: str
    description: str
    risk_level: str
    requires_approval: bool
    implemented: bool


_TOOL_REGISTRY = {
    "open_url": ToolDefinition(
        name="open_url",
        description="Open the target workflow URL.",
        risk_level="low",
        requires_approval=False,
        implemented=True,
    ),
    "extract_dom": ToolDefinition(
        name="extract_dom",
        description="Inspect raw page DOM for workflow planning context.",
        risk_level="low",
        requires_approval=False,
        implemented=False,
    ),
    "extract_form": ToolDefinition(
        name="extract_form",
        description="Extract form structure and fillable fields.",
        risk_level="low",
        requires_approval=False,
        implemented=True,
    ),
    "map_fields": ToolDefinition(
        name="map_fields",
        description="Map extracted fields to profile or user-provided values.",
        risk_level="medium",
        requires_approval=False,
        implemented=True,
    ),
    "request_human_approval": ToolDefinition(
        name="request_human_approval",
        description="Pause for explicit user review or approval.",
        risk_level="medium",
        requires_approval=False,
        implemented=True,
    ),
    "fill_field": ToolDefinition(
        name="fill_field",
        description="Write a value into one fillable field.",
        risk_level="medium",
        requires_approval=False,
        implemented=False,
    ),
    "fill_form": ToolDefinition(
        name="fill_form",
        description="Fill mapped values into the extracted form.",
        risk_level="medium",
        requires_approval=False,
        implemented=True,
    ),
    "click_element": ToolDefinition(
        name="click_element",
        description="Click a page element that may change page state.",
        risk_level="high",
        requires_approval=True,
        implemented=False,
    ),
    "verify_fields": ToolDefinition(
        name="verify_fields",
        description="Verify field values after browser execution.",
        risk_level="medium",
        requires_approval=False,
        implemented=True,
    ),
    "capture_screenshot": ToolDefinition(
        name="capture_screenshot",
        description="Capture a screenshot for review or debugging.",
        risk_level="low",
        requires_approval=False,
        implemented=False,
    ),
    "submit_form": ToolDefinition(
        name="submit_form",
        description="Submit the completed form.",
        risk_level="high",
        requires_approval=True,
        implemented=True,
    ),
}


def list_tools(include_unimplemented: bool = True) -> list[ToolDefinition]:
    """Return registered tools in stable definition order."""

    tools = list(_TOOL_REGISTRY.values())
    if include_unimplemented:
        return tools
    return [tool for tool in tools if tool.implemented]


def get_tool(name: str) -> ToolDefinition | None:
    """Return one tool definition or None when it is unknown."""

    return _TOOL_REGISTRY.get(name)


def require_tool(name: str) -> ToolDefinition:
    """Return one tool definition or raise for unknown names."""

    tool = get_tool(name)
    if tool is None:
        raise ValueError(f"Unknown workflow tool: {name}")
    return tool
