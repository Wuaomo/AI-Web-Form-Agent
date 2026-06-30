"""Tests for browser form filling helpers."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FormField, Profile, Task, TaskActionTrace
from app.services.browser_executor import (
    _checkbox_should_be_checked,
    _fill_fields,
    _radio_selector_for_value,
)


class FakeLocator:
    @property
    def first(self) -> "FakeLocator":
        return self

    def fill(self, value: str, timeout: int) -> None:
        self.value = value
        self.timeout = timeout


class FakePage:
    def __init__(self) -> None:
        self.locators: dict[str, FakeLocator] = {}

    def locator(self, selector: str) -> FakeLocator:
        self.locators.setdefault(selector, FakeLocator())
        return self.locators[selector]


def test_radio_selector_for_value_uses_matching_option_selector() -> None:
    field = FormField(
        selector="#remote",
        field_type="radio",
        mapped_value="office",
    )
    field.options = [
        {"label": "Remote", "value": "remote", "selector": "#remote"},
        {"label": "Office", "value": "office", "selector": "#office"},
    ]

    assert _radio_selector_for_value(field) == "#office"


def test_radio_selector_for_value_falls_back_to_field_selector() -> None:
    field = FormField(
        selector="#remote",
        field_type="radio",
        mapped_value="hybrid",
    )
    field.options = [
        {"label": "Remote", "value": "remote", "selector": "#remote"},
    ]

    assert _radio_selector_for_value(field) == "#remote"


def test_checkbox_should_be_checked_supports_true_and_false_values() -> None:
    assert _checkbox_should_be_checked("yes") is True
    assert _checkbox_should_be_checked("true") is True
    assert _checkbox_should_be_checked("no") is False
    assert _checkbox_should_be_checked("false") is False
    assert _checkbox_should_be_checked("maybe") is None


def test_fill_fields_records_success_and_skipped_action_traces() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    profile = Profile(profile_name="Executor trace profile")
    task = Task(url="https://example.com/form", profile=profile)
    session.add(task)
    session.commit()
    email = FormField(
        task_id=task.id,
        selector="#email",
        field_type="text",
        mapped_value="ada@example.com",
    )
    submit = FormField(
        task_id=task.id,
        selector="#submit",
        field_type="submit",
        mapped_value="Submit",
    )

    _fill_fields(FakePage(), [email, submit], task_id=task.id, db=session)

    traces = list(
        session.scalars(
            select(TaskActionTrace)
            .where(TaskActionTrace.task_id == task.id)
            .order_by(TaskActionTrace.step)
        )
    )
    assert [(trace.action, trace.result, trace.selector) for trace in traces] == [
        ("fill", "success", "#email"),
        ("skip", "skipped", "#submit"),
    ]

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()
