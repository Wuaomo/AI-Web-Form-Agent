"""Deterministic rules-based research summary service."""

from dataclasses import dataclass, field
from typing import Any

REQUIREMENT_KEYWORDS = [
    "requirement",
    "requirements",
    "qualification",
    "qualifications",
    "skill",
    "skills",
    "experience",
    "education",
    "degree",
    "technical",
    "knowledge",
    "ability",
    "abilities",
    "must have",
    "need",
    "needed",
    "expectation",
    "expectations",
    "responsibility",
    "responsibilities",
    "duty",
    "duties",
    "what you'll do",
    "key responsibility",
    "key responsibilities",
]

EXPERIENCE_KEYWORDS = [
    "years",
    "year",
    "experience",
    "experienced",
    "expert",
    "senior",
    "junior",
    "mid-level",
    "entry-level",
]

TECH_KEYWORDS = [
    "python",
    "java",
    "javascript",
    "typescript",
    "go",
    "rust",
    "c++",
    "sql",
    "machine learning",
    "ml",
    "deep learning",
    "ai",
    "tensorflow",
    "pytorch",
    "kubernetes",
    "docker",
    "aws",
    "azure",
    "gcp",
    "spark",
    "big data",
    "data engineering",
    "software engineering",
    "backend",
    "frontend",
    "full stack",
    "devops",
    "cloud",
]


@dataclass(frozen=True)
class ResearchSummary:
    """Structured research summary report."""

    summary: str
    key_requirements: list[str]
    action_checklist: list[str]
    risks: list[str]


def _find_section(extraction_data: dict[str, Any], keywords: list[str]) -> list[str]:
    """Find text content from headings and text blocks that match keywords."""

    results = []
    text_pool = []

    if extraction_data.get("headings"):
        for heading in extraction_data["headings"]:
            text_pool.append((heading.get("text", ""), heading.get("level", 1)))

    if extraction_data.get("main_text_blocks"):
        for block in extraction_data["main_text_blocks"]:
            text_pool.append((block, 99))

    for text, level in text_pool:
        lower_text = text.lower()
        for keyword in keywords:
            if keyword.lower() in lower_text:
                results.append(text)
                break

    return results


def _extract_years_of_experience(text: str) -> list[str]:
    """Extract years of experience requirements from text."""

    import re
    matches = re.findall(r"(\d+)\s*\+?\s*(?:year|years)\s*(?:of\s+)?experience?", text, re.IGNORECASE)
    return [f"{m} years of experience" for m in matches]


def _extract_tech_skills(text: str) -> list[str]:
    """Extract technology skills from text."""

    found = []
    lower_text = text.lower()
    for tech in TECH_KEYWORDS:
        if tech.lower() in lower_text and tech not in found:
            found.append(tech.title())
    return found


def _build_requirements(extraction_data: dict[str, Any]) -> list[str]:
    """Build key requirements list from extraction data."""

    requirements = []
    requirement_sections = _find_section(extraction_data, REQUIREMENT_KEYWORDS)

    for section in requirement_sections:
        years = _extract_years_of_experience(section)
        requirements.extend(years)

        skills = _extract_tech_skills(section)
        requirements.extend(skills)

        if len(section) > 20:
            requirements.append(section[:100] + "..." if len(section) > 100 else section)

    if not requirements:
        if extraction_data.get("title"):
            requirements.append(f"Review job posting: {extraction_data['title']}")
        requirements.append("No specific requirements identified")

    return list(dict.fromkeys(requirements))[:10]


def _build_checklist(extraction_data: dict[str, Any]) -> list[str]:
    """Build action checklist from extraction data."""

    checklist = []

    if extraction_data.get("forms") and len(extraction_data["forms"]) > 0:
        checklist.append("Complete application form")

    if extraction_data.get("links"):
        for link in extraction_data["links"][:5]:
            href = link.get("href", "")
            text = link.get("text", "")
            if "apply" in text.lower() or "apply" in href.lower():
                checklist.append(f"Submit application via {text or href}")
            elif "resume" in text.lower() or "cv" in text.lower():
                checklist.append(f"Upload resume/CV via {text or href}")
            elif "career" in text.lower():
                checklist.append(f"Check careers page: {text or href}")

    if extraction_data.get("title"):
        checklist.append(f"Prepare cover letter for: {extraction_data['title']}")

    if extraction_data.get("tables") and len(extraction_data["tables"]) > 0:
        checklist.append("Review benefits and compensation details")

    if not checklist:
        checklist.append("Review the full job description")
        checklist.append("Prepare application materials")

    return list(dict.fromkeys(checklist))[:8]


def _build_risks(extraction_data: dict[str, Any]) -> list[str]:
    """Build risks/missing information list from extraction data."""

    risks = []

    if not extraction_data.get("title") or extraction_data["title"] == "":
        risks.append("Job title not found")

    requirements = _find_section(extraction_data, REQUIREMENT_KEYWORDS)
    if not requirements:
        risks.append("Requirements section not clearly identified")

    if not extraction_data.get("links") or len(extraction_data["links"]) == 0:
        risks.append("No application links found")
    else:
        has_apply_link = any(
            "apply" in link.get("text", "").lower() or "apply" in link.get("href", "").lower()
            for link in extraction_data["links"]
        )
        if not has_apply_link:
            risks.append("Apply link not clearly marked")

    if not extraction_data.get("forms") or len(extraction_data["forms"]) == 0:
        risks.append("No application form found")

    if not risks:
        risks.append("No obvious risks identified")

    return risks


def _build_summary(extraction_data: dict[str, Any], goal: str) -> str:
    """Build summary text from extraction data."""

    title = extraction_data.get("title", "Unknown Page")
    heading_count = extraction_data.get("heading_count", 0)
    link_count = extraction_data.get("link_count", 0)
    table_count = extraction_data.get("table_count", 0)
    form_count = extraction_data.get("form_count", 0)

    if goal:
        summary = f"Research Summary for: {goal}\n\n"
    else:
        summary = "Research Summary\n\n"

    summary += f"Page Title: {title}\n"
    summary += f"Content Overview: {heading_count} headings, {link_count} links, {table_count} tables, {form_count} forms\n\n"

    requirement_sections = _find_section(extraction_data, REQUIREMENT_KEYWORDS)
    if requirement_sections:
        summary += "Key Findings:\n"
        for i, section in enumerate(requirement_sections[:3], 1):
            summary += f"{i}. {section[:150]}{'...' if len(section) > 150 else ''}\n"
    else:
        summary += "Key Findings: No structured requirements found in page content.\n"

    return summary


def generate_research_summary(extraction_data: dict[str, Any], goal: str = "") -> ResearchSummary:
    """Generate a deterministic research summary from extraction data using rules."""

    if not extraction_data or not isinstance(extraction_data, dict):
        return ResearchSummary(
            summary="No extraction data available for summarization.",
            key_requirements=["No data available"],
            action_checklist=["Re-run extraction to generate summary"],
            risks=["No extraction data found"],
        )

    return ResearchSummary(
        summary=_build_summary(extraction_data, goal),
        key_requirements=_build_requirements(extraction_data),
        action_checklist=_build_checklist(extraction_data),
        risks=_build_risks(extraction_data),
    )