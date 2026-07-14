"""Local source-backed answer suggestions for questionnaire-style workflows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.database import BACKEND_DIR
from app.models import FormField
from app.services.retrieval_service import jaccard_similarity
from app.services.workflow_memory import is_memory_eligible_field


DEFAULT_POLICY_PATHS = [
    BACKEND_DIR / "examples" / "mock-security-policy.md",
]


@dataclass(frozen=True)
class PolicyAnswerSuggestion:
    answer: str
    source: str
    matched_section: str
    score: float
    status: str = "needs_review"


def _sections(markdown: str) -> list[tuple[str, str]]:
    current_title = ""
    current_lines: list[str] = []
    sections: list[tuple[str, str]] = []

    for line in markdown.splitlines():
        heading = re.match(r"^##\s+(.+)$", line.strip())
        if heading:
            if current_title:
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = heading.group(1).strip()
            current_lines = []
            continue
        if current_title:
            current_lines.append(line)

    if current_title:
        sections.append((current_title, "\n".join(current_lines).strip()))
    return sections


def _answer_from_body(body: str) -> str | None:
    for line in body.splitlines():
        match = re.match(r"^\s*Answer:\s*(.+)\s*$", line)
        if match:
            return match.group(1).strip()
    return None


def suggest_policy_answer(
    question: str,
    *,
    policy_paths: list[Path] | None = None,
) -> PolicyAnswerSuggestion | None:
    """Return the best local policy answer for a question, or None when unsupported."""

    best: PolicyAnswerSuggestion | None = None
    for path in policy_paths or DEFAULT_POLICY_PATHS:
        if not path.exists():
            continue
        for title, body in _sections(path.read_text(encoding="utf-8")):
            answer = _answer_from_body(body)
            if not answer:
                continue
            score = jaccard_similarity(question, f"{title}\n{body}")
            if score < 0.2:
                continue
            suggestion = PolicyAnswerSuggestion(
                answer=answer,
                source=path.name,
                matched_section=title,
                score=round(score, 4),
            )
            if best is None or suggestion.score > best.score:
                best = suggestion
    return best


def _field_question(field: FormField) -> str:
    return " ".join(
        value
        for value in [
            field.label,
            field.name,
            field.placeholder,
            field.section_title,
            field.form_title,
        ]
        if value
    )


def _custom_key(field: FormField) -> str:
    text = (field.label or field.name or field.selector or "policy_answer").lower()
    key = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return f"custom:{key or 'policy_answer'}"


def _coerce_to_option_value(field: FormField, answer: str) -> str:
    options = field.options
    if not options:
        return answer
    normalized_answer = answer.strip().lower().rstrip(".")
    for option in options:
        label = str(option.get("label") or "").strip()
        value = str(option.get("value") or "").strip()
        if normalized_answer in {label.lower(), value.lower()}:
            return value or label
    return answer


def apply_policy_answer_suggestions(
    *,
    fields: list[FormField],
    policy_paths: list[Path] | None = None,
) -> list[dict[str, object]]:
    """Apply source-backed questionnaire suggestions to unmapped safe fields."""

    evidence: list[dict[str, object]] = []
    for field in fields:
        if field.mapped_value not in (None, ""):
            continue
        if not is_memory_eligible_field(field):
            continue
        suggestion = suggest_policy_answer(
            _field_question(field),
            policy_paths=policy_paths,
        )
        if suggestion is None:
            continue
        mapped_value = _coerce_to_option_value(field, suggestion.answer)
        field.mapped_value = mapped_value
        field.mapped_profile_key = _custom_key(field)
        field.confidence = 0.66
        evidence.append(
            {
                "field_id": field.id,
                "field_label": field.label,
                "suggested_value": mapped_value,
                "source": suggestion.source,
                "matched_section": suggestion.matched_section,
                "score": suggestion.score,
                "status": suggestion.status,
            }
        )
    return evidence
