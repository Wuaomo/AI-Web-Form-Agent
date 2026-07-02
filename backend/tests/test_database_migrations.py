"""Tests for database migration helpers."""

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