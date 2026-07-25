"""Tests for page intake service — deterministic page classification.

Tests construct ExtractedFormAnalysis and PageExtractionResult directly
and pass them to pure functions. No Playwright, no LLM, no database.
"""

from app.services.form_extractor import ExtractedFormAnalysis, ExtractedFormField
from app.services.page_extractor import ExtractedHeading, PageExtractionResult
from app.services.page_intake_service import (
    build_page_intake_result,
    classify_page_intake,
)
from app.workflow_constants import (
    WORKFLOW_TYPE_FORM_FILL,
    WORKFLOW_TYPE_JOB_RESEARCH_SUMMARY,
    WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE,
    WORKFLOW_TYPE_VENDOR_ONBOARDING,
    WORKFLOW_TYPE_WEB_DATA_EXTRACT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _field(
    label: str | None = "Name",
    field_type: str = "text",
    selector: str = "#f1",
    required: bool = True,
    placeholder: str | None = None,
) -> ExtractedFormField:
    return ExtractedFormField(
        element_ref="field_1",
        form_title=None,
        section_title=None,
        label=label,
        selector=selector,
        field_type=field_type,
        placeholder=placeholder,
        name=None,
        html_id=None,
        current_value=None,
        required=required,
    )


def _page(
    title: str = "Page",
    headings: list[str] | None = None,
    text_blocks: list[str] | None = None,
) -> PageExtractionResult:
    return PageExtractionResult(
        title=title,
        headings=[ExtractedHeading(level=2, text=h) for h in (headings or [])],
        main_text_blocks=text_blocks or [],
        links=[],
        tables=[],
        forms=[],
    )


def _form_analysis(
    fields: list[ExtractedFormField] | None = None,
    login_required: bool = False,
) -> ExtractedFormAnalysis:
    return ExtractedFormAnalysis(fields=fields or [], login_required=login_required)


# ---------------------------------------------------------------------------
# Goal 1: security questionnaire signals recommend security_questionnaire
# ---------------------------------------------------------------------------


def test_security_questionnaire_signals_recommend_security_questionnaire():
    fields = [
        _field("Security Question 1", selector="#q1"),
        _field("Security Question 2", selector="#q2"),
    ]
    page = _page(title="Security Questionnaire")

    _page_type, recommended_workflow, _confidence, _evidence = classify_page_intake(
        page, _form_analysis(fields)
    )

    assert recommended_workflow == WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE


# ---------------------------------------------------------------------------
# Goal 2: vendor onboarding signals recommend vendor_onboarding
# ---------------------------------------------------------------------------


def test_vendor_onboarding_signals_recommend_vendor_onboarding():
    fields = [
        _field("Company Name", selector="#company"),
        _field("Tax ID", selector="#taxid"),
    ]
    page = _page()

    _page_type, recommended_workflow, _confidence, _evidence = classify_page_intake(
        page, _form_analysis(fields)
    )

    assert recommended_workflow == WORKFLOW_TYPE_VENDOR_ONBOARDING


# ---------------------------------------------------------------------------
# Goal 3: job page signals recommend job_research_summary
# ---------------------------------------------------------------------------


def test_job_page_signals_recommend_job_research_summary():
    page = _page(
        title="Senior Engineer Position",
        headings=["Job Description", "Responsibilities", "Requirements"],
        text_blocks=["You will be responsible for building and maintaining..."],
    )

    _page_type, recommended_workflow, _confidence, _evidence = classify_page_intake(
        page, _form_analysis([])
    )

    assert recommended_workflow == WORKFLOW_TYPE_JOB_RESEARCH_SUMMARY


# ---------------------------------------------------------------------------
# Goal 4: regular form recommends form_fill
# ---------------------------------------------------------------------------


def test_regular_form_recommends_form_fill():
    fields = [
        _field("First Name", selector="#fn"),
        _field("Last Name", selector="#ln"),
        _field("Email", field_type="email", selector="#email"),
    ]
    page = _page()

    _page_type, recommended_workflow, _confidence, _evidence = classify_page_intake(
        page, _form_analysis(fields)
    )

    assert recommended_workflow == WORKFLOW_TYPE_FORM_FILL


# ---------------------------------------------------------------------------
# Goal 5: no form but has content recommends web_data_extract
# ---------------------------------------------------------------------------


def test_content_page_without_form_recommends_web_data_extract():
    page = _page(
        title="Welcome",
        headings=["Introduction"],
        text_blocks=["This is a general information page."],
    )

    _page_type, recommended_workflow, _confidence, _evidence = classify_page_intake(
        page, _form_analysis([])
    )

    assert recommended_workflow == WORKFLOW_TYPE_WEB_DATA_EXTRACT


# ---------------------------------------------------------------------------
# Goal 6: login_required adds risk flag and blocked reason
# ---------------------------------------------------------------------------


def test_login_required_flagged_and_blocked():
    result = build_page_intake_result(
        url="https://example.com",
        page=_page(),
        form_analysis=_form_analysis([], login_required=True),
    )

    assert "login_required" in result.risk_flags
    assert "Manual login is required before automation can continue." in result.blocked_reasons


# ---------------------------------------------------------------------------
# Goal 7: password / otp / payment fields are flagged as risks
# ---------------------------------------------------------------------------


def test_sensitive_fields_flagged_as_risks():
    fields = [
        _field("Password", field_type="password", selector="#pw"),
        _field("Verification Code", selector="#otp"),
        _field("Credit Card Number", selector="#cc"),
    ]
    result = build_page_intake_result(
        url="https://example.com",
        page=_page(),
        form_analysis=_form_analysis(fields),
    )

    assert "password" in result.risk_flags
    assert "otp" in result.risk_flags
    assert "payment" in result.risk_flags


# ---------------------------------------------------------------------------
# Rule quality: false-positive prevention
# ---------------------------------------------------------------------------


def test_company_and_contact_fields_do_not_trigger_vendor():
    """A regular form with Company + Contact Email should not be vendor_intake."""

    fields = [
        _field("Company", selector="#company"),
        _field("Contact Email", field_type="email", selector="#contact"),
    ]
    page = _page(title="Contact Us")

    _page_type, recommended_workflow, _confidence, _evidence = classify_page_intake(
        page, _form_analysis(fields)
    )

    assert recommended_workflow == WORKFLOW_TYPE_FORM_FILL


def test_syntax_text_does_not_match_tax_vendor():
    """The word 'syntax' should not trigger the 'tax' vendor keyword."""

    page = _page(
        title="Developer Guide",
        text_blocks=["This page explains syntax rules for developers."],
    )

    _page_type, recommended_workflow, _confidence, _evidence = classify_page_intake(
        page, _form_analysis([])
    )

    assert recommended_workflow == WORKFLOW_TYPE_WEB_DATA_EXTRACT


def test_postal_code_field_is_not_otp():
    """A 'Postal Code' field should not be flagged as OTP."""

    fields = [_field("Postal Code", selector="#postal")]
    result = build_page_intake_result(
        url="https://example.com",
        page=_page(),
        form_analysis=_form_analysis(fields),
    )

    assert "otp" not in result.risk_flags
