"""Tests for the deterministic research summary service."""

import pytest

from app.services.research_summary import generate_research_summary


def test_generate_research_summary_with_job_page_data() -> None:
    """Verify summary extracts key requirements and checklist from job page data."""

    extraction_data = {
        "title": "Senior AI Engineer - Machine Learning Platform",
        "heading_count": 8,
        "headings": [
            {"level": 1, "text": "Senior AI Engineer - Machine Learning Platform"},
            {"level": 2, "text": "About the Role"},
            {"level": 2, "text": "Key Responsibilities"},
            {"level": 2, "text": "Requirements"},
            {"level": 3, "text": "Technical Skills"},
            {"level": 3, "text": "Education"},
            {"level": 2, "text": "Benefits"},
            {"level": 2, "text": "Apply Now"},
        ],
        "main_text_blocks": [
            "We are looking for a Senior AI Engineer to join our machine learning platform team.",
            "5+ years of experience in machine learning. Strong Python programming skills.",
            "Experience with TensorFlow, PyTorch, or similar frameworks.",
            "Bachelor's or Master's degree in Computer Science, Mathematics, or related field.",
        ],
        "link_count": 3,
        "links": [
            {"text": "careers page", "href": "https://example.com/careers"},
            {"text": "Apply Now", "href": "https://example.com/apply"},
            {"text": "LinkedIn", "href": "https://linkedin.com/company/example"},
        ],
        "table_count": 1,
        "tables": [
            {"headers": ["Benefit", "Details"], "row_count": 3},
        ],
        "form_count": 1,
        "forms": [
            {"action": "/apply", "method": "POST", "field_count": 4},
        ],
    }

    result = generate_research_summary(extraction_data, goal="Research Senior AI Engineer role")

    assert "Senior AI Engineer" in result.summary
    assert "Requirements" in result.summary

    assert any("5 years" in req for req in result.key_requirements)
    assert any("Python" in req for req in result.key_requirements)
    assert any("TensorFlow" in req for req in result.key_requirements)
    assert any("PyTorch" in req for req in result.key_requirements)

    assert any("Complete application" in item for item in result.action_checklist)
    assert any("Submit application" in item for item in result.action_checklist)
    assert any("cover letter" in item.lower() for item in result.action_checklist)
    assert any("benefits" in item.lower() for item in result.action_checklist)

    assert len(result.risks) == 1
    assert "No obvious risks" in result.risks[0]


def test_generate_research_summary_with_empty_data() -> None:
    """Verify fallback behavior when no extraction data is provided."""

    result = generate_research_summary({})

    assert "No extraction data" in result.summary
    assert "No data available" in result.key_requirements
    assert any("Re-run extraction" in item for item in result.action_checklist)


def test_generate_research_summary_with_no_requirements() -> None:
    """Verify fallback when no job-specific fields are found."""

    extraction_data = {
        "title": "Generic Page",
        "heading_count": 2,
        "headings": [
            {"level": 1, "text": "Welcome to Our Site"},
            {"level": 2, "text": "About Us"},
        ],
        "main_text_blocks": [
            "This is a generic page with no job-related content.",
        ],
        "link_count": 1,
        "links": [
            {"text": "Home", "href": "https://example.com"},
        ],
        "table_count": 0,
        "tables": [],
        "form_count": 0,
        "forms": [],
    }

    result = generate_research_summary(extraction_data)

    assert "Generic Page" in result.summary
    assert "No specific requirements identified" in result.key_requirements
    assert "Requirements section not clearly identified" in result.risks
    assert "No application form found" in result.risks


def test_generate_research_summary_with_partial_data() -> None:
    """Verify summary works with partial extraction data."""

    extraction_data = {
        "title": "Job Posting",
        "heading_count": 1,
        "headings": [
            {"level": 1, "text": "Job Posting"},
        ],
        "link_count": 2,
        "links": [
            {"text": "Apply Here", "href": "https://example.com/apply"},
        ],
        "form_count": 1,
        "forms": [
            {"action": "/submit", "method": "POST", "field_count": 3},
        ],
    }

    result = generate_research_summary(extraction_data)

    assert "Job Posting" in result.summary
    assert any("Submit application" in item for item in result.action_checklist)
    assert any("Complete application" in item for item in result.action_checklist)


def test_generate_research_summary_without_title() -> None:
    """Verify summary handles missing title."""

    extraction_data = {
        "heading_count": 2,
        "headings": [
            {"level": 1, "text": "Some Content"},
            {"level": 2, "text": "Requirements"},
        ],
        "main_text_blocks": [
            "3+ years of experience required.",
        ],
    }

    result = generate_research_summary(extraction_data)

    assert "Unknown Page" in result.summary
    assert any("3 years" in req for req in result.key_requirements)
    assert "Job title not found" in result.risks