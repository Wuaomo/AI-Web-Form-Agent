"""Tests for checkpoint service to ensure deterministic read/write behavior."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Profile, Task, utc_now
from app.services.checkpoint_service import (
    list_checkpoints,
    read_checkpoint,
    write_checkpoint,
)
from app.workflow_constants import (
    CHECKPOINT_FAILED,
    CHECKPOINT_SUCCESS,
    WORKFLOW_STAGE_ANALYSIS,
    WORKFLOW_STAGE_FILL,
    WORKFLOW_STAGE_MAPPING,
)


@pytest.fixture
def db_session(tmp_path):
    """Create a temporary database session for tests."""

    db_path = tmp_path / "checkpoint_service_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    profile = Profile(profile_name="Test Profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.commit()

    yield session, task.id

    session.close()


def test_write_checkpoint_creates_record(db_session):
    """Verify write_checkpoint creates a new checkpoint record."""

    db, task_id = db_session

    checkpoint = write_checkpoint(
        task_id=task_id,
        stage=WORKFLOW_STAGE_ANALYSIS,
        status=CHECKPOINT_SUCCESS,
        input_hash="abc123",
        output={"fields": ["email", "name"]},
        db=db,
    )

    db.commit()

    assert checkpoint is not None
    assert checkpoint.task_id == task_id
    assert checkpoint.stage == WORKFLOW_STAGE_ANALYSIS
    assert checkpoint.status == CHECKPOINT_SUCCESS
    assert checkpoint.input_hash == "abc123"
    assert checkpoint.output == {"fields": ["email", "name"]}


def test_write_checkpoint_updates_existing_stage(db_session):
    """Verify write_checkpoint updates an existing checkpoint for the same stage."""

    db, task_id = db_session

    write_checkpoint(
        task_id=task_id,
        stage=WORKFLOW_STAGE_ANALYSIS,
        status=CHECKPOINT_SUCCESS,
        input_hash="hash1",
        db=db,
    )
    db.commit()

    checkpoint = write_checkpoint(
        task_id=task_id,
        stage=WORKFLOW_STAGE_ANALYSIS,
        status=CHECKPOINT_FAILED,
        input_hash="hash2",
        failure_reason="ANALYSIS_FAILED",
        error_message="Failed to extract fields",
        db=db,
    )

    db.commit()

    assert checkpoint.status == CHECKPOINT_FAILED
    assert checkpoint.input_hash == "hash2"
    assert checkpoint.failure_reason == "ANALYSIS_FAILED"
    assert checkpoint.error_message == "Failed to extract fields"


def test_read_checkpoint_returns_latest(db_session):
    """Verify read_checkpoint returns the most recent checkpoint for a stage."""

    db, task_id = db_session

    write_checkpoint(
        task_id=task_id,
        stage=WORKFLOW_STAGE_ANALYSIS,
        status=CHECKPOINT_SUCCESS,
        input_hash="v1",
        db=db,
    )
    db.commit()

    write_checkpoint(
        task_id=task_id,
        stage=WORKFLOW_STAGE_ANALYSIS,
        status=CHECKPOINT_FAILED,
        input_hash="v2",
        db=db,
    )
    db.commit()

    checkpoint = read_checkpoint(task_id=task_id, stage=WORKFLOW_STAGE_ANALYSIS, db=db)

    assert checkpoint is not None
    assert checkpoint.status == CHECKPOINT_FAILED
    assert checkpoint.input_hash == "v2"


def test_read_checkpoint_returns_none_for_missing_stage(db_session):
    """Verify read_checkpoint returns None when no checkpoint exists for a stage."""

    db, task_id = db_session

    write_checkpoint(
        task_id=task_id,
        stage=WORKFLOW_STAGE_ANALYSIS,
        status=CHECKPOINT_SUCCESS,
        db=db,
    )
    db.commit()

    checkpoint = read_checkpoint(task_id=task_id, stage=WORKFLOW_STAGE_MAPPING, db=db)

    assert checkpoint is None


def test_list_checkpoints_returns_all_for_task(db_session):
    """Verify list_checkpoints returns all checkpoints for a task."""

    db, task_id = db_session

    write_checkpoint(
        task_id=task_id,
        stage=WORKFLOW_STAGE_ANALYSIS,
        status=CHECKPOINT_SUCCESS,
        db=db,
    )
    db.commit()

    write_checkpoint(
        task_id=task_id,
        stage=WORKFLOW_STAGE_MAPPING,
        status=CHECKPOINT_SUCCESS,
        db=db,
    )
    db.commit()

    write_checkpoint(
        task_id=task_id,
        stage=WORKFLOW_STAGE_FILL,
        status=CHECKPOINT_FAILED,
        failure_reason="BROWSER_FILL_FAILED",
        db=db,
    )
    db.commit()

    checkpoints = list_checkpoints(task_id=task_id, db=db)

    assert len(checkpoints) == 3
    stages = [c.stage for c in checkpoints]
    assert WORKFLOW_STAGE_FILL in stages
    assert WORKFLOW_STAGE_MAPPING in stages
    assert WORKFLOW_STAGE_ANALYSIS in stages


def test_write_checkpoint_without_session(tmp_path):
    """Verify write_checkpoint works with direct session management."""

    db_path = tmp_path / "checkpoint_no_session_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        profile = Profile(profile_name="Test Profile")
        session.add(profile)
        session.commit()

        task = Task(url="https://example.com/form", profile_id=profile.id)
        session.add(task)
        session.commit()
        task_id = task.id

        checkpoint = write_checkpoint(
            task_id=task_id,
            stage=WORKFLOW_STAGE_ANALYSIS,
            status=CHECKPOINT_SUCCESS,
            db=session,
        )
        session.commit()

        assert checkpoint is not None
        assert checkpoint.task_id == task_id
        assert checkpoint.stage == WORKFLOW_STAGE_ANALYSIS


def test_read_checkpoint_without_session(tmp_path):
    """Verify read_checkpoint works with direct session management."""

    db_path = tmp_path / "read_checkpoint_no_session_test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        profile = Profile(profile_name="Test Profile")
        session.add(profile)
        session.commit()

        task = Task(url="https://example.com/form", profile_id=profile.id)
        session.add(task)
        session.commit()
        task_id = task.id

        write_checkpoint(
            task_id=task_id,
            stage=WORKFLOW_STAGE_ANALYSIS,
            status=CHECKPOINT_SUCCESS,
            db=session,
        )
        session.commit()

        checkpoint = read_checkpoint(task_id=task_id, stage=WORKFLOW_STAGE_ANALYSIS, db=session)

        assert checkpoint is not None
        assert checkpoint.stage == WORKFLOW_STAGE_ANALYSIS


def test_write_checkpoint_rejects_invalid_status(db_session):
    """Verify write_checkpoint raises ValueError for invalid status."""

    db, task_id = db_session

    with pytest.raises(ValueError, match="Invalid checkpoint status"):
        write_checkpoint(
            task_id=task_id,
            stage=WORKFLOW_STAGE_ANALYSIS,
            status="INVALID_STATUS",
            db=db,
        )