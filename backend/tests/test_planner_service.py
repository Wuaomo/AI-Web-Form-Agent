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


def test_build_job_research_summary_plan_uses_expected_step_order() -> None:
    """Verify the deterministic job_research_summary planner outputs the approved order."""

    plan = build_plan(
        workflow_type="job_research_summary",
        goal="Research job listing",
    )

    assert plan.workflow_type == "job_research_summary"
    assert plan.goal == "Research job listing"
    assert [step.step_id for step in plan.steps] == [
        "open_url",
        "extract_dom",
        "summarize_page",
        "save_result",
    ]


def test_build_security_questionnaire_plan_reuses_review_first_form_flow() -> None:
    """Verify the questionnaire planner keeps human review before browser execution."""

    plan = build_plan(
        workflow_type="security_questionnaire",
        goal="Complete security questionnaire",
    )

    assert plan.workflow_type == "security_questionnaire"
    assert [step.step_id for step in plan.steps] == [
        "open_url",
        "extract_form",
        "map_fields",
        "review_mapping",
        "fill_form",
        "verify_fields",
        "submit_form",
    ]
    assert next(step for step in plan.steps if step.step_id == "review_mapping").requires_approval is True
    assert next(step for step in plan.steps if step.step_id == "submit_form").requires_approval is True


def test_build_vendor_onboarding_plan_reuses_review_first_form_flow() -> None:
    """Verify vendor onboarding keeps the same review and approval gates."""

    plan = build_plan(
        workflow_type="vendor_onboarding",
        goal="Complete vendor onboarding",
    )

    assert plan.workflow_type == "vendor_onboarding"
    assert [step.step_id for step in plan.steps] == [
        "open_url",
        "extract_form",
        "map_fields",
        "review_mapping",
        "fill_form",
        "verify_fields",
        "submit_form",
    ]
    assert next(step for step in plan.steps if step.step_id == "review_mapping").requires_approval is True
    assert next(step for step in plan.steps if step.step_id == "submit_form").requires_approval is True


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
    plan_dict = plan_to_dict(plan)

    assert plan_dict["workflow_type"] == "form_fill"
    assert plan_dict["goal"] == "Fill this application."
    assert [
        (
            step["step_id"],
            step["tool"],
            step["requires_approval"],
            step["status"],
        )
        for step in plan_dict["steps"]
    ] == [
        ("open_url", "open_url", False, "PENDING"),
        ("extract_form", "extract_form", False, "PENDING"),
        ("map_fields", "map_fields", False, "PENDING"),
        ("review_mapping", "request_human_approval", True, "PENDING"),
        ("fill_form", "fill_form", False, "PENDING"),
        ("verify_fields", "verify_fields", False, "PENDING"),
        ("submit_form", "submit_form", True, "PENDING"),
    ]


def test_plan_to_dict_includes_tool_runtime_metadata() -> None:
    """Verify serialized steps include tool schemas for review and execution context."""

    plan = build_form_fill_plan(goal="Fill this application.")

    first_step = plan_to_dict(plan)["steps"][0]

    assert first_step["params_schema"] == {
        "type": "object",
        "required": ["task_id", "url"],
        "properties": {
            "task_id": {"type": "integer"},
            "url": {"type": "string"},
        },
    }
    assert first_step["preconditions"] == ["task_created"]
    assert first_step["produces"] == ["page_opened", "screenshot"]


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
