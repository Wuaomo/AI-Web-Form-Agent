"""Persist extracted form fields for agent runtime and legacy task flows."""

from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FormField, Task
from app.services.form_extractor import ExtractedFormField


def replace_task_form_fields(
    *,
    db: Session,
    task: Task,
    fields: Sequence[ExtractedFormField],
) -> int:
    """Replace all extracted fields for one task and return the saved count."""

    existing_fields = list(
        db.scalars(select(FormField).where(FormField.task_id == task.id))
    )
    for existing_field in existing_fields:
        db.delete(existing_field)
    db.flush()
    for existing_field in existing_fields:
        db.expunge(existing_field)

    for field in fields:
        db.add(
            FormField(
                task_id=task.id,
                element_ref=field.element_ref,
                form_title=field.form_title,
                section_title=field.section_title,
                label=field.label,
                selector=field.selector,
                field_type=field.field_type,
                placeholder=field.placeholder,
                name=field.name,
                html_id=field.html_id,
                current_value=field.current_value,
                field_options=json.dumps(field.options, ensure_ascii=False),
                required=field.required,
            )
        )
    return len(fields)


__all__ = ["replace_task_form_fields"]
