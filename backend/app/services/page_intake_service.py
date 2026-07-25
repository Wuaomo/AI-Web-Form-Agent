"""Deterministic page intake service for workflow selection.

Analyzes a page using FormExtractor and PageExtractor results and returns
a structured intake result with page_type, recommended_workflow, confidence,
summary, detected_fields, risk_flags, blocked_reasons, and evidence.

No LLM calls. No database writes. Pure deterministic rules.
"""

import re

from dataclasses import dataclass, field

from app.services.form_extractor import ExtractedFormAnalysis
from app.services.page_extractor import PageExtractionResult
from app.workflow_constants import (
    WORKFLOW_TYPE_FORM_FILL,
    WORKFLOW_TYPE_JOB_RESEARCH_SUMMARY,
    WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE,
    WORKFLOW_TYPE_VENDOR_ONBOARDING,
    WORKFLOW_TYPE_WEB_DATA_EXTRACT,
)

# ---------------------------------------------------------------------------
# Classification keyword sets (Step 3) — English + Chinese where useful.
# ---------------------------------------------------------------------------

_QUESTIONNAIRE_TEXT_KEYWORDS = (
    "security",
    "compliance",
    "questionnaire",
    "policy",
    "privacy",
    "encryption",
    "audit",
    "access control",
    "vendor risk",
)

_VENDOR_STRONG_KEYWORDS = (
    "vendor",
    "supplier",
    "onboarding",
    "w-9",
)

_VENDOR_WEAK_KEYWORDS = (
    "company",
    "tax",
    "bank",
    "contact name",
)

_JOB_TEXT_KEYWORDS = (
    "job",
    "responsibilities",
    "requirements",
    "location",
    "salary",
    "apply",
)

# ---------------------------------------------------------------------------
# Risk keyword sets (Step 4)
# ---------------------------------------------------------------------------

