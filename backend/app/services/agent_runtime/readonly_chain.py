"""Small read-only runtime chain for form intake."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.agent_runtime.schemas import ToolResult
from app.services.agent_runtime.tool_runtime import ToolExecutionContext, ToolRuntime
from app.services.agent_runtime.tools import build_default_tool_runtime


async def run_readonly_form_intake(
    *,
    task_id: int,
    url: str,
    profile_id: int,
    db: Session,
    runtime: ToolRuntime | None = None,
) -> list[ToolResult]:
    """Run the first runtime tools without changing task workflow state."""

    active_runtime = runtime or build_default_tool_runtime()
    context = ToolExecutionContext(metadata={"db": db, "task_id": task_id})
    results: list[ToolResult] = []

    extract_result = await active_runtime.execute(
        tool_call_id=f"task-{task_id}:extract_form",
        tool_name="extract_form",
        tool_input={
            "task_id": task_id,
            "url": url,
            "profile_id": profile_id,
        },
        context=context,
    )
    results.append(extract_result)
    if extract_result.status != "SUCCEEDED" or extract_result.output_json.get("login_required"):
        return results

    map_result = await active_runtime.execute(
        tool_call_id=f"task-{task_id}:map_fields",
        tool_name="map_fields",
        tool_input={"task_id": task_id},
        context=context,
    )
    results.append(map_result)
    return results


__all__ = ["run_readonly_form_intake"]
