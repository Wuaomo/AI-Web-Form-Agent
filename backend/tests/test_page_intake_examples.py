"""Integration tests for page intake — real local HTML fixtures through analyze_page_intake()."""

from pathlib import Path

import pytest
from playwright.async_api import Error as PlaywrightError

from app.services.page_intake_service import analyze_page_intake


def example_url(filename: str) -> str:
    path = Path(__file__).parent.parent / "examples" / filename
    return f"file:///{path.resolve()}"


@pytest.mark.anyio
async def test_security_questionnaire_demo_recommends_security_questionnaire():
    try:
        result = await analyze_page_intake(
            url=example_url("security-questionnaire.html"),
            profile_id=1,
        )
    except PlaywrightError as exc:
        pytest.skip(f"Chromium is not installed for Playwright: {exc}")

    assert result.recommended_workflow == "security_questionnaire"


@pytest.mark.anyio
async def test_vendor_onboarding_demo_recommends_vendor_onboarding():
    try:
        result = await analyze_page_intake(
            url=example_url("vendor-onboarding.html"),
            profile_id=1,
        )
    except PlaywrightError as exc:
        pytest.skip(f"Chromium is not installed for Playwright: {exc}")

    assert result.recommended_workflow == "vendor_onboarding"


@pytest.mark.anyio
async def test_job_research_page_demo_recommends_job_research_summary():
    try:
        result = await analyze_page_intake(
            url=example_url("job-research-page.html"),
            profile_id=1,
        )
    except PlaywrightError as exc:
        pytest.skip(f"Chromium is not installed for Playwright: {exc}")

    assert result.recommended_workflow == "job_research_summary"