_PASSWORD_KEYWORDS = ("password",)
_OTP_KEYWORDS = (
    "otp",
    "one time",
    "one-time",
    "one-time code",
    "verification code",
    "security code",
)
_PAYMENT_KEYWORDS = ("payment", "card", "billing", "credit")
_CAPTCHA_KEYWORDS = ("captcha",)
_DESTRUCTIVE_KEYWORDS = (
    "delete",
    "remove",
    "purchase",
    "cancel subscription",
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PageIntakeEvidence:
    """A single piece of evidence supporting the page classification."""

    source: str
    text: str
    reason: str


@dataclass(frozen=True)
class PageIntakeDetectedField:
    """A simplified form field detected during page intake."""

    label: str | None
    field_type: str
    required: bool
    selector: str


@dataclass(frozen=True)
class PageIntakeResult:
    """Structured page intake analysis result."""

    page_type: str
    recommended_workflow: str
    confidence: float
    summary: str
    detected_fields: list[PageIntakeDetectedField] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    evidence: list[PageIntakeEvidence] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_text(
    page: PageExtractionResult,
    form_analysis: ExtractedFormAnalysis,
    user_goal: str,
) -> str:
    """Combine all text sources into a single lowercase string for matching."""

    parts: list[str] = [page.title or "", user_goal]
    parts.extend(heading.text or "" for heading in page.headings)
    parts.extend(page.main_text_blocks)
    parts.extend(f.label or "" for f in form_analysis.fields)
    parts.extend(f.placeholder or "" for f in form_analysis.fields)
    return " ".join(parts).lower()


def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    """Compile a keyword into a word-boundary regex for safe matching.

    Keywords without non-word characters (e.g. "w-9", "one-time") use
    lookaround boundaries; plain words use \\b.
    """

    escaped = re.escape(keyword)
    if re.search(r"\W", keyword):
        return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


def _matches_any(text: str, keywords: tuple[str, ...]) -> bool:
    """Return True if any keyword matches as a whole word/phrase in text."""

    return any(_keyword_pattern(keyword).search(text) for keyword in keywords)


def _matched_keywords(text: str, keywords: tuple[str, ...]) -> list[str]:
    """Return the list of keywords that match as whole words/phrases in text."""

    return [keyword for keyword in keywords if _keyword_pattern(keyword).search(text)]


def _count_questions(
    form_analysis: ExtractedFormAnalysis,
    page: PageExtractionResult,
) -> int:
    """Count how many field labels or headings look like question sentences."""

    count = 0
    for f in form_analysis.fields:
        if f.label and "?" in f.label:
            count += 1
    for heading in page.headings:
        if heading.text and "?" in heading.text:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Step 3: classify_page_intake
# ---------------------------------------------------------------------------


def classify_page_intake(
    page: PageExtractionResult,
    form_analysis: ExtractedFormAnalysis,
    user_goal: str = "",
) -> tuple[str, str, float, list[PageIntakeEvidence]]:
    """Classify a page and recommend a workflow.

    Returns (page_type, recommended_workflow, confidence, evidence).
    No LLM, no network — pure deterministic keyword and signal matching.
    """

    text = _collect_text(page, form_analysis, user_goal)
    evidence: list[PageIntakeEvidence] = []

    # Rule 1: questionnaire — security/compliance keywords or multiple questions.
    questionnaire_matches = _matched_keywords(text, _QUESTIONNAIRE_TEXT_KEYWORDS)
    question_count = _count_questions(form_analysis, page)

    if questionnaire_matches or question_count >= 2:
        if questionnaire_matches:
            evidence.append(PageIntakeEvidence(
                source="page_text",
                text=f"matched: {', '.join(questionnaire_matches)}",
                reason="Page text contains security/compliance questionnaire signals",
            ))
        if question_count >= 2:
            evidence.append(PageIntakeEvidence(
                source="form_fields",
                text=f"{question_count} question(s) detected in labels/headings",
                reason="Multiple question sentences suggest a questionnaire",
            ))
        return ("questionnaire", WORKFLOW_TYPE_SECURITY_QUESTIONNAIRE, 0.85, evidence)

    # Rule 2: vendor onboarding — strong keywords alone, or 2+ weak + form fields.
    strong_vendor_matches = _matched_keywords(text, _VENDOR_STRONG_KEYWORDS)
    weak_vendor_matches = _matched_keywords(text, _VENDOR_WEAK_KEYWORDS)

    if strong_vendor_matches or (len(weak_vendor_matches) >= 2 and form_analysis.fields):
        all_matches = strong_vendor_matches + weak_vendor_matches
        evidence.append(PageIntakeEvidence(
            source="page_text",
            text=f"matched: {', '.join(all_matches)}",
            reason="Page text contains vendor/supplier onboarding signals",
        ))
        return ("vendor_intake", WORKFLOW_TYPE_VENDOR_ONBOARDING, 0.82, evidence)

    # Rule 3: job page — job keywords with fewer than 3 form fields.
    job_matches = _matched_keywords(text, _JOB_TEXT_KEYWORDS)
    if job_matches and len(form_analysis.fields) < 3:
        evidence.append(PageIntakeEvidence(
            source="page_text",
            text=f"matched: {', '.join(job_matches)}",
            reason="Page text contains job listing signals with few form fields",
        ))
        return ("job_page", WORKFLOW_TYPE_JOB_RESEARCH_SUMMARY, 0.8, evidence)

    # Rule 4: form — has editable fields.
    if form_analysis.fields:
        evidence.append(PageIntakeEvidence(
            source="form_analysis",
            text=f"{len(form_analysis.fields)} field(s) detected",
            reason="Page has form fields suitable for form fill workflow",
        ))
        return ("form", WORKFLOW_TYPE_FORM_FILL, 0.75, evidence)

    # Rule 5: article — has text content but no form.
    if page.main_text_blocks or page.headings:
        evidence.append(PageIntakeEvidence(
            source="page_content",
            text=(
                f"{len(page.headings)} heading(s), "
                f"{len(page.main_text_blocks)} text block(s)"
            ),
            reason="Page has text content suitable for data extraction",
        ))
        return ("article", WORKFLOW_TYPE_WEB_DATA_EXTRACT, 0.65, evidence)

    # Rule 6: fallback.
    evidence.append(PageIntakeEvidence(
        source="fallback",
        text="no classification signals detected",
        reason="Unable to classify page, defaulting to web data extraction",
    ))
    return ("unknown", WORKFLOW_TYPE_WEB_DATA_EXTRACT, 0.4, evidence)


# ---------------------------------------------------------------------------
# Step 4: build_page_intake_result
# ---------------------------------------------------------------------------


def build_page_intake_result(
    *,
    url: str,
    page: PageExtractionResult,
    form_analysis: ExtractedFormAnalysis,
    user_goal: str = "",
) -> PageIntakeResult:
    """Build a full page intake result with risk flags and evidence.

    Calls classify_page_intake for classification, then enriches with
    detected fields, risk flags, blocked reasons, and a summary.
    """

    page_type, recommended_workflow, confidence, evidence = classify_page_intake(
        page, form_analysis, user_goal
    )

    # Detected fields — simplified view of form_analysis.fields.
    detected_fields = [
        PageIntakeDetectedField(
            label=f.label,
            field_type=f.field_type,
            required=f.required,
            selector=f.selector,
        )
        for f in form_analysis.fields
    ]

    # Collect field text for risk detection.
    field_text_parts: list[str] = []
    for f in form_analysis.fields:
        field_text_parts.extend([
            f.label or "",
            f.name or "",
            f.placeholder or "",
            f.field_type or "",
        ])
    field_text = " ".join(field_text_parts).lower()

    # Collect page text and link text for captcha/destructive detection.
    page_text_parts: list[str] = [page.title or ""]
    page_text_parts.extend(h.text or "" for h in page.headings)
    page_text_parts.extend(page.main_text_blocks)
    page_text = " ".join(page_text_parts).lower()

    link_text = " ".join(link.text or "" for link in page.links).lower()

    # Risk flags.
    risk_flags: list[str] = []

    if form_analysis.login_required:
        risk_flags.append("login_required")
    if _matches_any(field_text, _PASSWORD_KEYWORDS):
        risk_flags.append("password")
    if _matches_any(field_text, _OTP_KEYWORDS):
        risk_flags.append("otp")
    if _matches_any(field_text, _PAYMENT_KEYWORDS):
        risk_flags.append("payment")
    if _matches_any(page_text, _CAPTCHA_KEYWORDS):
        risk_flags.append("captcha")
    if _matches_any(f"{page_text} {link_text}", _DESTRUCTIVE_KEYWORDS):
        risk_flags.append("destructive_action")

    # Blocked reasons — human-readable explanations for each blocking risk.
    blocked_reasons: list[str] = []
    if "login_required" in risk_flags:
        blocked_reasons.append(
            "Manual login is required before automation can continue."
        )
    if "captcha" in risk_flags:
        blocked_reasons.append("CAPTCHA cannot be automated.")
    if "otp" in risk_flags:
        blocked_reasons.append("One-time codes cannot be stored or automated.")
    if "payment" in risk_flags:
        blocked_reasons.append("Payment fields are blocked from automation.")

    # Summary.
    summary = (
        f"Detected {page_type} page with {len(form_analysis.fields)} field(s). "
        f"Recommended workflow: {recommended_workflow}."
    )

    return PageIntakeResult(
        page_type=page_type,
        recommended_workflow=recommended_workflow,
        confidence=confidence,
        summary=summary,
        detected_fields=detected_fields,
        risk_flags=risk_flags,
        blocked_reasons=blocked_reasons,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Step 5: async entry point
# ---------------------------------------------------------------------------


async def analyze_page_intake(
    *,
    url: str,
    profile_id: int,
    user_goal: str = "",
) -> PageIntakeResult:
    """Open a page, extract form and content data, then run intake analysis.

    Orchestrates FormExtractor and PageExtractor, then delegates to
    build_page_intake_result for deterministic classification.

    Does not swallow exceptions, write to the database, capture screenshots,
    or call any LLM provider.
    """

    from app.services.form_extractor import extract_form_analysis
    from app.services.page_extractor import extract_page

    form_analysis = await extract_form_analysis(url, profile_id)
    page = await extract_page(url, profile_id)

    return build_page_intake_result(
        url=url,
        page=page,
        form_analysis=form_analysis,
        user_goal=user_goal,
    )
