from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_DOC = REPO_ROOT / "docs" / "section-21-validation-audit.md"
FINAL_STATUS = "section 21 validation audit completed; remaining gaps documented"


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


def test_section_21_validation_audit_indexes_runtime_api_boundaries() -> None:
    """Verify primary and legacy runtime API boundaries are explicitly indexed."""

    text = AUDIT_DOC.read_text(encoding="utf-8")

    assert "## Runtime API Boundary Matrix" in text
    for boundary, classification in [
        ("/workflows/{task_id}/governed/start", "primary"),
        ("/workflows/{task_id}/governed", "primary"),
        ("/workflows/{task_id}/governed/review-items/{item_id}/decision", "primary"),
        ("/tasks", "legacy facade"),
        ("/tasks/{task_id}", "legacy facade"),
        ("/tasks/{task_id}/review-items", "compatibility fallback"),
        ("/workflows/*", "workflow-specific compatibility"),
    ]:
        assert f"| `{boundary}` | {classification} |" in text


def test_section_21_validation_audit_indexes_task_workflow_facade_evidence() -> None:
    """Verify task and workflow facade evidence is pinned to endpoint coverage."""

    text = AUDIT_DOC.read_text(encoding="utf-8")

    assert "## Task And Workflow Endpoint Evidence Matrix" in text
    for boundary, evidence in [
        ("/tasks/{task_id}", "compact `agent_runtime` without raw `tool_results`"),
        ("/tasks", "compact list facade without raw `tool_results`"),
        (
            "/tasks/{task_id}/extract-page",
            "records runtime output while keeping the task facade compact",
        ),
        (
            "/workflows/{task_id}/governed",
            "restores compact state from persisted AgentRun data",
        ),
    ]:
        assert f"| `{boundary}` | {evidence} |" in text


def test_section_21_validation_status_is_reflected_in_primary_docs() -> None:
    """Verify primary docs record the final audit status without completion claims."""

    for path in [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "roadmap" / "00-ai-engineer-alignment-roadmap.md",
        REPO_ROOT / "docs" / "agent-runtime-refactor-rfc.zh.md",
    ]:
        text = path.read_text(encoding="utf-8")
        assert FINAL_STATUS in text
        assert "runtime refactor complete" not in text.lower()
