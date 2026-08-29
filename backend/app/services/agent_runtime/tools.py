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


def build_default_tool_runtime(
    *,
    extract_form_analysis_handler=extract_form_analysis,
    map_fields_by_rules_handler=map_fields_by_rules,
) -> ToolRuntime:
    """Return the default runtime with internal read-only tools registered."""

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
    return runtime


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
    "MAP_FIELDS_INPUT_SCHEMA",
    "MAP_FIELDS_OUTPUT_SCHEMA",
    "build_default_tool_runtime",
]
