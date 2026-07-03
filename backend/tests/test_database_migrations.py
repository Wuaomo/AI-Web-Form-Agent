"""Tests for database migration helpers."""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text


def test_init_db_adds_profile_memory_policy_to_existing_form_fields_table(tmp_path):
    """Verify that _add_missing_form_field_columns adds profile_memory_policy to legacy tables."""

    from app.database import _add_missing_form_field_columns

    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}")

    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE form_fields (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                label VARCHAR(500),
                selector VARCHAR(1000) NOT NULL,
                field_type VARCHAR(100),
                placeholder VARCHAR(500),
                required BOOLEAN NOT NULL DEFAULT 0,
                mapped_profile_key VARCHAR(100),
                mapped_value TEXT,
                confidence FLOAT
            )
        """))

    _add_missing_form_field_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("form_fields")}
    assert "profile_memory_policy" in columns

    with engine.begin() as connection:
        result = connection.execute(text("SELECT profile_memory_policy FROM form_fields LIMIT 1"))
        row = result.fetchone()
        assert row is None or row[0] == "auto"


def test_init_db_adds_all_missing_columns_to_existing_form_fields_table(tmp_path):
    """Verify that all missing columns are added to legacy tables."""

    from app.database import _add_missing_form_field_columns

    db_path = tmp_path / "minimal.db"
    engine = create_engine(f"sqlite:///{db_path}")

    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE form_fields (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                selector VARCHAR(1000) NOT NULL
            )
        """))

    _add_missing_form_field_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("form_fields")}
    assert "element_ref" in columns
    assert "form_title" in columns
    assert "section_title" in columns
    assert "name" in columns
    assert "html_id" in columns
    assert "current_value" in columns
    assert "options" in columns
    assert "profile_memory_policy" in columns


def test_task_checkpoint_model_creates_profile_task_and_checkpoint(tmp_path):
    """Verify TaskCheckpoint model creates and loads checkpoints with relationship."""

    from app.database import Base
    from app.models import Profile, Task, TaskCheckpoint, utc_now
    from app.workflow_constants import WORKFLOW_STAGE_ANALYSIS, CHECKPOINT_SUCCESS

    db_path = tmp_path / "checkpoint_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    checkpoint = TaskCheckpoint(
        task_id=task.id,
        stage=WORKFLOW_STAGE_ANALYSIS,
        status=CHECKPOINT_SUCCESS,
        input_hash="abc123",
        output_json=json.dumps({"fields": ["email", "name"]}),
    )
    session.add(checkpoint)
    session.commit()

    session.refresh(task)

    assert len(task.checkpoints) == 1
    assert task.checkpoints[0].stage == WORKFLOW_STAGE_ANALYSIS
    assert task.checkpoints[0].status == CHECKPOINT_SUCCESS
    assert task.checkpoints[0].input_hash == "abc123"

    session.close()


def test_task_checkpoint_output_json_safe_parse(tmp_path):
    """Verify invalid JSON in output_json is handled safely."""

    from app.database import Base
    from app.models import Profile, Task, TaskCheckpoint
    from app.workflow_constants import WORKFLOW_STAGE_MAPPING, CHECKPOINT_SUCCESS

    db_path = tmp_path / "checkpoint_json_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    checkpoint = TaskCheckpoint(
        task_id=task.id,
        stage=WORKFLOW_STAGE_MAPPING,
        status=CHECKPOINT_SUCCESS,
        output_json="{invalid json}",
    )
    session.add(checkpoint)
    session.commit()

    session.refresh(checkpoint)

    assert checkpoint.output is not None
    assert isinstance(checkpoint.output, dict)
    assert checkpoint.output == {}

    session.close()