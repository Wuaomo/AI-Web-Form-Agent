"""Tests for workflow trace span persistence."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Profile, Task, WorkflowSpan
from app.services.workflow_trace_service import create_span, finish_span, list_spans_for_task


def make_session() -> Session:
    """Create an isolated in-memory database session."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_create_span_persists_dict_payloads() -> None:
    """Verify span input, output, and metadata are stored as JSON text."""

    session = make_session()
    profile = Profile(profile_name="Trace profile")
    task = Task(url="https://example.com/form", profile=profile)
    session.add(task)
    session.commit()

    span = create_span(
        session,
        task_id=task.id,
        phase="mapping",
        name="map_fields_llm",
        input={"mode": "llm"},
        output={"mapped_count": 3},
        metadata={"fallback_used": False},
    )
    session.commit()

    assert span.input == {"mode": "llm"}
    assert span.output == {"mapped_count": 3}
    assert span.span_metadata == {"fallback_used": False}


def test_workflow_span_safe_properties_return_empty_dict_for_invalid_json() -> None:
    """Verify invalid JSON never leaks through span properties."""

    span = WorkflowSpan(
        task_id=1,
        phase="browser",
        name="fill_form",
        status="STARTED",
        input_json="{bad",
        output_json='"string"',
        metadata_json="[1,2,3]",
    )

    assert span.input == {}
    assert span.output == {}
    assert span.span_metadata == {}


def test_finish_span_updates_status_output_latency_and_error() -> None:
    """Verify finish_span updates the final trace details."""

    session = make_session()
    profile = Profile(profile_name="Trace profile")
    task = Task(url="https://example.com/form", profile=profile)
    session.add(task)
    session.commit()

    span = create_span(
        session,
        task_id=task.id,
        phase="extraction",
        name="extract_form",
    )
    finish_span(
        session,
        span,
        status="FAILED",
        output={"field_count": 0},
        metadata={"cache_hit": False},
        latency_ms=321,
        error_message="Timed out",
    )
    session.commit()

    assert span.status == "FAILED"
    assert span.output == {"field_count": 0}
    assert span.span_metadata == {"cache_hit": False}
    assert span.latency_ms == 321
    assert span.error_message == "Timed out"


def test_list_spans_for_task_returns_chronological_rows() -> None:
    """Verify task traces are returned in chronological order."""

    session = make_session()
    profile = Profile(profile_name="Trace profile")
    task = Task(url="https://example.com/form", profile=profile)
    session.add(task)
    session.commit()

    first = create_span(session, task_id=task.id, phase="extraction", name="extract_form")
    second = create_span(session, task_id=task.id, phase="mapping", name="map_fields_rules")
    session.commit()

    spans = list_spans_for_task(session, task.id)

    assert [span.id for span in spans] == [first.id, second.id]
