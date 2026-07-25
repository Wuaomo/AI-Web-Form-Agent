"""Static metadata for supported workflow tools."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolDefinition:
    """One inspectable workflow tool definition."""

    name: str
    description: str
    risk_level: str
    requires_approval: bool
    implemented: bool
    params_schema: dict[str, object] = field(default_factory=dict)
    preconditions: list[str] = field(default_factory=list)
    produces: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)
    recovery_hint: str = ""
    evidence_required: list[str] = field(default_factory=list)
    approval_reason: str = ""


TASK_ID_SCHEMA = {
    "type": "object",
    "required": ["task_id"],
    "properties": {
        "task_id": {"type": "integer"},
    },
}


_TOOL_REGISTRY = {
    "open_url": ToolDefinition(
        name="open_url",
        description="Open the target workflow URL.",
        risk_level="low",
        requires_approval=False,
        implemented=True,
        params_schema={
            "type": "object",
            "required": ["task_id", "url"],
            "properties": {
                "task_id": {"type": "integer"},
                "url": {"type": "string"},
            },
        },
        preconditions=["task_created"],
        produces=["page_opened", "screenshot"],
        failure_modes=["network_error", "page_timeout", "login_required"],
        recovery_hint="Check network connectivity, verify URL validity, or log in manually if the page requires authentication.",
        evidence_required=["screenshot"],
        approval_reason="",
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
        params_schema=TASK_ID_SCHEMA,
        preconditions=["page_opened"],
        produces=["form_fields"],
        failure_modes=["no_form_found", "javascript_render_timeout", "selector_failure"],
        recovery_hint="Ensure the page contains form elements and wait for JavaScript rendering. Verify page structure manually if extraction fails.",
        evidence_required=["form_fields_json"],
        approval_reason="",
    ),
    "map_fields": ToolDefinition(
        name="map_fields",
        description="Map extracted fields to profile or user-provided values.",
        risk_level="medium",
        requires_approval=False,
        implemented=True,
        params_schema=TASK_ID_SCHEMA,
        preconditions=["form_fields"],
        produces=["field_mappings"],
        failure_modes=["low_confidence_mapping", "missing_profile_data", "ambiguous_field_match"],
        recovery_hint="Review and correct low-confidence mappings manually. Add missing profile data or adjust field matching rules.",
        evidence_required=["mapping_confidence_scores", "field_source_evidence"],
        approval_reason="",
    ),
    "request_human_approval": ToolDefinition(
        name="request_human_approval",
        description="Pause for explicit user review or approval.",
        risk_level="medium",
        requires_approval=False,
        implemented=True,
        params_schema=TASK_ID_SCHEMA,
        preconditions=["field_mappings"],
        produces=["approval_decision"],
        failure_modes=["approval_timeout", "user_rejection"],
        recovery_hint="Review the current state, address concerns, and resubmit for approval. Adjust mappings if rejected.",
        evidence_required=["approval_decision", "reviewer_comments"],
        approval_reason="",
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
        params_schema=TASK_ID_SCHEMA,
        preconditions=["mapping_confirmed", "policy_passed"],
        produces=["filled_fields", "verification_candidates"],
        failure_modes=["field_not_fillable", "value_format_error", "page_navigated"],
        recovery_hint="Check field type compatibility, verify value formats, and ensure the page has not navigated away. Refill failed fields manually.",
        evidence_required=["fill_result_screenshot", "field_value_log"],
        approval_reason="",
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
        params_schema=TASK_ID_SCHEMA,
        preconditions=["filled_fields"],
        produces=["verification_results"],
        failure_modes=["verification_mismatch", "selector_not_found", "field_disabled"],
        recovery_hint="Compare expected vs actual values. Re-fill mismatched fields or adjust selectors if elements have changed.",
        evidence_required=["verification_results_json", "post_fill_screenshot"],
        approval_reason="",
    ),
    "capture_screenshot": ToolDefinition(
        name="capture_screenshot",
        description="Capture a screenshot for review or debugging.",
        risk_level="low",
        requires_approval=False,
        implemented=False,
    ),
    "save_result": ToolDefinition(
        name="save_result",
        description="Save extraction result to persistent storage.",
        risk_level="low",
        requires_approval=False,
        implemented=False,
    ),
    "summarize_page": ToolDefinition(
        name="summarize_page",
        description="Summarize extracted page content into a structured research summary.",
        risk_level="medium",
        requires_approval=False,
        implemented=False,
    ),
    "submit_form": ToolDefinition(
        name="submit_form",
        description="Submit the completed form.",
        risk_level="high",
        requires_approval=True,
        implemented=True,
        params_schema=TASK_ID_SCHEMA,
        preconditions=["final_approval", "verification_results"],
        produces=["submitted_form", "screenshot"],
        failure_modes=["submit_timeout", "server_error", "validation_failure"],
        recovery_hint="Check network connectivity, review form validation errors, and verify all required fields are completed. Retry submission after fixing issues.",
        evidence_required=["submit_screenshot", "verification_results"],
        approval_reason="Form submission is irreversible and may have financial or legal implications. User must explicitly approve before submission.",
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
