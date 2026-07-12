"""Tests for deterministic workflow planning helpers."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Profile, Task
from app.services.planner_service import (
    build_form_fill_plan,
    build_plan,
    plan_to_dict,
    resolve_plan_goal,
    save_plan,
)
from app.services.tool_registry import require_tool


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory session for save_plan tests."""

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


def test_build_form_fill_plan_uses_expected_step_order() -> None:
    """Verify the deterministic form-fill planner outputs the approved order."""

    plan = build_form_fill_plan(goal="Fill this application.")

    assert [step.step_id for step in plan.steps] == [
        "open_url",
        "extract_form",
        "map_fields",
        "review_mapping",
        "fill_form",
        "verify_fields",
        "submit_form",
    ]


def test_every_planned_tool_exists_in_registry() -> None:
    """Verify planner output never references unknown tools."""

    plan = build_form_fill_plan(goal="Fill this application.")

    for step in plan.steps:
        assert require_tool(step.tool).name == step.tool


def test_submit_form_step_requires_approval() -> None:
    """Verify the final submit step stays approval-gated in plan metadata."""

    plan = build_form_fill_plan(goal="Fill this application.")

    submit_step = next(step for step in plan.steps if step.step_id == "submit_form")

    assert submit_step.requires_approval is True


def test_build_web_data_extract_plan_uses_expected_step_order() -> None:
    """Verify the deterministic web_data_extract planner outputs the approved order."""

    plan = build_plan(
        workflow_type="web_data_extract",
        goal="Extract data from page",
    )

    assert plan.workflow_type == "web_data_extract"
    assert plan.goal == "Extract data from page"
    assert [step.step_id for step in plan.steps] == [
        "open_url",
        "extract_dom",
        "capture_screenshot",
        "save_result",
    ]


def test_build_plan_rejects_unsupported_workflow_type() -> None:
    """Verify planner scope remains bounded to supported workflow types."""

    with pytest.raises(
        ValueError,
        match="Unsupported workflow type for planning: data_entry",
    ):
        build_plan(
            workflow_type="data_entry",
            goal="Data entry",
        )


def test_plan_to_dict_output_is_stable() -> None:
    """Verify plan serialization stays deterministic for persistence and tests."""

    plan = build_form_fill_plan(goal="Fill this application.")

    assert plan_to_dict(plan) == {
        "workflow_type": "form_fill",
        "goal": "Fill this application.",
        "steps": [
            {
                "step_id": "open_url",
                "tool": "open_url",
                "reason": "Open the target page before extracting form structure.",
                "requires_approval": False,
                "status": "PENDING",
            },
            {
                "step_id": "extract_form",
                "tool": "extract_form",
                "reason": "Extract the form schema and candidate fields.",
                "requires_approval": False,
                "status": "PENDING",
            },
            {
                "step_id": "map_fields",
                "tool": "map_fields",
                "reason": "Map extracted fields to profile data or user-provided values.",
                "requires_approval": False,
                "status": "PENDING",
            },
            {
                "step_id": "review_mapping",
                "tool": "request_human_approval",
                "reason": "Let the user review and confirm the proposed mapping before fill.",
                "requires_approval": True,
                "status": "PENDING",
            },
            {
                "step_id": "fill_form",
                "tool": "fill_form",
                "reason": "Apply confirmed mapped values to the form.",
                "requires_approval": False,
                "status": "PENDING",
            },
            {
                "step_id": "verify_fields",
                "tool": "verify_fields",
                "reason": "Verify browser-side field values after fill.",
                "requires_approval": False,
                "status": "PENDING",
            },
            {
                "step_id": "submit_form",
                "tool": "submit_form",
                "reason": "Submit the completed form after final approval.",
                "requires_approval": True,
                "status": "PENDING",
            },
        ],
    }


def test_save_plan_persists_stable_json_on_task(session: Session) -> None:
    """Verify save_plan writes workflow plan JSON on the task row."""

    profile = Profile(profile_name="Planner profile")
    session.add(profile)
    session.commit()

    task = Task(url="https://example.com/form", profile_id=profile.id)
    session.add(task)
    session.flush()

    save_plan(session, task, build_form_fill_plan(goal="Fill this application."))
    session.commit()
    session.refresh(task)

    assert task.workflow_plan["goal"] == "Fill this application."
    assert task.workflow_plan["steps"][0]["step_id"] == "open_url"


def test_task_workflow_plan_raises_for_malformed_json() -> None:
    """Verify malformed saved plan JSON is not treated as a missing plan."""

    task = Task(
        url="https://example.com/form",
        profile_id=1,
        workflow_plan_json="{broken json",
    )

    with pytest.raises(ValueError, match="Invalid workflow plan JSON"):
        _ = task.workflow_plan


def test_resolve_plan_goal_uses_description_then_url_fallback() -> None:
    """Verify deterministic goal resolution needs no LLM involvement."""

    assert resolve_plan_goal(
        description=" Internship application ",
        url="https://example.com/form",
    ) == "Internship application"
    assert resolve_plan_goal(
        description="",
        url="https://example.com/form",
    ) == "Complete the form workflow for https://example.com/form."
