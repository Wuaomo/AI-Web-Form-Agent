"""SQLite database configuration and initialization."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BACKEND_DIR / "app.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all database models."""


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for a FastAPI dependency."""

    with SessionLocal() as session:
        yield session


def init_db() -> None:
    """Create the SQLite database and all declared tables."""

    # Importing models registers their table metadata on Base.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _add_missing_task_workflow_columns()
    _add_missing_workflow_span_columns()
    _add_missing_approval_request_columns()
    _add_missing_form_field_columns()
    _add_missing_profile_columns()
    _add_missing_llm_usage_log_columns()
    _add_missing_benchmark_run_columns()


def _add_missing_task_workflow_columns(target_engine=engine) -> None:
    """Add workflow columns when opening an older SQLite database."""

    inspector = inspect(target_engine)
    if "tasks" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("tasks")
    }
    missing_columns = {
        "workflow_type": "VARCHAR(50) NOT NULL DEFAULT 'form_fill'",
        "workflow_status": "VARCHAR(50) NOT NULL DEFAULT 'CREATED'",
        "workflow_plan_json": "TEXT",
    }

    with target_engine.begin() as connection:
        for column_name, column_type in missing_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE tasks "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )


def _add_missing_workflow_span_columns(target_engine=engine) -> None:
    """Add new trace span columns for older SQLite databases."""

    inspector = inspect(target_engine)
    if "workflow_spans" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("workflow_spans")
    }
    missing_columns = {
        "parent_span_id": "INTEGER",
        "phase": "VARCHAR(100) NOT NULL DEFAULT 'extraction'",
        "name": "VARCHAR(150) NOT NULL DEFAULT 'unknown'",
        "status": "VARCHAR(50) NOT NULL DEFAULT 'STARTED'",
        "input_json": "TEXT",
        "output_json": "TEXT",
        "metadata_json": "TEXT",
        "provider": "VARCHAR(50)",
        "model": "VARCHAR(100)",
        "prompt_tokens": "INTEGER NOT NULL DEFAULT 0",
        "completion_tokens": "INTEGER NOT NULL DEFAULT 0",
        "total_tokens": "INTEGER NOT NULL DEFAULT 0",
        "estimated_cost": "FLOAT NOT NULL DEFAULT 0.0",
        "latency_ms": "INTEGER NOT NULL DEFAULT 0",
        "screenshot_id": "INTEGER",
        "error_message": "TEXT",
        "created_at": "DATETIME",
    }

    with target_engine.begin() as connection:
        for column_name, column_type in missing_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE workflow_spans "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )


def _add_missing_approval_request_columns(target_engine=engine) -> None:
    """Add approval request columns for older SQLite databases."""

    inspector = inspect(target_engine)
    if "approval_requests" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("approval_requests")
    }
    missing_columns = {
        "step_name": "VARCHAR(150) NOT NULL DEFAULT 'unknown_step'",
        "risk_type": "VARCHAR(100) NOT NULL DEFAULT 'UNKNOWN'",
        "risk_level": "VARCHAR(50) NOT NULL DEFAULT 'LOW'",
        "decision": "VARCHAR(50) NOT NULL DEFAULT 'REVIEW_REQUIRED'",
        "reason": "TEXT NOT NULL DEFAULT ''",
        "proposed_action_json": "TEXT NOT NULL DEFAULT '{}'",
        "status": "VARCHAR(50) NOT NULL DEFAULT 'PENDING'",
        "resolved_by": "VARCHAR(100)",
        "created_at": "DATETIME",
        "resolved_at": "DATETIME",
    }

    with target_engine.begin() as connection:
        for column_name, column_type in missing_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE approval_requests "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )


def _add_missing_form_field_columns(target_engine=engine) -> None:
    """Add new nullable columns when opening an older MVP SQLite database."""

    inspector = inspect(target_engine)
    if "form_fields" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("form_fields")
    }
    missing_columns = {
        "element_ref": "VARCHAR(100)",
        "form_title": "VARCHAR(500)",
        "section_title": "VARCHAR(500)",
        "name": "VARCHAR(500)",
        "html_id": "VARCHAR(500)",
        "current_value": "TEXT",
        "options": "TEXT",
        "profile_memory_policy": "VARCHAR(20) NOT NULL DEFAULT 'auto'",
    }

    with target_engine.begin() as connection:
        for column_name, column_type in missing_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE form_fields "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )


def _add_missing_profile_columns() -> None:
    """Add new nullable profile columns when opening an older SQLite database."""

    inspector = inspect(engine)
    if "profiles" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("profiles")
    }
    missing_columns = {
        "custom_values": "TEXT",
    }

    with engine.begin() as connection:
        for column_name, column_type in missing_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE profiles "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )


def _add_missing_llm_usage_log_columns() -> None:
    """Add new columns when opening an older SQLite database without llm_api_usage_logs fields."""

    inspector = inspect(engine)
    if "llm_api_usage_logs" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("llm_api_usage_logs")
    }
    missing_columns = {
        "latency_ms": "INTEGER NOT NULL DEFAULT 0",
        "error_type": "VARCHAR(100)",
        "fallback_used": "BOOLEAN NOT NULL DEFAULT 0",
        "cache_source": "VARCHAR(50) NOT NULL DEFAULT 'no_cache'",
        "estimated_cost": "FLOAT NOT NULL DEFAULT 0.0",
    }

    with engine.begin() as connection:
        for column_name, column_type in missing_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE llm_api_usage_logs "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )


def _add_missing_benchmark_run_columns(target_engine=engine) -> None:
    """Add new columns when opening an older SQLite database without benchmark_runs comparison fields."""

    inspector = inspect(target_engine)
    if "benchmark_runs" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("benchmark_runs")
    }
    missing_columns = {
        "baseline_run_id": "INTEGER",
        "duration_ms": "INTEGER NOT NULL DEFAULT 0",
        "regression_count": "INTEGER NOT NULL DEFAULT 0",
        "improvement_count": "INTEGER NOT NULL DEFAULT 0",
        "mode_detail": "VARCHAR(200)",
    }

    with target_engine.begin() as connection:
        for column_name, column_type in missing_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE benchmark_runs "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )
