"""Tests for workflow memory persistence helpers."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FormField, Profile, Task, WorkflowMemoryItem
from app.services.workflow_memory import (
    build_field_memory_text,
    save_confirmed_mapping_memory,
    should_save_mapping_memory,
)
from app.workflow_constants import MEMORY_TYPE_CONFIRMED_MAPPING


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _create_task(db: Session) -> Task:
    profile = Profile(profile_name="Memory profile", email="ada@example.com")
    db.add(profile)
    db.flush()
    task = Task(url="https://example.com/form", profile_id=profile.id)
    db.add(task)
    db.flush()
    db.commit()
    db.refresh(task)
    return task


def test_build_field_memory_text_includes_expected_sections(session: Session) -> None:
    task = _create_task(session)
    field = FormField(
        task_id=task.id,
        label="GitHub",
        name="github_url",
        placeholder="https://github.com/...",
        field_type="url",
        selector="#github",
        required=False,
    )

    text = build_field_memory_text(field)

    assert "label: GitHub" in text
    assert "name: github_url" in text
    assert "placeholder: https://github.com/..." in text
    assert "type: url" in text
    assert "options:" in text


def test_sensitive_fields_are_not_saved(session: Session) -> None:
    task = _create_task(session)
    field = FormField(
        task_id=task.id,
        label="Password",
        selector="#password",
        field_type="password",
        required=True,
        mapped_profile_key="custom:password",
        mapped_value="should_not_store",
    )

    assert should_save_mapping_memory(field) is False
    saved = save_confirmed_mapping_memory(session, task=task, field=field)
    assert saved is None


def test_confirmed_mapping_saves_profile_key_but_not_raw_value(session: Session) -> None:
    task = _create_task(session)
    field = FormField(
        task_id=task.id,
        label="GitHub",
        selector="#github",
        field_type="url",
        required=False,
        mapped_profile_key="github",
        mapped_value="https://github.com/ada",
    )

    item = save_confirmed_mapping_memory(session, task=task, field=field)
    session.commit()

    assert item is not None
    assert item.memory_type == MEMORY_TYPE_CONFIRMED_MAPPING
    assert item.mapped_profile_key == "github"
    assert not hasattr(item, "mapped_value")


def test_duplicate_memory_increments_success_count(session: Session) -> None:
    task = _create_task(session)
    field = FormField(
        task_id=task.id,
        label="GitHub",
        selector="#github",
        field_type="url",
        required=False,
        mapped_profile_key="github",
        mapped_value="https://github.com/ada",
    )
    session.add(field)
    session.commit()

    first = save_confirmed_mapping_memory(session, task=task, field=field)
    session.commit()
    second = save_confirmed_mapping_memory(session, task=task, field=field)
    session.commit()

    assert first is not None
    assert second is not None
    rows = list(
        session.scalars(
            select(WorkflowMemoryItem).where(
                WorkflowMemoryItem.memory_type == MEMORY_TYPE_CONFIRMED_MAPPING
            )
        )
    )
    assert len(rows) == 1
    assert rows[0].success_count == 2

