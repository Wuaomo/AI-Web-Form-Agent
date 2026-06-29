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
    _add_missing_form_field_columns()


def _add_missing_form_field_columns() -> None:
    """Add new nullable columns when opening an older MVP SQLite database."""

    inspector = inspect(engine)
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
    }

    with engine.begin() as connection:
        for column_name, column_type in missing_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE form_fields "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )
