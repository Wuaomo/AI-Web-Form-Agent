"""Tests for action trace persistence."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Profile, Task
from app.services.action_trace_service import record_action_trace


def test_record_action_trace_assigns_steps_and_persists_details() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    profile = Profile(profile_name="Trace profile")
    task = Task(url="https://example.com/form", profile=profile)
    session.add(task)
    session.commit()

    first = record_action_trace(
        session,
        task_id=task.id,
        phase="fill",
        action="fill",
        result="success",
        selector="#email",
        field_id=7,
        input_value="ada@example.com",
    )
    second = record_action_trace(
        session,
        task_id=task.id,
        phase="fill",
        action="select",
        result="failed",
        selector="#location",
        error_message="No option found",
    )

    assert first.step == 1
    assert second.step == 2
    assert first.selector == "#email"
    assert first.input_value == "ada@example.com"
    assert second.error_message == "No option found"

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()

