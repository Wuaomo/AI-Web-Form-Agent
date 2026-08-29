"""Tests for shared agent runtime form-field persistence."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FormField, Profile, Task
from app.services.agent_runtime.form_field_persistence import replace_task_form_fields
from app.services.form_extractor import ExtractedFormField


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_replace_task_form_fields_replaces_existing_fields_and_preserves_options() -> None:
    """Verify extracted form fields are persisted through one shared adapter."""

    session = make_session()
    try:
        profile = Profile(profile_name="Persistence profile")
        task = Task(url="https://example.com/form", profile=profile)
        old_field = FormField(
            task=task,
            label="Old field",
            selector="#old",
            field_type="text",
            required=False,
        )
        session.add_all([task, old_field])
        session.commit()

        count = replace_task_form_fields(
            db=session,
            task=task,
            fields=[
                ExtractedFormField(
                    element_ref="field_1",
                    form_title="Application",
                    section_title="Contact",
                    label="Email",
                    selector="#email",
                    field_type="select",
                    placeholder="Choose one",
                    name="email",
                    html_id="email",
                    current_value=None,
                    required=True,
                    options=[
                        {"label": "Work", "value": "work", "selector": None},
                        {"label": "Personal", "value": "personal", "selector": None},
                    ],
                )
            ],
        )
        session.commit()

        fields = list(
            session.scalars(
                select(FormField)
                .where(FormField.task_id == task.id)
                .order_by(FormField.id)
            )
        )
        assert count == 1
        assert len(fields) == 1
        assert fields[0].label == "Email"
        assert fields[0].selector == "#email"
        assert fields[0].required is True
        assert fields[0].options == [
            {"label": "Work", "value": "work", "selector": None},
            {"label": "Personal", "value": "personal", "selector": None},
        ]
    finally:
        session.close()
