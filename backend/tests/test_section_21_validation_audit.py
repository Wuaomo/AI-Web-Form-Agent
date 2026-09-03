from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_DOC = REPO_ROOT / "docs" / "section-21-validation-audit.md"


def test_section_21_validation_audit_indexes_runtime_object_evidence() -> None:
    """Verify the section 21 audit maps each runtime object to test evidence."""

    text = AUDIT_DOC.read_text(encoding="utf-8")

    for runtime_object in [
        "AgentRun",
        "AgentPlan",
        "ToolCall",
        "ToolResult",
        "Proposal",
        "EvidenceItem",
        "ReviewDecision",
        "GovernanceDecision",
        "VerificationResult",
    ]:
        assert f"| `{runtime_object}` |" in text


def test_section_21_validation_audit_indexes_completion_criteria() -> None:
    """Verify every RFC section 21 criterion has an audit row."""

    text = AUDIT_DOC.read_text(encoding="utf-8")

    for criterion in [
        "Runtime object persistence",
        "Generic governed graph demo path",
        "Internal browser read/write Tool Runtime path",
        "Browser write and submit governance",
        "Review Queue primary proposal entry",
        "Run Cockpit compact state",
        "No-key deterministic demos and benchmark replay",
        "Read-only external tools",
        "External write tools",
        "Docs and demo alignment",
    ]:
        assert f"| {criterion} |" in text


def test_section_21_validation_audit_marks_no_key_demo_paths_covered() -> None:
    """Verify no-key demo coverage is not left as an audit gap."""

    text = AUDIT_DOC.read_text(encoding="utf-8")

    assert re.search(
        r"\| No-key deterministic demos and benchmark replay \| covered \|",
        text,
    )


def test_section_21_validation_audit_indexes_raw_output_exposure() -> None:
    """Verify raw runtime outputs are audited at each user-facing boundary."""

    text = AUDIT_DOC.read_text(encoding="utf-8")

    assert "## Raw Output Exposure Matrix" in text
    for boundary in [
        "Task facade",
        "Run Cockpit",
        "Review Queue",
        "External read-only tools",
        "Backend persistence",
    ]:
        assert f"| {boundary} |" in text
