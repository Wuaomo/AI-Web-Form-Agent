from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_DOC = REPO_ROOT / "docs" / "section-21-validation-audit.md"
FINAL_STATUS = "section 21 validation audit completed; remaining gaps documented"
PHASE_11_STATUS = (
    "Phase 11 Agent Runtime API primary boundary audit completed; "
    "remaining migration gaps documented"
)
PHASE_12_STATUS = (
    "Phase 12 Agent Runtime API read boundary thin slice completed; "
    "remaining migration gaps documented"
)
REVIEW_QUEUE_STATUS = (
    "Review Queue primary AgentRun API boundary thin slice completed; "
    "remaining migration gaps documented"
)
REVIEW_MAPPING_CLIENT_STATUS = (
    "Review Mapping AgentRun Review Queue client helper thin slice completed; "
    "remaining migration gaps documented"
)
RUN_COCKPIT_CLIENT_STATUS = (
    "Run Cockpit AgentRun read helper thin slice completed; "
    "remaining migration gaps documented"
)
PHASE_B_BACKEND_STATUS = (
    "Phase B backend AgentRun/review boundary evidence sweep completed; "
    "remaining migration gaps documented"
)


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
        ("/agent-runs/{run_id}", "primary read boundary"),
        ("/agent-runs/{run_id}/review-items", "primary review boundary"),
        (
            "/agent-runs/{run_id}/review-items/{item_id}/decision",
            "primary review boundary",
        ),
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
        (
            "/tasks/{task_id}",
            "compact `agent_runtime` without raw `tool_results` / `output_json`",
        ),
        ("/tasks", "compact list facade without raw `tool_results` / `output_json`"),
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


def test_section_21_validation_audit_indexes_frontend_runtime_boundaries() -> None:
    """Verify frontend runtime boundary evidence is tied to UI surfaces."""

    text = AUDIT_DOC.read_text(encoding="utf-8")

    assert "## Frontend Runtime Boundary Evidence Matrix" in text
    for surface, priority in [
        ("Task Detail", "Run Cockpit AgentRun state first"),
        ("Run Cockpit", "AgentRun compact state before governed workflow and task facade fallback"),
        ("Review Mapping", "AgentRun review items before legacy task fallback"),
    ]:
        assert f"| {surface} | {priority} |" in text


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


def test_phase_11_runtime_boundary_status_is_reflected_in_primary_docs() -> None:
    """Verify primary docs record Phase 11 boundary status and remaining gaps."""

    for path in [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "roadmap" / "00-ai-engineer-alignment-roadmap.md",
        REPO_ROOT / "docs" / "agent-runtime-refactor-rfc.zh.md",
        AUDIT_DOC,
    ]:
        text = path.read_text(encoding="utf-8")
        assert PHASE_11_STATUS in text
        assert "legacy `/tasks` facade" in text
        assert "workflow-specific endpoints" in text
        assert "old security questionnaire graph fallback" in text
        assert "runtime refactor complete" not in text.lower()


def test_phase_12_agent_run_read_boundary_status_is_reflected_in_primary_docs() -> None:
    """Verify primary docs record the AgentRun read boundary without completion claims."""

    for path in [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "roadmap" / "00-ai-engineer-alignment-roadmap.md",
        REPO_ROOT / "docs" / "agent-runtime-refactor-rfc.zh.md",
        AUDIT_DOC,
    ]:
        text = path.read_text(encoding="utf-8")
        assert PHASE_12_STATUS in text
        assert "`/agent-runs/{run_id}`" in text
        assert "legacy `/tasks` facade" in text
        assert "workflow-specific endpoints" in text
        assert "old security questionnaire graph fallback" in text
        assert "runtime refactor complete" not in text.lower()


def test_review_queue_primary_agent_run_boundary_status_is_reflected() -> None:
    """Verify docs record primary Review Queue endpoints and compatibility gaps."""

    for path in [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "roadmap" / "00-ai-engineer-alignment-roadmap.md",
        REPO_ROOT / "docs" / "agent-runtime-refactor-rfc.zh.md",
        AUDIT_DOC,
    ]:
        text = path.read_text(encoding="utf-8")
        assert REVIEW_QUEUE_STATUS in text
        assert "`/agent-runs/{run_id}/review-items`" in text
        assert "`/agent-runs/{run_id}/review-items/{item_id}/decision`" in text
        assert "legacy `/tasks/{task_id}/review-items` fallback" in text
        assert "FormField sync" in text
        assert "runtime refactor complete" not in text.lower()


def test_run_cockpit_agent_run_client_status_is_reflected() -> None:
    """Verify docs record Run Cockpit AgentRun-first read helper wiring."""

    for path in [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "roadmap" / "00-ai-engineer-alignment-roadmap.md",
        REPO_ROOT / "docs" / "agent-runtime-refactor-rfc.zh.md",
        AUDIT_DOC,
    ]:
        text = path.read_text(encoding="utf-8")
        assert RUN_COCKPIT_CLIENT_STATUS in text
        assert "Run Cockpit now reads AgentRun compact state first" in text
        assert "governed workflow fallback" in text
        assert "task facade fallback" in text
        assert "runtime refactor complete" not in text.lower()


def test_review_mapping_agent_run_client_status_is_reflected() -> None:
    """Verify docs record Review Mapping AgentRun-first review client wiring."""

    for path in [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "roadmap" / "00-ai-engineer-alignment-roadmap.md",
        REPO_ROOT / "docs" / "agent-runtime-refactor-rfc.zh.md",
        AUDIT_DOC,
    ]:
        text = path.read_text(encoding="utf-8")
        assert REVIEW_MAPPING_CLIENT_STATUS in text
        assert "Review Mapping now reads AgentRun review items first" in text
        assert "legacy `/tasks/{task_id}/review-items` fallback" in text
        assert "FormField sync" in text
        assert "runtime refactor complete" not in text.lower()


def test_phase_b_backend_agent_run_review_boundary_status_is_reflected() -> None:
    """Verify docs record backend AgentRun/review boundary evidence and gaps."""

    for path in [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "roadmap" / "00-ai-engineer-alignment-roadmap.md",
        REPO_ROOT / "docs" / "agent-runtime-refactor-rfc.zh.md",
        AUDIT_DOC,
    ]:
        text = path.read_text(encoding="utf-8")
        assert PHASE_B_BACKEND_STATUS in text
        assert "`/agent-runs/{run_id}`" in text
        assert "`/agent-runs/{run_id}/review-items`" in text
        assert "`/agent-runs/{run_id}/review-items/{item_id}/decision`" in text
        assert "nested raw tool payloads" in text
        assert "FormField sync" in text
        assert "workflow-specific endpoints" in text
        assert "runtime refactor complete" not in text.lower()
