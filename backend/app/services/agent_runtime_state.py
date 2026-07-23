"""Graph-ready WorkflowState generation for agent runtime compatibility.

This module produces a serializable state dict from existing Task/FormField
models without introducing LangGraph or any new database tables. The state is
designed so a future LangGraph adapter could consume it, but the current
system remains fully functional without LangGraph.
"""

from __future__ import annotations

from typing import Any

from app.models import FormField, Task

SENSITIVE_FIELD_TYPES = {"password"}
SENSITIVE_TOKENS = {"password", "otp", "payment", "card", "captcha", "consent"}


def _is_sensitive_field(field: FormField) -> bool:
    """Return True if the field may carry a sensitive or one-time value."""

    field_type = (field.field_type or "").lower()
    if field_type in SENSITIVE_FIELD_TYPES:
        return True

    text = " ".join(
        str(x or "")
        for x in [field.label, field.name, field.placeholder, field.selector, field.field_type]
    ).lower()
    return any(token in text for token in SENSITIVE_TOKENS)


def compact_field(field: FormField) -> dict[str, object]:
    """Produce a minimal, serializable representation of a form field.

    Sensitive fields omit ``mapped_value`` so secrets never enter the state.
    """

    item: dict[str, object] = {
        "field_id": field.id,
        "label": field.label,
        "name": field.name,
        "selector": field.selector,
        "field_type": field.field_type,
        "required": bool(field.required),
        "mapped_profile_key": field.mapped_profile_key,
        "confidence": field.confidence,
    }
    if not _is_sensitive_field(field):
        item["mapped_value"] = field.mapped_value
    return item


def build_workflow_state(
    task: Task,
    *,
    checkpoints: list[Any] | None = None,
    approvals: list[Any] | None = None,
) -> dict[str, object]:
    """Build a graph-ready workflow state dict from a Task and its relations.

    The state is a plain dict that a future LangGraph adapter could consume
    as the initial graph state. It only reads existing model attributes and
    never persists anything new.

    Parameters
    ----------
    task:
        The persisted Task row to read.
    checkpoints:
        Optional list of TaskCheckpoint rows (reserved for future use).
    approvals:
        Optional list of ApprovalRequest rows (reserved for future use).
    """

    return {
        "task_id": task.id,
        "workflow_type": task.workflow_type,
        "target_url": task.url,
        "profile_id": task.profile_id,
        "page_snapshot_id": None,
        "extracted_fields": [
            compact_field(field) for field in getattr(task, "form_fields", [])
        ],
        "memory_hits": [],
        "policy_sources": [],
        "suggestions": [],
        "policy_result": None,
        "review_request_id": None,
        "review_decision": None,
        "browser_execution_id": None,
        "verification_result": None,
        "submit_approval_request_id": None,
        "status": task.workflow_status or task.status,
        "error": None,
    }
