"""Tests for static workflow template definitions."""

import pytest

from app.workflow_templates import (
    get_workflow_template,
    list_workflow_templates,
    require_enabled_template,
)


def test_list_workflow_templates_includes_form_fill() -> None:
    """Verify the primary form-fill template is always listed."""

    templates = list_workflow_templates()

    form_fill = next(template for template in templates if template["id"] == "form_fill")
    assert form_fill["enabled"] is True


def test_list_workflow_templates_can_include_disabled_templates() -> None:
    """Verify disabled templates remain visible for future-facing UI."""

    templates = list_workflow_templates(include_disabled=True)

    assert any(template["id"] == "web_data_extract" for template in templates)


def test_get_workflow_template_returns_none_for_missing_template() -> None:
    """Verify unknown template ids return None instead of raising."""

    assert get_workflow_template("missing_template") is None


def test_require_enabled_template_accepts_form_fill() -> None:
    """Verify the enabled form-fill template passes validation."""

    template = require_enabled_template("form_fill")

    assert template["id"] == "form_fill"


def test_require_enabled_template_rejects_disabled_template() -> None:
    """Verify disabled templates cannot be used to create tasks."""

    with pytest.raises(ValueError, match="Workflow template is not enabled: data_entry"):
        require_enabled_template("data_entry")


def test_require_enabled_template_rejects_missing_template() -> None:
    """Verify missing template ids raise a descriptive validation error."""

    with pytest.raises(ValueError, match="Workflow template not found: missing_template"):
        require_enabled_template("missing_template")
