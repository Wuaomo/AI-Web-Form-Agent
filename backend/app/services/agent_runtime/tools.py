"""Default executable tools for the agent runtime."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from app.services.agent_runtime.tool_runtime import (
    AgentTool,
    ToolExecutionContext,
    ToolRuntime,
)
from app.services.field_mapper import map_fields_by_rules
from app.services.form_extractor import extract_form_analysis
from app.services.browser_executor import fill_form_and_capture_screenshot


EXTRACT_FORM_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["url", "profile_id"],
    "properties": {
        "url": {"type": "string"},
        "profile_id": {"type": "integer"},
    },
}

EXTRACT_FORM_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["fields", "field_count", "login_required"],
    "properties": {
        "fields": {"type": "array"},
        "field_count": {"type": "integer"},
        "login_required": {"type": "boolean"},
    },
}

MAP_FIELDS_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["task_id"],
    "properties": {
        "task_id": {"type": "integer"},
    },
}

MAP_FIELDS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["fields", "field_count", "mapped_count", "mode"],
    "properties": {
        "fields": {"type": "array"},
        "field_count": {"type": "integer"},
        "mapped_count": {"type": "integer"},
        "mode": {"type": "string"},
    },
}

FILL_FORM_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["task_id", "url", "profile_id", "fields"],
    "properties": {
        "task_id": {"type": "integer"},
        "url": {"type": "string"},
        "profile_id": {"type": "integer"},
        "fields": {"type": "array"},
    },
}

FILL_FORM_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["filled_count", "screenshot_id", "verification_count"],
    "properties": {
        "filled_count": {"type": "integer"},
        "screenshot_id": {"type": "integer"},
        "verification_count": {"type": "integer"},
    },
}


def build_default_tool_runtime(
    *,
    extract_form_analysis_handler=extract_form_analysis,
    map_fields_by_rules_handler=map_fields_by_rules,
    fill_form_handler=fill_form_and_capture_screenshot,
) -> ToolRuntime:
    """Return the default runtime with internal tools registered."""

    async def run_extract_form(
        _context: ToolExecutionContext,
        tool_input: dict[str, Any],
    ) -> dict[str, Any]:
        analysis = await extract_form_analysis_handler(
            tool_input["url"],
            tool_input["profile_id"],
        )
        fields = [_field_to_dict(field) for field in analysis.fields]
        return {
            "fields": fields,
            "field_count": len(fields),
            "login_required": analysis.login_required,
        }

    async def run_map_fields(
        context: ToolExecutionContext,
        tool_input: dict[str, Any],
    ) -> dict[str, Any]:
        fields = map_fields_by_rules_handler(
            tool_input["task_id"],
            db=context.metadata.get("db"),
        )
        field_payload = [_mapped_field_to_dict(field) for field in fields]
        return {
            "fields": field_payload,
            "field_count": len(field_payload),
            "mapped_count": sum(
                1 for field in field_payload if field["mapped_profile_key"]
            ),
            "mode": "rules",
        }

    async def run_fill_form(
        context: ToolExecutionContext,
        tool_input: dict[str, Any],
    ) -> dict[str, Any]:
        screenshot, verification = await fill_form_handler(
            task_id=tool_input["task_id"],
            url=tool_input["url"],
            profile_id=tool_input["profile_id"],
            fields=tool_input["fields"],
            stage="filled_form",
            db=context.metadata.get("db"),
        )
        sink = context.metadata.get("fill_form_result")
        if isinstance(sink, dict):
            sink["screenshot"] = screenshot
            sink["verification_data"] = verification
        return {
            "filled_count": len(tool_input["fields"]),
            "screenshot_id": getattr(screenshot, "id", None),
            "verification_count": len(verification),
        }

    runtime = ToolRuntime()
    for name in ("extract_form", "extract_form_fields"):
        runtime.register(
            AgentTool(
                name=name,
                description="Extract form structure and fillable fields.",
                input_schema=EXTRACT_FORM_INPUT_SCHEMA,
                output_schema=EXTRACT_FORM_OUTPUT_SCHEMA,
                risk_level="low",
                mutates_browser=False,
                mutates_external_system=False,
                trace_phase="extraction",
                handler=run_extract_form,
            )
        )
    for name in ("map_fields", "generate_field_mappings"):
        runtime.register(
            AgentTool(
                name=name,
                description="Map extracted fields to profile values with local rules.",
                input_schema=MAP_FIELDS_INPUT_SCHEMA,
                output_schema=MAP_FIELDS_OUTPUT_SCHEMA,
                risk_level="medium",
                mutates_browser=False,
                mutates_external_system=False,
                trace_phase="mapping",
                handler=run_map_fields,
            )
        )
    runtime.register(
        AgentTool(
            name="fill_form",
            description="Fill reviewed form fields in the browser.",
            input_schema=FILL_FORM_INPUT_SCHEMA,
            output_schema=FILL_FORM_OUTPUT_SCHEMA,
            risk_level="medium",
            mutates_browser=True,
            mutates_external_system=False,
            trace_phase="browser",
            handler=run_fill_form,
        )
    )
    return runtime


async def execute_fill_form_runtime_tool(
    *,
    db: Any,
    task: Any,
    fields: list[Any],
    fill_form_handler=fill_form_and_capture_screenshot,
) -> tuple[Any, Any, list[Any]]:
    """Run the approved fill_form browser-write tool for a legacy task."""

    tool_call_id = f"task-{task.id}:fill_form"
    fill_result: dict[str, Any] = {}
    tool_result = await build_default_tool_runtime(
        fill_form_handler=fill_form_handler
    ).execute(
        tool_call_id=tool_call_id,
        tool_name="fill_form",
        tool_input={
            "task_id": task.id,
            "url": task.url,
            "profile_id": task.profile_id,
            "fields": fields,
        },
        context=ToolExecutionContext(
            metadata={
                "db": db,
                "task_id": task.id,
                "approved_tool_call_ids": [tool_call_id],
                "fill_form_result": fill_result,
            }
        ),
    )
    if tool_result.status != "SUCCEEDED":
        raise RuntimeError(tool_result.error or "Runtime fill_form failed")
    return (
        tool_result,
        fill_result.get("screenshot"),
        fill_result.get("verification_data", []),
    )


def _field_to_dict(field: object) -> dict[str, Any]:
    if is_dataclass(field):
        return asdict(field)
    if hasattr(field, "model_dump"):
        return field.model_dump()
    return {
        "element_ref": getattr(field, "element_ref"),
        "form_title": getattr(field, "form_title"),
        "section_title": getattr(field, "section_title"),
        "label": getattr(field, "label"),
        "selector": getattr(field, "selector"),
        "field_type": getattr(field, "field_type"),
        "placeholder": getattr(field, "placeholder"),
        "name": getattr(field, "name"),
        "html_id": getattr(field, "html_id"),
        "current_value": getattr(field, "current_value"),
        "required": getattr(field, "required"),
        "options": getattr(field, "options"),
    }


def _mapped_field_to_dict(field: object) -> dict[str, Any]:
    return {
        "id": getattr(field, "id"),
        "element_ref": getattr(field, "element_ref"),
        "label": getattr(field, "label"),
        "selector": getattr(field, "selector"),
        "field_type": getattr(field, "field_type"),
        "required": getattr(field, "required"),
        "mapped_profile_key": getattr(field, "mapped_profile_key"),
        "mapped_value": getattr(field, "mapped_value"),
        "confidence": getattr(field, "confidence"),
    }


__all__ = [
    "EXTRACT_FORM_INPUT_SCHEMA",
    "EXTRACT_FORM_OUTPUT_SCHEMA",
    "FILL_FORM_INPUT_SCHEMA",
    "FILL_FORM_OUTPUT_SCHEMA",
    "MAP_FIELDS_INPUT_SCHEMA",
    "MAP_FIELDS_OUTPUT_SCHEMA",
    "build_default_tool_runtime",
    "execute_fill_form_runtime_tool",
]
