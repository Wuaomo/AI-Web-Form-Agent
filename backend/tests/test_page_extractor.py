"""Tests for page extraction service."""

from pathlib import Path

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from app.services.page_extractor import (
    ExtractedForm,
    ExtractedHeading,
    ExtractedLink,
    ExtractedTable,
    extract_page_sync,
)


@pytest.fixture
def research_page_url() -> str:
    """Return file URL for the local research page example."""

    examples_dir = Path(__file__).parent.parent / "examples"
    page_path = examples_dir / "research-page.html"
    return f"file:///{page_path.resolve()}"


def extract_from_url(url: str) -> object:
    """Render a page and run the production extractor."""

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except PlaywrightError as exc:
            pytest.skip(f"Chromium is not installed for Playwright: {exc}")

        page = browser.new_page()
        result = extract_page_sync(page, url)
        browser.close()

    return result


def test_extract_page_title(research_page_url: str) -> None:
    """Verify page title is extracted correctly."""

    result = extract_from_url(research_page_url)

    assert result.title == "Research Job Description: Senior AI Engineer"


def test_extract_page_headings(research_page_url: str) -> None:
    """Verify headings are extracted with correct levels and text."""

    result = extract_from_url(research_page_url)

    assert len(result.headings) >= 6
    assert result.headings[0] == ExtractedHeading(level=1, text="Senior AI Engineer - Machine Learning Platform")
    assert any(h.text == "About the Role" for h in result.headings)
    assert any(h.text == "Key Responsibilities" for h in result.headings)
    assert any(h.text == "Requirements" for h in result.headings)
    assert any(h.text == "Technical Skills" for h in result.headings if h.level == 3)


def test_extract_page_links(research_page_url: str) -> None:
    """Verify links are extracted with text and href."""

    result = extract_from_url(research_page_url)

    assert len(result.links) >= 3
    assert any(link.text == "careers page" for link in result.links)
    assert any(link.text == "careers@example.com" for link in result.links)
    assert any("linkedin" in link.href.lower() for link in result.links)


def test_extract_page_tables(research_page_url: str) -> None:
    """Verify tables are extracted with headers and rows."""

    result = extract_from_url(research_page_url)

    assert len(result.tables) == 1
    table = result.tables[0]
    assert table.headers == ["Benefit", "Details"]
    assert len(table.rows) == 3
    assert table.rows[0][0] == "Health Insurance"
    assert table.rows[1][0] == "Stock Options"
    assert table.rows[2][0] == "Remote Work"


def test_extract_page_forms(research_page_url: str) -> None:
    """Verify forms are extracted with action, method, and field count."""

    result = extract_from_url(research_page_url)

    assert len(result.forms) == 1
    form = result.forms[0]
    assert form.action is not None
    assert form.method == "POST"
    assert form.field_count >= 4


def test_extract_page_text_blocks(research_page_url: str) -> None:
    """Verify main text blocks are extracted."""

    result = extract_from_url(research_page_url)

    assert len(result.main_text_blocks) > 0
    assert any("We are looking for a Senior AI Engineer" in block for block in result.main_text_blocks)