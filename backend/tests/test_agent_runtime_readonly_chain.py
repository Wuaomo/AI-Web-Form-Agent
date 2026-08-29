"""Tests for the read-only agent runtime intake chain."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FormField, Profile, Task
from app.services.agent_runtime.readonly_chain import run_readonly_form_intake
from app.services.agent_runtime.tools import build_default_tool_runtime


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


@pytest.mark.anyio
async def test_readonly_form_intake_runs_extract_then_rules_mapping() -> None:
    """Verify the chain executes the first two runtime tools in order."""

    session = make_session()
    try:
        profile = Profile(profile_name="Runtime profile", email="ada@example.com")
        task = Task(
            url="https://example.com/form",
            profile=profile,
            status="MAPPING_READY",
            workflow_status="MAPPING_READY",
        )
        field = FormField(
            task=task,
            element_ref="field_1",
            label="Email",
            selector="#email",
            field_type="email",
            required=True,
        )
        session.add_all([task, field])
        session.commit()
        extractor = AsyncMock(
            return_value=SimpleNamespace(fields=[], login_required=False)
        )
        runtime = build_default_tool_runtime(extract_form_analysis_handler=extractor)

        results = await run_readonly_form_intake(
            task_id=task.id,
            url=task.url,
            profile_id=task.profile_id,
            db=session,
            runtime=runtime,
        )

        assert [result.status for result in results] == ["SUCCEEDED", "SUCCEEDED"]
        assert [result.tool_call_id for result in results] == [
            f"task-{task.id}:extract_form",
            f"task-{task.id}:map_fields",
        ]
        assert results[1].output_json["mapped_count"] == 1
        session.refresh(task)
        session.refresh(field)
        assert task.status == "MAPPING_READY"
        assert field.mapped_profile_key == "email"
    finally:
        session.close()


@pytest.mark.anyio
async def test_readonly_form_intake_stops_when_extract_fails() -> None:
    """Verify a failed extraction prevents follow-up mapping."""

    session = make_session()
    try:
        profile = Profile(profile_name="Runtime profile", email="ada@example.com")
        task = Task(url="https://example.com/form", profile=profile)
        field = FormField(
            task=task,
            label="Email",
            selector="#email",
            field_type="email",
            required=True,
        )
        session.add_all([task, field])
        session.commit()
        extractor = AsyncMock(side_effect=RuntimeError("extract failed"))
        runtime = build_default_tool_runtime(extract_form_analysis_handler=extractor)

        results = await run_readonly_form_intake(
            task_id=task.id,
            url=task.url,
            profile_id=task.profile_id,
            db=session,
            runtime=runtime,
        )

        assert len(results) == 1
        assert results[0].status == "FAILED"
        assert results[0].error == "extract failed"
        session.refresh(field)
        assert field.mapped_profile_key is None
    finally:
        session.close()
