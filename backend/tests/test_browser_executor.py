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
    _read_field_value,
)


class FakeLocator:
    def __init__(self) -> None:
        self.value: str | None = None
        self.timeout: int | None = None
        self.checked: bool = False

    @property
    def first(self) -> "FakeLocator":
        return self

    def fill(self, value: str, timeout: int) -> None:
        self.value = value
        self.timeout = timeout

    def check(self, timeout: int) -> None:
        self.checked = True
        self.timeout = timeout

    def uncheck(self, timeout: int) -> None:
        self.checked = False
        self.timeout = timeout

    def is_checked(self, timeout: int) -> bool:
        self.timeout = timeout
        return self.checked

    def input_value(self, timeout: int) -> str | None:
        self.timeout = timeout
        return self.value

    def select_option(self, **kwargs: str) -> None:
        if "label" in kwargs:
            self.value = kwargs["label"]
        elif "value" in kwargs:
            self.value = kwargs["value"]

    def evaluate(self, script: str, timeout: int) -> str | None:
        self.timeout = timeout
        return self.value


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

    verification_data = _fill_fields(FakePage(), [email, submit], task_id=task.id, db=session)

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

    assert len(verification_data) == 1
    assert verification_data[0].field_id == email.id
    assert verification_data[0].selector == "#email"
    assert verification_data[0].expected_value == "ada@example.com"
    assert verification_data[0].actual_value == "ada@example.com"
    assert verification_data[0].status == "VERIFIED"

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_fill_fields_returns_verification_data_for_text_input() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    profile = Profile(profile_name="Test profile")
    task = Task(url="https://example.com/form", profile=profile)
    session.add(task)
    session.commit()
    email = FormField(
        task_id=task.id,
        selector="#email",
        field_type="text",
        mapped_value="test@example.com",
    )

    page = FakePage()
    verification_data = _fill_fields(page, [email], task_id=task.id, db=session)

    assert len(verification_data) == 1
    assert verification_data[0].field_id == email.id
    assert verification_data[0].selector == "#email"
    assert verification_data[0].expected_value == "test@example.com"
    assert verification_data[0].actual_value == "test@example.com"
    assert verification_data[0].status == "VERIFIED"

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_fill_fields_returns_verification_data_for_checkbox() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    profile = Profile(profile_name="Test profile")
    task = Task(url="https://example.com/form", profile=profile)
    session.add(task)
    session.commit()
    checkbox = FormField(
        task_id=task.id,
        selector="#agree",
        field_type="checkbox",
        mapped_value="yes",
    )

    page = FakePage()
    verification_data = _fill_fields(page, [checkbox], task_id=task.id, db=session)

    assert len(verification_data) == 1
    assert verification_data[0].field_id == checkbox.id
    assert verification_data[0].selector == "#agree"
    assert verification_data[0].expected_value == "yes"
    assert verification_data[0].actual_value == "true"
    assert verification_data[0].status == "VERIFIED"

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_fill_fields_returns_verification_data_for_select() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    profile = Profile(profile_name="Test profile")
    task = Task(url="https://example.com/form", profile=profile)
    session.add(task)
    session.commit()
    select_field = FormField(
        task_id=task.id,
        selector="#country",
        field_type="select",
        mapped_value="United States",
    )

    page = FakePage()
    verification_data = _fill_fields(page, [select_field], task_id=task.id, db=session)

    assert len(verification_data) == 1
    assert verification_data[0].field_id == select_field.id
    assert verification_data[0].selector == "#country"
    assert verification_data[0].expected_value == "United States"
    assert verification_data[0].actual_value == "United States"
    assert verification_data[0].status == "VERIFIED"

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_fill_fields_skips_sensitive_password_field() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    profile = Profile(profile_name="Test profile")
    task = Task(url="https://example.com/form", profile=profile)
    session.add(task)
    session.commit()
    password = FormField(
        task_id=task.id,
        selector="#password",
        field_type="password",
        mapped_value="secret123",
    )

    page = FakePage()
    verification_data = _fill_fields(page, [password], task_id=task.id, db=session)

    assert len(verification_data) == 1
    assert verification_data[0].field_id == password.id
    assert verification_data[0].selector == "#password"
    assert verification_data[0].expected_value is None
    assert verification_data[0].actual_value is None
    assert verification_data[0].status == "SKIPPED"
    assert verification_data[0].reason == "SENSITIVE_FIELD_SKIPPED"

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()
