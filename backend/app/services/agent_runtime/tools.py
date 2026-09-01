"""Default executable tools for the agent runtime."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from types import SimpleNamespace
from typing import Any

from app.models import Task
from app.services.policy_answer_retrieval import apply_policy_answer_suggestions
from app.services.agent_runtime.tool_runtime import (
    AgentTool,
    ToolExecutionContext,
    ToolRuntime,
)
from app.services.field_mapper import map_fields_by_rules
from app.services.form_extractor import extract_form_analysis
from app.services.browser_executor import (
    fill_form_and_capture_screenshot,
    submit_form_and_capture_screenshot,
)
from app.services.agent_runtime.review_queue import build_task_review_proposals
from app.workflow_constants import (
    WORKFLOW_STAGE_MAPPING,
    WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE,
)


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

SUBMIT_FORM_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["task_id", "url", "profile_id", "fields"],
    "properties": {
        "task_id": {"type": "integer"},
        "url": {"type": "string"},
        "profile_id": {"type": "integer"},
        "fields": {"type": "array"},
    },
}

SUBMIT_FORM_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["submitted", "field_count", "screenshot_id"],
    "properties": {
        "submitted": {"type": "boolean"},
        "field_count": {"type": "integer"},
        "screenshot_id": {"type": "integer"},
    },
}


def build_default_tool_runtime(
    *,
    extract_form_analysis_handler=extract_form_analysis,
    map_fields_by_rules_handler=map_fields_by_rules,
    fill_form_handler=fill_form_and_capture_screenshot,
    submit_form_handler=submit_form_and_capture_screenshot,
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
        db = context.metadata.get("db")
        fields = map_fields_by_rules_handler(
            tool_input["task_id"],
            db=db,
        )
        task = _task_from_context(context, tool_input["task_id"])
        source_suggestions = (
            apply_policy_answer_suggestions(fields=fields, db=db, task=task)
            if task is not None
            and task.workflow_type == WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE
            else []
        )
        if source_suggestions and db is not None:
            db.commit()
        proposals = (
            build_task_review_proposals(
                task=task,
                fields=fields,
                checkpoints=[
                    SimpleNamespace(
                        stage=WORKFLOW_STAGE_MAPPING,
                        output={"source_suggestions": source_suggestions},
                    )
                ],
            )
            if task is not None
            else []
        )
        field_payload = [_mapped_field_to_dict(field) for field in fields]
        return {
            "fields": field_payload,
            "field_count": len(field_payload),
            "mapped_count": sum(
                1 for field in field_payload if field["mapped_profile_key"]
            ),
            "mode": "rules",
            "_created_proposals": [
                proposal.model_dump(mode="json") for proposal in proposals
            ],
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
        screenshot_id = _int_id(screenshot)
        output = {
            "filled_count": len(tool_input["fields"]),
            "screenshot_id": screenshot_id,
            "verification_count": len(verification),
            "_verification_candidates": [
                _field_verification_candidate(
                    item,
                    run_id=str(context.run_id or f"task-{tool_input['task_id']}"),
                    screenshot_id=screenshot_id,
                )
                for item in verification
            ],
        }
        return output

    async def run_submit_form(
        context: ToolExecutionContext,
        tool_input: dict[str, Any],
    ) -> dict[str, Any]:
        screenshot = await submit_form_handler(
            task_id=tool_input["task_id"],
            url=tool_input["url"],
            profile_id=tool_input["profile_id"],
            fields=tool_input["fields"],
            stage="submitted_form",
            db=context.metadata.get("db"),
        )
        sink = context.metadata.get("submit_form_result")
        if isinstance(sink, dict):
            sink["screenshot"] = screenshot
        return {
            "submitted": True,
            "field_count": len(tool_input["fields"]),
            "screenshot_id": _int_id(screenshot),
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
    runtime.register(
        AgentTool(
            name="submit_form",
            description="Submit the reviewed browser form.",
            input_schema=SUBMIT_FORM_INPUT_SCHEMA,
            output_schema=SUBMIT_FORM_OUTPUT_SCHEMA,
            risk_level="high",
            mutates_browser=True,
            mutates_external_system=False,
            trace_phase="submit",
            handler=run_submit_form,
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


async def execute_submit_form_runtime_tool(
    *,
    db: Any,
    task: Any,
    fields: list[Any],
    submit_form_handler=submit_form_and_capture_screenshot,
) -> tuple[Any, Any]:
    """Run the approved submit_form browser-write tool for a legacy task."""

    tool_call_id = f"task-{task.id}:submit_form"
    submit_result: dict[str, Any] = {}
    tool_result = await build_default_tool_runtime(
        submit_form_handler=submit_form_handler
    ).execute(
        tool_call_id=tool_call_id,
        tool_name="submit_form",
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
                "submit_form_result": submit_result,
            }
        ),
    )
    if tool_result.status != "SUCCEEDED":
        raise RuntimeError(tool_result.error or "Runtime submit_form failed")
    return tool_result, submit_result.get("screenshot")


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


def _task_from_context(context: ToolExecutionContext, task_id: int) -> Task | None:
    db = context.metadata.get("db")
    return db.get(Task, task_id) if hasattr(db, "get") else None


def _field_verification_candidate(
    item: object,
    *,
    run_id: str,
    screenshot_id: int | None,
) -> dict[str, Any]:
    field_id = getattr(item, "field_id", None)
    selector = str(getattr(item, "selector", ""))
    return {
        "run_id": run_id,
        "target_ref": str(field_id) if field_id is not None else selector,
        "verification_type": "field_value",
        "expected": getattr(item, "expected_value", None),
        "evidence_required": ["dom_value"],
        "screenshot_id": screenshot_id,
    }


def _int_id(item: object) -> int | None:
    value = getattr(item, "id", None)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


__all__ = [
    "EXTRACT_FORM_INPUT_SCHEMA",
    "EXTRACT_FORM_OUTPUT_SCHEMA",
    "FILL_FORM_INPUT_SCHEMA",
    "FILL_FORM_OUTPUT_SCHEMA",
    "MAP_FIELDS_INPUT_SCHEMA",
    "MAP_FIELDS_OUTPUT_SCHEMA",
    "SUBMIT_FORM_INPUT_SCHEMA",
    "SUBMIT_FORM_OUTPUT_SCHEMA",
    "build_default_tool_runtime",
    "execute_fill_form_runtime_tool",
    "execute_submit_form_runtime_tool",
]
