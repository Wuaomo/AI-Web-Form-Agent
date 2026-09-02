"""Tests for the task field-mapping endpoint mode selection."""

import json
from datetime import datetime, timedelta, timezone
from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app import config
from app.models import (
    ActionLog,
    AgentEvidenceItem,
    AgentProposal,
    AgentReviewDecision,
    AgentRun,
    AgentToolCall,
    AgentToolResult,
    ApprovalRequest,
    FormField,
    Profile,
    Screenshot,
    Task,
    TaskCheckpoint,
    WorkflowMemoryItem,
)
from app.routers.approvals import router as approvals_router
from app.routers.tasks import router as tasks_router
from app.services.field_mapper import map_fields_with_llm
from app.services.form_extractor import ExtractedFormField
from app.services.agent_runtime import review_queue
from app.services.agent_runtime.state_store import save_governed_runtime_state
from app.services.llm_client import LLMResult


@pytest.fixture
def test_environment() -> Generator[tuple[TestClient, Session], None, None]:
    """Provide an isolated API client and in-memory database session."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    test_app = FastAPI()
    test_app.include_router(tasks_router)
    test_app.include_router(approvals_router)
    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app) as client:
        yield client, session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def create_task_with_field(session: Session) -> tuple[Task, FormField]:
    """Create a task with one extracted field for endpoint tests."""

    profile = Profile(
        profile_name="Endpoint profile",
        full_name="Ada Lovelace",
        email="ada@example.com",
    )
    task = Task(
        url="https://example.com/form",
        profile=profile,
        status="MAPPING_READY",
    )
    field = FormField(
        task=task,
        label="Where can we reach you?",
        selector="#contact",
        field_type="email",
        required=True,
    )
    session.add(task)
    session.add(field)
    session.commit()
    return task, field


def save_two_pending_tool_created_proposals(
    session: Session,
    task: Task,
    field: FormField,
) -> list[str]:
    """Persist two governed proposals for count-focused review tests."""

    proposal_ids = [f"tool-created-{task.id}-1", f"tool-created-{task.id}-2"]
    raw_state = {
        "run_id": f"task-{task.id}",
        "task_id": task.id,
        "workflow_type": task.workflow_type,
        "planner_mode": "deterministic",
        "run": {
            "id": f"task-{task.id}",
            "goal": "Review tool-created proposals.",
            "target_url": task.url,
            "profile_id": task.profile_id,
            "status": "WAITING_REVIEW",
            "mode": "deterministic",
        },
        "tool_results": [
            {
                "tool_call_id": f"task-{task.id}:map_fields",
                "status": "SUCCEEDED",
                "created_proposals": [
                    {
                        "id": proposal_id,
                        "proposal_type": "field_value",
                        "target_type": "form_field",
                        "target_ref": str(field.id),
                        "proposed_value": f"{index}@example.com",
                        "rationale": "Review tool-created proposal.",
                        "confidence": 0.8,
                        "risk_level": "low",
                        "status": "PENDING",
                    }
                    for index, proposal_id in enumerate(proposal_ids, start=1)
                ],
            }
        ],
    }
    save_governed_runtime_state(session, task=task, raw_state=raw_state)
    return proposal_ids


def create_task_without_fields(session: Session) -> Task:
    """Create a task that has not been analyzed yet."""

    profile = Profile(
        profile_name="Analysis profile",
        full_name="Ada Lovelace",
        email="ada@example.com",
    )
    task = Task(
        url="https://example.com/form",
        profile=profile,
        status="CREATED",
    )
    session.add(task)
    session.commit()
    return task


def create_web_data_task(session: Session) -> Task:
    """Create a web data extraction task for endpoint tests."""

    profile = Profile(profile_name="Web data profile")
    task = Task(
        url="https://example.com/page",
        profile=profile,
        status="CREATED",
        workflow_status="CREATED",
        workflow_type="web_data_extract",
    )
    session.add(task)
    session.commit()
    return task


def test_create_task_response_includes_workflow_fields(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify POST /tasks returns workflow identity and saves a default plan."""

    client, session = test_environment
    profile = Profile(
        profile_name="Create task profile",
        full_name="Ada Lovelace",
        email="ada@example.com",
    )
    session.add(profile)
    session.commit()

    with patch("app.routers.tasks.safe_create_span", return_value=None), patch(
        "app.routers.tasks.safe_finish_span",
    ):
        response = client.post(
            "/tasks",
            json={
                "url": "https://example.com/form",
                "profile_id": profile.id,
                "description": "Internship application",
                "workflow_type": "form_fill",
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "CREATED"
    assert payload["workflow_type"] == "form_fill"
    assert payload["workflow_status"] == "CREATED"
    saved_task = session.get(Task, payload["id"])
    assert saved_task is not None
    assert saved_task.workflow_plan["goal"] == "Internship application"
    assert saved_task.workflow_plan["steps"][0]["step_id"] == "open_url"


def test_create_task_rejects_unsupported_workflow_type(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify POST /tasks rejects workflow types missing from the template registry."""

    client, session = test_environment
    profile = Profile(
        profile_name="Unsupported workflow profile",
        full_name="Ada Lovelace",
        email="ada@example.com",
    )
    session.add(profile)
    session.commit()

    response = client.post(
        "/tasks",
        json={
            "url": "https://example.com/form",
            "profile_id": profile.id,
            "workflow_type": "unknown_type",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Workflow template not found: unknown_type"


def test_get_task_includes_compact_agent_runtime_state(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify legacy task details expose the current AgentRun facade state."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    save_two_pending_tool_created_proposals(session, task, field)

    response = client.get(f"/tasks/{task.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_run_id"] == f"task-{task.id}"
    assert payload["agent_runtime"]["status"] == "WAITING_REVIEW"
    assert payload["agent_runtime"]["pending_review_count"] == 2
    assert payload["agent_runtime"]["tool_result_count"] == 1
    assert "tool_results" not in payload["agent_runtime"]


def test_list_tasks_includes_compact_agent_runtime_state(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify legacy task lists expose the current AgentRun facade state."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    save_two_pending_tool_created_proposals(session, task, field)

    response = client.get("/tasks")

    assert response.status_code == 200
    payload = response.json()[0]
    assert payload["id"] == task.id
    assert payload["agent_run_id"] == f"task-{task.id}"
    assert payload["agent_runtime"]["status"] == "WAITING_REVIEW"
    assert payload["agent_runtime"]["pending_review_count"] == 2
    assert payload["agent_runtime"]["tool_result_count"] == 1
    assert "tool_results" not in payload["agent_runtime"]


def test_extract_page_persists_runtime_call_without_raw_task_facade_output(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify legacy page extraction records runtime without raw UI facade output."""

    client, session = test_environment
    task = create_web_data_task(session)
    page_result = SimpleNamespace(
        title="Research page",
        headings=[SimpleNamespace(level=1, text="Overview")],
        main_text_blocks=["Long research paragraph for checkpoint output."],
        links=[SimpleNamespace(text="Docs", href="https://example.com/docs")],
        tables=[SimpleNamespace(headers=["Name"], rows=[["Ada"]])],
        forms=[SimpleNamespace(action="/signup", method="POST", field_count=2)],
    )

    with (
        patch("app.routers.tasks.extract_page", new=AsyncMock(return_value=page_result)),
        patch(
            "app.routers.tasks.open_url_and_capture_screenshot",
            new=AsyncMock(return_value=None),
        ),
    ):
        response = client.post(f"/tasks/{task.id}/extract-page")

    assert response.status_code == 200
    call = session.get(AgentToolCall, f"task-{task.id}:extract_page")
    assert call is not None
    assert call.tool_name == "extract_page"
    result = session.get(AgentToolResult, f"task-{task.id}:extract_page")
    assert result is not None
    assert result.output_json["heading_count"] == 1

    task_response = client.get(f"/tasks/{task.id}")
    payload = task_response.json()
    assert payload["agent_runtime"]["tool_result_count"] == 1
    assert "tool_results" not in payload["agent_runtime"]
    assert "main_text_blocks" not in payload["agent_runtime"]


def test_job_summary_page_extraction_persists_runtime_call(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify job-summary prerequisite page extraction records runtime."""

    client, session = test_environment
    task = create_web_data_task(session)
    page_result = SimpleNamespace(
        title="Research page",
        headings=[SimpleNamespace(level=1, text="Overview")],
        main_text_blocks=["This page describes a role with security ownership."],
        links=[],
        tables=[],
        forms=[],
    )

    with (
        patch("app.routers.tasks.extract_page", new=AsyncMock(return_value=page_result)),
        patch(
            "app.routers.tasks.open_url_and_capture_screenshot",
            new=AsyncMock(return_value=None),
        ),
    ):
        response = client.post(f"/tasks/{task.id}/job-summary")

    assert response.status_code == 200
    call = session.get(AgentToolCall, f"task-{task.id}:extract_page")
    assert call is not None
    assert call.tool_name == "extract_page"
    result = session.get(AgentToolResult, f"task-{task.id}:extract_page")
    assert result is not None
    assert result.output_json["text_block_count"] == 1


def test_review_items_returns_field_value_proposals(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify the mapping review path exposes generic proposal review items."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = "ada@example.com"
    field.confidence = 0.99
    checkpoint = TaskCheckpoint(
        task_id=task.id,
        stage="MAPPING",
        status="SUCCESS",
        input_hash="mapping",
    )
    checkpoint.output = {
        "retrieval_suggestions": [
            {
                "field_id": field.id,
                "source_type": "reviewed_memory",
                "source_id": 7,
                "mapped_profile_key": "email",
                "score": 0.84,
                "stale": False,
            }
        ]
    }
    session.add(checkpoint)
    session.commit()

    response = client.get(f"/tasks/{task.id}/review-items")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["proposal_type"] == "field_value"
    assert payload[0]["target_type"] == "form_field"
    assert payload[0]["target_ref"] == str(field.id)
    assert payload[0]["proposed_value"] == "ada@example.com"
    assert payload[0]["confidence"] == 0.99
    assert payload[0]["evidence"][0]["source_type"] == "memory"
    assert payload[0]["evidence"][0]["source_id"] == "7"


def test_review_items_returns_answer_proposals_with_source_evidence(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify questionnaire answers use the generic proposal review contract."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    task.workflow_type = "security_questionnaire"
    field.label = "Do you require MFA?"
    field.mapped_value = "Yes. MFA is required for admin access."
    field.confidence = 0.88
    checkpoint = TaskCheckpoint(
        task_id=task.id,
        stage="MAPPING",
        status="SUCCESS",
        input_hash="mapping",
    )
    checkpoint.output = {
        "source_suggestions": [
            {
                "field_id": field.id,
                "source": "mock-security-policy.md",
                "matched_section": "Access Control",
                "status": "needs_review",
                "source_evidence": [
                    {
                        "source_type": "policy_doc",
                        "content": "MFA is required for administrative access.",
                    }
                ],
            }
        ]
    }
    session.add(checkpoint)
    session.commit()

    response = client.get(f"/tasks/{task.id}/review-items")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["proposal_type"] == "answer"
    assert payload[0]["rationale"] == "Review the proposed answer before browser execution."
    assert payload[0]["evidence"][0]["source_type"] == "policy_doc"
    assert payload[0]["evidence"][0]["source_title"] == "mock-security-policy.md"
    assert payload[0]["evidence"][0]["section_title"] == "Access Control"


def test_review_items_persist_proposals_and_evidence(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify Review Mapping proposals are double-written to runtime tables."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = "ada@example.com"
    field.confidence = 0.99
    checkpoint = TaskCheckpoint(
        task_id=task.id,
        stage="MAPPING",
        status="SUCCESS",
        input_hash="mapping",
    )
    checkpoint.output = {
        "retrieval_suggestions": [
            {
                "field_id": field.id,
                "source_id": 7,
                "mapped_profile_key": "email",
                "score": 0.84,
                "stale": False,
            }
        ]
    }
    session.add(checkpoint)
    session.commit()

    response = client.get(f"/tasks/{task.id}/review-items")

    assert response.status_code == 200
    proposal = session.execute(
        text(
            """
            SELECT id, run_id, proposal_type, target_type, target_ref,
                   proposed_value, confidence, risk_level, status
            FROM agent_proposals
            WHERE id = :proposal_id
            """
        ),
        {"proposal_id": f"task-{task.id}-field-{field.id}"},
    ).mappings().one()
    assert proposal["run_id"] == f"task-{task.id}"
    assert proposal["proposal_type"] == "field_value"
    assert proposal["target_type"] == "form_field"
    assert proposal["target_ref"] == str(field.id)
    assert json.loads(proposal["proposed_value"]) == "ada@example.com"
    assert proposal["confidence"] == 0.99
    assert proposal["risk_level"] == "low"
    assert proposal["status"] == "PENDING"

    evidence = session.execute(
        text(
            """
            SELECT id, run_id, proposal_id, source_type, source_id,
                   source_title, section_title, quote_or_summary, score
            FROM agent_evidence_items
            WHERE proposal_id = :proposal_id
            """
        ),
        {"proposal_id": f"task-{task.id}-field-{field.id}"},
    ).mappings().one()
    assert evidence["run_id"] == f"task-{task.id}"
    assert evidence["source_type"] == "memory"
    assert evidence["source_id"] == "7"
    assert evidence["source_title"] == "Reviewed memory"
    assert evidence["section_title"] == "email"
    assert evidence["quote_or_summary"] == "Reviewed memory suggests profile.email (reviewed)."
    assert evidence["score"] == 0.84


def test_review_items_restore_persisted_proposals_before_deriving_from_fields(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify persisted proposals are the Review Mapping source of truth."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = "form-field@example.com"
    field.confidence = 0.99
    run = AgentRun(
        id=f"task-{task.id}",
        legacy_task_id=task.id,
        goal="Review persisted items.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=f"task-{task.id}-field-{field.id}",
        run=run,
        proposal_type="answer",
        target_type="form_field",
        target_ref=str(field.id),
        proposed_value="persisted answer",
        rationale="Persisted proposal should win.",
        confidence=0.42,
        risk_level="medium",
        status="PENDING",
    )
    evidence = AgentEvidenceItem(
        id=f"persisted-evidence-{task.id}",
        run_id=run.id,
        proposal=proposal,
        source_type="policy_doc",
        source_id="policy-1",
        source_title="Persisted policy",
        section_title="Access",
        quote_or_summary="Persisted evidence should win.",
        score=0.77,
    )
    session.add_all([run, proposal, evidence])
    session.commit()

    response = client.get(f"/tasks/{task.id}/review-items")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["proposal_type"] == "answer"
    assert payload[0]["proposed_value"] == "persisted answer"
    assert payload[0]["rationale"] == "Persisted proposal should win."
    assert payload[0]["confidence"] == 0.42
    assert payload[0]["risk_level"] == "medium"
    evidence_payload = payload[0]["evidence"][0]
    assert evidence_payload["id"] == f"persisted-evidence-{task.id}"
    assert evidence_payload["run_id"] == run.id
    assert evidence_payload["proposal_id"] == proposal.id
    assert evidence_payload["source_type"] == "policy_doc"
    assert evidence_payload["source_id"] == "policy-1"
    assert evidence_payload["source_title"] == "Persisted policy"
    assert evidence_payload["section_title"] == "Access"
    assert evidence_payload["quote_or_summary"] == "Persisted evidence should win."
    assert evidence_payload["score"] == 0.77
    assert payload[1]["proposal_type"] == "memory_write"


def test_review_items_backfill_missing_persisted_field_proposals(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify persisted proposals stay authoritative without hiding new fields."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = "form-field@example.com"
    field.confidence = 0.99
    second_field = FormField(
        task_id=task.id,
        label="Phone",
        selector="#phone",
        field_type="tel",
        mapped_profile_key="phone",
        mapped_value="123-456",
        confidence=0.91,
    )
    run = AgentRun(
        id=f"task-{task.id}",
        legacy_task_id=task.id,
        goal="Review persisted items.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=f"task-{task.id}-field-{field.id}",
        run=run,
        proposal_type="answer",
        target_type="form_field",
        target_ref=str(field.id),
        proposed_value="persisted answer",
        rationale="Persisted proposal should win.",
        confidence=0.42,
        risk_level="medium",
        status="PENDING",
    )
    session.add_all([run, proposal, second_field])
    session.commit()

    response = client.get(f"/tasks/{task.id}/review-items")

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload] == [
        proposal.id,
        f"task-{task.id}-field-{second_field.id}",
        f"task-{task.id}-field-{field.id}-memory-mapping",
        f"task-{task.id}-field-{second_field.id}-memory-mapping",
    ]
    assert payload[0]["proposed_value"] == "persisted answer"
    assert payload[1]["proposed_value"] == "123-456"
    assert session.get(
        AgentProposal,
        f"task-{task.id}-field-{second_field.id}",
    ) is not None


def test_review_items_restore_tool_created_governed_proposals(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify governed ToolResult proposals become persisted review items."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_value = "derived@example.com"
    proposal_id = f"tool-created-{task.id}"
    evidence_id = f"{proposal_id}-evidence"
    raw_state = {
        "run_id": f"task-{task.id}",
        "task_id": task.id,
        "workflow_type": task.workflow_type,
        "planner_mode": "deterministic",
        "run": {
            "id": f"task-{task.id}",
            "goal": "Review tool-created proposal.",
            "target_url": task.url,
            "profile_id": task.profile_id,
            "status": "WAITING_REVIEW",
            "mode": "deterministic",
        },
        "tool_results": [
            {
                "tool_call_id": f"task-{task.id}:map_fields",
                "status": "SUCCEEDED",
                "created_proposals": [
                    {
                        "id": proposal_id,
                        "run_id": f"task-{task.id}",
                        "proposal_type": "field_value",
                        "target_type": "form_field",
                        "target_ref": str(field.id),
                        "proposed_value": "tool@example.com",
                        "rationale": "Tool-created proposal should persist.",
                        "confidence": 0.91,
                        "risk_level": "low",
                        "status": "PENDING",
                        "evidence": [
                            {
                                "id": evidence_id,
                                "run_id": f"task-{task.id}",
                                "proposal_id": proposal_id,
                                "source_type": "tool_result",
                                "source_title": "map_fields",
                                "section_title": "Contact",
                                "quote_or_summary": "Mapped from tool output.",
                                "score": 0.82,
                            }
                        ],
                    }
                ],
            }
        ],
    }

    save_governed_runtime_state(session, task=task, raw_state=raw_state)
    save_governed_runtime_state(session, task=task, raw_state=raw_state)

    assert session.query(AgentProposal).count() == 1
    assert session.query(AgentEvidenceItem).count() == 1
    assert session.query(WorkflowMemoryItem).count() == 0

    response = client.get(f"/tasks/{task.id}/review-items")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == proposal_id
    assert payload[0]["proposed_value"] == "tool@example.com"
    assert payload[0]["evidence"][0]["id"] == evidence_id
    assert payload[0]["evidence"][0]["quote_or_summary"] == "Mapped from tool output."


def test_review_items_restore_tool_result_evidence_for_created_proposals(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify ToolResult evidence can back a created proposal without nesting."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    proposal_id = f"tool-created-{task.id}"
    evidence_id = f"{proposal_id}-top-level-evidence"
    raw_state = {
        "run_id": f"task-{task.id}",
        "task_id": task.id,
        "workflow_type": task.workflow_type,
        "planner_mode": "deterministic",
        "run": {
            "id": f"task-{task.id}",
            "goal": "Review tool-created proposal.",
            "target_url": task.url,
            "profile_id": task.profile_id,
            "status": "WAITING_REVIEW",
            "mode": "deterministic",
        },
        "tool_results": [
            {
                "tool_call_id": f"task-{task.id}:map_fields",
                "status": "SUCCEEDED",
                "created_proposals": [
                    {
                        "id": proposal_id,
                        "proposal_type": "field_value",
                        "target_type": "form_field",
                        "target_ref": str(field.id),
                        "proposed_value": "tool@example.com",
                        "rationale": "Tool-created proposal should persist.",
                        "confidence": 0.91,
                        "risk_level": "low",
                        "status": "PENDING",
                    }
                ],
                "evidence_items": [
                    {
                        "id": evidence_id,
                        "proposal_id": proposal_id,
                        "source_type": "tool_result",
                        "source_title": "map_fields",
                        "quote_or_summary": "Top-level evidence should persist.",
                        "score": 0.82,
                    }
                ],
            }
        ],
    }

    save_governed_runtime_state(session, task=task, raw_state=raw_state)

    response = client.get(f"/tasks/{task.id}/review-items")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["id"] == proposal_id
    assert payload[0]["evidence"][0]["id"] == evidence_id
    assert payload[0]["evidence"][0]["quote_or_summary"] == "Top-level evidence should persist."


def test_review_items_replace_stale_persisted_proposal_evidence(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify refreshed tool proposals do not keep stale evidence rows."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    proposal_id = f"tool-created-{task.id}"

    def raw_state(evidence_id: str, summary: str) -> dict[str, object]:
        return {
            "run_id": f"task-{task.id}",
            "task_id": task.id,
            "workflow_type": task.workflow_type,
            "planner_mode": "deterministic",
            "run": {
                "id": f"task-{task.id}",
                "goal": "Review refreshed proposal.",
                "target_url": task.url,
                "profile_id": task.profile_id,
                "status": "WAITING_REVIEW",
                "mode": "deterministic",
            },
            "tool_results": [
                {
                    "tool_call_id": f"task-{task.id}:map_fields",
                    "status": "SUCCEEDED",
                    "created_proposals": [
                        {
                            "id": proposal_id,
                            "proposal_type": "field_value",
                            "target_type": "form_field",
                            "target_ref": str(field.id),
                            "proposed_value": "tool@example.com",
                            "rationale": "Tool-created proposal should persist.",
                            "confidence": 0.91,
                            "risk_level": "low",
                            "status": "PENDING",
                            "evidence": [
                                {
                                    "id": evidence_id,
                                    "source_type": "tool_result",
                                    "source_title": "map_fields",
                                    "quote_or_summary": summary,
                                    "score": 0.82,
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    save_governed_runtime_state(
        session,
        task=task,
        raw_state=raw_state("old-evidence", "Old evidence."),
    )
    save_governed_runtime_state(
        session,
        task=task,
        raw_state=raw_state("new-evidence", "New evidence."),
    )

    response = client.get(f"/tasks/{task.id}/review-items")

    assert response.status_code == 200
    evidence = response.json()[0]["evidence"]
    assert [item["id"] for item in evidence] == ["new-evidence"]
    assert evidence[0]["quote_or_summary"] == "New evidence."


def test_review_items_restore_tool_created_governed_proposal_after_decision(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify task review decisions preserve tool-created proposal evidence."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_value = "derived@example.com"
    proposal_id = f"tool-created-{task.id}"
    evidence_id = f"{proposal_id}-evidence"
    raw_state = {
        "run_id": f"task-{task.id}",
        "task_id": task.id,
        "workflow_type": task.workflow_type,
        "planner_mode": "deterministic",
        "run": {
            "id": f"task-{task.id}",
            "goal": "Review tool-created proposal.",
            "target_url": task.url,
            "profile_id": task.profile_id,
            "status": "WAITING_REVIEW",
            "mode": "deterministic",
        },
        "tool_results": [
            {
                "tool_call_id": f"task-{task.id}:map_fields",
                "status": "SUCCEEDED",
                "created_proposals": [
                    {
                        "id": proposal_id,
                        "run_id": f"task-{task.id}",
                        "proposal_type": "field_value",
                        "target_type": "form_field",
                        "target_ref": str(field.id),
                        "proposed_value": "tool@example.com",
                        "rationale": "Tool-created proposal should persist.",
                        "confidence": 0.91,
                        "risk_level": "low",
                        "status": "PENDING",
                        "evidence": [
                            {
                                "id": evidence_id,
                                "run_id": f"task-{task.id}",
                                "proposal_id": proposal_id,
                                "source_type": "tool_result",
                                "source_title": "map_fields",
                                "section_title": "Contact",
                                "quote_or_summary": "Mapped from tool output.",
                                "score": 0.82,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    save_governed_runtime_state(session, task=task, raw_state=raw_state)

    response = client.post(
        f"/tasks/{task.id}/review-items/{proposal_id}/decision",
        json={"decision": "edited", "edited_value": "edited@example.com"},
    )
    assert response.status_code == 200

    response = client.get(f"/tasks/{task.id}/review-items")

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload] == [proposal_id]
    assert payload[0]["status"] == "EDITED"
    assert payload[0]["proposed_value"] == "edited@example.com"
    assert payload[0]["evidence"][0]["id"] == evidence_id
    assert payload[0]["evidence"][0]["quote_or_summary"] == "Mapped from tool output."


def test_review_items_keep_edited_value_after_tool_proposal_replay(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify replayed pending proposals do not overwrite reviewed values."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    proposal_id = f"tool-created-{task.id}"
    raw_state = {
        "run_id": f"task-{task.id}",
        "task_id": task.id,
        "workflow_type": task.workflow_type,
        "planner_mode": "deterministic",
        "run": {
            "id": f"task-{task.id}",
            "goal": "Review replayed proposal.",
            "target_url": task.url,
            "profile_id": task.profile_id,
            "status": "WAITING_REVIEW",
            "mode": "deterministic",
        },
        "tool_results": [
            {
                "tool_call_id": f"task-{task.id}:map_fields",
                "status": "SUCCEEDED",
                "created_proposals": [
                    {
                        "id": proposal_id,
                        "proposal_type": "field_value",
                        "target_type": "form_field",
                        "target_ref": str(field.id),
                        "proposed_value": "tool@example.com",
                        "rationale": "Tool-created proposal should persist.",
                        "confidence": 0.91,
                        "risk_level": "low",
                        "status": "PENDING",
                    }
                ],
            }
        ],
    }
    save_governed_runtime_state(session, task=task, raw_state=raw_state)

    response = client.post(
        f"/tasks/{task.id}/review-items/{proposal_id}/decision",
        json={"decision": "edited", "edited_value": "edited@example.com"},
    )
    assert response.status_code == 200

    save_governed_runtime_state(session, task=task, raw_state=raw_state)
    proposal = session.get(AgentProposal, proposal_id)
    assert proposal is not None
    assert proposal.proposed_value == "edited@example.com"
    response = client.get(f"/tasks/{task.id}/review-items")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["status"] == "EDITED"
    assert payload[0]["proposed_value"] == "edited@example.com"


@pytest.mark.parametrize("decision", ["approved", "edited", "rejected"])
def test_review_item_decision_decrements_pending_review_count_for_final_decisions(
    test_environment: tuple[TestClient, Session],
    decision: str,
) -> None:
    """Verify task review decisions remove approved/edited/rejected items from pending count."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    proposal_ids = save_two_pending_tool_created_proposals(session, task, field)

    response = client.post(
        f"/tasks/{task.id}/review-items/{proposal_ids[0]}/decision",
        json={
            "decision": decision,
            "edited_value": "edited@example.com" if decision == "edited" else None,
        },
    )

    assert response.status_code == 200
    run = session.get(AgentRun, f"task-{task.id}")
    assert run is not None
    assert run.pending_review_count == 1


def test_review_item_decision_needs_more_evidence_decrements_pending_review_count(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify needs_more_evidence is not counted as pending after task review."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    proposal_ids = save_two_pending_tool_created_proposals(session, task, field)

    response = client.post(
        f"/tasks/{task.id}/review-items/{proposal_ids[0]}/decision",
        json={"decision": "needs_more_evidence"},
    )

    assert response.status_code == 200
    run = session.get(AgentRun, f"task-{task.id}")
    assert run is not None
    assert run.pending_review_count == 1


@pytest.mark.parametrize(
    ("decision", "expected_status"),
    [
        ("edited", "EDITED"),
        ("rejected", "REJECTED"),
        ("needs_more_evidence", "NEEDS_MORE_EVIDENCE"),
    ],
)
def test_review_items_restore_latest_persisted_decision_status(
    test_environment: tuple[TestClient, Session],
    decision: str,
    expected_status: str,
) -> None:
    """Verify persisted review decisions drive returned proposal status."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    run = AgentRun(
        id=f"task-{task.id}",
        legacy_task_id=task.id,
        goal="Review persisted decisions.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=f"task-{task.id}-field-{field.id}",
        run=run,
        proposal_type="field_value",
        target_type="form_field",
        target_ref=str(field.id),
        proposed_value="pending@example.com",
        rationale="Review persisted decision.",
        confidence=0.9,
        risk_level="low",
        status="PENDING",
    )
    older = AgentReviewDecision(
        id=f"old-decision-{task.id}",
        proposal=proposal,
        decision="approved",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    latest = AgentReviewDecision(
        id=f"latest-decision-{task.id}",
        proposal=proposal,
        decision=decision,
        created_at=datetime.now(timezone.utc),
    )
    if decision == "edited":
        latest.edited_value = "edited@example.com"
    session.add_all([run, proposal, older, latest])
    session.commit()

    response = client.get(f"/tasks/{task.id}/review-items")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["status"] == expected_status
    if decision == "edited":
        assert payload[0]["proposed_value"] == "edited@example.com"


def test_review_items_restore_memory_write_decision_value(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify persisted memory-write decisions restore through GET review-items."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    run = AgentRun(
        id=f"task-{task.id}",
        legacy_task_id=task.id,
        goal="Review memory decisions.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=f"task-{task.id}-field-{field.id}-memory-mapping",
        run=run,
        proposal_type="memory_write",
        target_type="workflow_memory",
        target_ref=str(field.id),
        proposed_value="email",
        rationale="Review persisted memory decision.",
        confidence=0.9,
        risk_level="medium",
        status="PENDING",
    )
    decision = AgentReviewDecision(
        id=f"memory-decision-{task.id}",
        proposal=proposal,
        decision="edited",
        created_at=datetime.now(timezone.utc),
    )
    decision.edited_value = "support_email"
    session.add_all([run, proposal, decision])
    session.commit()

    response = client.get(f"/tasks/{task.id}/review-items")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["proposal_type"] == "memory_write"
    assert payload[0]["status"] == "EDITED"
    assert payload[0]["proposed_value"] == "support_email"


def test_review_items_include_memory_write_proposals_for_reusable_mappings(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify reviewed reusable mappings are visible as memory-write proposals."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = "ada@example.com"
    field.confidence = 0.99
    session.commit()

    response = client.get(f"/tasks/{task.id}/review-items")

    assert response.status_code == 200
    payload = response.json()
    memory_write = next(
        item for item in payload if item["proposal_type"] == "memory_write"
    )
    assert memory_write["target_type"] == "workflow_memory"
    assert memory_write["target_ref"] == str(field.id)
    assert memory_write["proposed_value"] == "email"
    assert memory_write["rationale"] == "Save this reviewed mapping for future retrieval."
    assert memory_write["risk_level"] == "medium"


def test_review_items_include_memory_write_proposals_for_questionnaire_answers(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify reviewed questionnaire answers can use the same memory proposal type."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    task.workflow_type = "security_questionnaire"
    field.label = "Do you require MFA?"
    field.mapped_value = "Yes. MFA is required for admin access."
    field.confidence = 0.88
    session.commit()

    response = client.get(f"/tasks/{task.id}/review-items")

    assert response.status_code == 200
    payload = response.json()
    memory_write = next(
        item for item in payload if item["proposal_type"] == "memory_write"
    )
    assert memory_write["target_type"] == "workflow_memory"
    assert memory_write["target_ref"] == str(field.id)
    assert memory_write["proposed_value"] == "reviewed_answer"
    assert memory_write["rationale"] == "Save this reviewed answer for future retrieval."


def test_review_item_decision_edits_existing_field_mapping(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify generic proposal decisions can update Review Mapping fields."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_value = "old@example.com"
    field.confidence = 0.5
    session.commit()

    response = client.post(
        f"/tasks/{task.id}/review-items/task-{task.id}-field-{field.id}/decision",
        json={"decision": "edited", "edited_value": "ada@example.com"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["proposal_id"] == f"task-{task.id}-field-{field.id}"
    assert payload["decision"] == "edited"
    assert payload["edited_value"] == "ada@example.com"
    session.refresh(field)
    assert field.mapped_value == "ada@example.com"
    assert field.confidence == 1.0


def test_review_item_decision_uses_persisted_form_field_target_ref(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify custom persisted proposal ids can still update their target field."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_value = "old@example.com"
    field.confidence = 0.5
    run = AgentRun(
        id=f"persisted-run-{task.id}",
        legacy_task_id=task.id,
        goal="Review persisted proposal ids.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=f"runtime-proposal-{task.id}",
        run=run,
        proposal_type="field_value",
        target_type="form_field",
        target_ref=str(field.id),
        proposed_value="persisted@example.com",
        rationale="Review the persisted proposal.",
        confidence=0.8,
        risk_level="low",
        status="PENDING",
    )
    session.add_all([run, proposal])
    session.commit()

    response = client.post(
        f"/tasks/{task.id}/review-items/{proposal.id}/decision",
        json={"decision": "edited", "edited_value": "ada@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["proposal_id"] == proposal.id
    session.refresh(field)
    assert field.mapped_value == "ada@example.com"
    assert field.confidence == 1.0


def test_review_item_decision_approve_syncs_persisted_proposal_value(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify approve uses the persisted proposal value as the field value."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_value = "stale-field@example.com"
    field.confidence = 0.5
    run = AgentRun(
        id=f"persisted-approve-run-{task.id}",
        legacy_task_id=task.id,
        goal="Approve persisted proposal value.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=f"persisted-approve-{task.id}",
        run=run,
        proposal_type="field_value",
        target_type="form_field",
        target_ref=str(field.id),
        proposed_value="persisted@example.com",
        rationale="Review persisted value.",
        confidence=0.8,
        risk_level="low",
        status="PENDING",
    )
    session.add_all([run, proposal])
    session.commit()

    response = client.post(
        f"/tasks/{task.id}/review-items/{proposal.id}/decision",
        json={"decision": "approved"},
    )

    assert response.status_code == 200
    session.refresh(field)
    assert field.mapped_value == "persisted@example.com"
    assert field.confidence == 1.0


def test_review_queue_resolves_persisted_form_field_target(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify persisted form-field proposals resolve through the review queue helper."""

    _, session = test_environment
    task, field = create_task_with_field(session)
    run = AgentRun(
        id=f"helper-run-{task.id}",
        legacy_task_id=task.id,
        goal="Resolve persisted field proposal.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=f"helper-proposal-{task.id}",
        run=run,
        proposal_type="field_value",
        target_type="form_field",
        target_ref=str(field.id),
        proposed_value="ada@example.com",
        rationale="Review helper target.",
        confidence=0.8,
        risk_level="low",
        status="PENDING",
    )
    session.add_all([run, proposal])
    session.commit()

    target = review_queue.resolve_task_review_item_target(
        session,
        task=task,
        proposal_id=proposal.id,
    )

    assert target.proposal == proposal
    assert target.field == field
    assert target.requires_form_field_sync is True


def test_review_queue_resolves_non_field_target_without_form_field_sync(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify persisted non-field proposals do not require FormField sync."""

    _, session = test_environment
    task, field = create_task_with_field(session)
    run = AgentRun(
        id=f"helper-memory-run-{task.id}",
        legacy_task_id=task.id,
        goal="Resolve persisted memory proposal.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=f"helper-memory-{task.id}",
        run=run,
        proposal_type="memory_write",
        target_type="workflow_memory",
        target_ref=str(field.id),
        proposed_value="email",
        rationale="Review memory target.",
        confidence=0.8,
        risk_level="medium",
        status="PENDING",
    )
    session.add_all([run, proposal])
    session.commit()

    target = review_queue.resolve_task_review_item_target(
        session,
        task=task,
        proposal_id=proposal.id,
    )

    assert target.proposal == proposal
    assert target.field is None
    assert target.requires_form_field_sync is False


def test_review_queue_keeps_legacy_field_id_fallback(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify legacy task-field proposal ids still resolve during migration."""

    _, session = test_environment
    task, field = create_task_with_field(session)

    target = review_queue.resolve_task_review_item_target(
        session,
        task=task,
        proposal_id=f"task-{task.id}-field-{field.id}",
    )

    assert target.proposal is None
    assert target.field == field
    assert target.requires_form_field_sync is True


def test_review_item_decision_keeps_legacy_field_id_fallback(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify legacy task-field proposal ids keep working during migration."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_value = "old@example.com"
    field.confidence = 0.5
    session.commit()

    response = client.post(
        f"/tasks/{task.id}/review-items/task-{task.id}-field-{field.id}/decision",
        json={"decision": "approved"},
    )

    assert response.status_code == 200
    assert response.json()["proposal_id"] == f"task-{task.id}-field-{field.id}"
    session.refresh(field)
    assert field.mapped_value == "old@example.com"
    assert field.confidence == 1.0


def test_review_item_decision_persists_review_decision(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify proposal decisions are double-written without replacing FormField sync."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_value = "old@example.com"
    field.confidence = 0.5
    session.commit()

    response = client.post(
        f"/tasks/{task.id}/review-items/task-{task.id}-field-{field.id}/decision",
        json={
            "decision": "edited",
            "edited_value": "ada@example.com",
            "reviewer_note": "Use current contact address.",
        },
    )

    assert response.status_code == 200
    decision = session.execute(
        text(
            """
            SELECT id, proposal_id, decision, edited_value, reviewer_note
            FROM agent_review_decisions
            WHERE proposal_id = :proposal_id
            """
        ),
        {"proposal_id": f"task-{task.id}-field-{field.id}"},
    ).mappings().one()
    assert decision["id"] == f"decision-task-{task.id}-field-{field.id}"
    assert decision["decision"] == "edited"
    assert json.loads(decision["edited_value"]) == "ada@example.com"
    assert decision["reviewer_note"] == "Use current contact address."

    proposal = session.execute(
        text(
            """
            SELECT status, proposed_value
            FROM agent_proposals
            WHERE id = :proposal_id
            """
        ),
        {"proposal_id": f"task-{task.id}-field-{field.id}"},
    ).mappings().one()
    assert proposal["status"] == "EDITED"
    assert json.loads(proposal["proposed_value"]) == "ada@example.com"

    session.refresh(field)
    assert field.mapped_value == "ada@example.com"
    assert field.confidence == 1.0


def test_review_item_decision_persists_non_field_decision_without_side_effects(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify non-field proposal decisions persist without changing form or memory."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_value = "old@example.com"
    field.confidence = 0.5
    run = AgentRun(
        id=f"memory-run-{task.id}",
        legacy_task_id=task.id,
        goal="Review memory proposal.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=f"memory-write-{task.id}",
        run=run,
        proposal_type="memory_write",
        target_type="workflow_memory",
        target_ref=str(field.id),
        proposed_value="email",
        rationale="Review memory write.",
        confidence=0.8,
        risk_level="medium",
        status="PENDING",
    )
    session.add_all([run, proposal])
    session.commit()

    response = client.post(
        f"/tasks/{task.id}/review-items/{proposal.id}/decision",
        json={"decision": "approved"},
    )

    assert response.status_code == 200
    decision = session.get(AgentReviewDecision, f"decision-{proposal.id}")
    assert decision is not None
    assert decision.decision == "approved"
    session.refresh(proposal)
    assert proposal.status == "APPROVED"
    session.refresh(field)
    assert field.mapped_value == "old@example.com"
    assert field.confidence == 0.5
    assert session.query(WorkflowMemoryItem).count() == 0


def test_review_item_decision_edits_non_field_proposed_value_only(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify edited non-field decisions only update the proposal value."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_value = "old@example.com"
    field.confidence = 0.5
    run = AgentRun(
        id=f"edited-memory-run-{task.id}",
        legacy_task_id=task.id,
        goal="Review edited memory proposal.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=f"edited-memory-write-{task.id}",
        run=run,
        proposal_type="memory_write",
        target_type="workflow_memory",
        target_ref=str(field.id),
        proposed_value="email",
        rationale="Review edited memory write.",
        confidence=0.8,
        risk_level="medium",
        status="PENDING",
    )
    session.add_all([run, proposal])
    session.commit()

    response = client.post(
        f"/tasks/{task.id}/review-items/{proposal.id}/decision",
        json={"decision": "edited", "edited_value": "support_email"},
    )

    assert response.status_code == 200
    session.refresh(proposal)
    assert proposal.status == "EDITED"
    assert proposal.proposed_value == "support_email"
    session.refresh(field)
    assert field.mapped_value == "old@example.com"
    assert field.confidence == 0.5
    assert session.query(WorkflowMemoryItem).count() == 0


def test_review_item_decision_rejects_existing_field_mapping(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify rejected proposal decisions clear the mapped field value."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = "ada@example.com"
    field.confidence = 0.99
    session.commit()

    response = client.post(
        f"/tasks/{task.id}/review-items/task-{task.id}-field-{field.id}/decision",
        json={"decision": "rejected"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "rejected"
    session.refresh(field)
    assert field.mapped_profile_key is None
    assert field.mapped_value is None
    assert field.confidence is None


def test_map_fields_requires_llm_provider_when_no_default_is_configured(
    test_environment: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = test_environment
    task, _ = create_task_with_field(session)
    monkeypatch.setattr(config, "LLM_PROVIDER", "")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "test-deepseek-key")

    with patch("app.routers.tasks.map_fields_with_llm_result") as llm:
        response = client.post(f"/tasks/{task.id}/map-fields")

    assert response.status_code == 400
    assert "Choose an LLM provider" in response.json()["detail"]
    llm.assert_not_called()


def test_map_fields_uses_selected_deepseek_provider(
    test_environment: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "test-deepseek-key")

    with patch(
        "app.routers.tasks.map_fields_with_llm_result",
        return_value=SimpleNamespace(fields=[field], retrieval_suggestions=[]),
    ) as llm:
        response = client.post(f"/tasks/{task.id}/map-fields?provider=deepseek")

    assert response.status_code == 200
    llm.assert_called_once_with(task.id, session, provider="deepseek")


def test_map_fields_passes_selected_llm_provider(
    test_environment: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-gemini-key")

    with patch(
        "app.routers.tasks.map_fields_with_llm_result",
        return_value=SimpleNamespace(fields=[field], retrieval_suggestions=[]),
    ) as llm:
        response = client.post(f"/tasks/{task.id}/map-fields?provider=gemini")

    assert response.status_code == 200
    llm.assert_called_once_with(task.id, session, provider="gemini")


def test_map_fields_writes_retrieval_suggestions_to_checkpoint(
    test_environment: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "test-deepseek-key")
    suggestion = {
        "field_id": field.id,
        "source_type": "reviewed_memory",
        "source_id": 7,
        "mapped_profile_key": "email",
        "stale": True,
        "governance_status": "stale_review_recommended",
    }

    with patch(
        "app.routers.tasks.map_fields_with_llm_result",
        return_value=SimpleNamespace(fields=[field], retrieval_suggestions=[suggestion]),
    ):
        response = client.post(f"/tasks/{task.id}/map-fields?provider=deepseek")

    assert response.status_code == 200
    checkpoint = session.scalar(
        select(TaskCheckpoint).where(TaskCheckpoint.task_id == task.id)
    )
    assert checkpoint is not None
    assert checkpoint.output["retrieval_suggestions"] == [suggestion]


def test_map_fields_reports_missing_provider_api_key(
    test_environment: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = test_environment
    task, _ = create_task_with_field(session)
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", None)

    with patch("app.routers.tasks.map_fields_with_llm_result") as llm:
        response = client.post(f"/tasks/{task.id}/map-fields?provider=deepseek")

    assert response.status_code == 409
    assert "DEEPSEEK_API_KEY" in response.json()["detail"]
    llm.assert_not_called()


def test_map_fields_supports_developer_rule_mode(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)

    with (
        patch("app.routers.tasks.map_fields_with_llm_result") as llm,
        patch("app.routers.tasks.map_fields_by_rules", return_value=[field]) as rules,
    ):
        response = client.post(f"/tasks/{task.id}/map-fields?mode=rules")

    assert response.status_code == 200
    rules.assert_called_once()
    llm.assert_not_called()


def test_rules_mapping_persists_map_fields_runtime_call(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify legacy rules mapping records the internal read/write as runtime."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = "ada@example.com"
    field.confidence = 1.0
    session.commit()

    with patch("app.routers.tasks.map_fields_by_rules", return_value=[field]):
        response = client.post(f"/tasks/{task.id}/map-fields?mode=rules")

    assert response.status_code == 200
    call = session.get(AgentToolCall, f"task-{task.id}:map_fields")
    assert call is not None
    assert call.tool_name == "map_fields"
    assert call.status == "SUCCEEDED"
    result = session.get(AgentToolResult, f"task-{task.id}:map_fields")
    assert result is not None
    assert result.output_json["field_count"] == 1
    assert result.output_json["mapped_count"] == 1


def test_confirm_mapping_rejects_missing_required_values(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = None
    session.commit()

    response = client.post(f"/tasks/{task.id}/confirm-mapping")

    assert response.status_code == 409
    assert "Required fields need values" in response.json()["detail"]
    assert "Where can we reach you?" in response.json()["detail"]


def test_confirm_mapping_allows_required_values_after_manual_entry(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_value = "manual@example.com"
    session.commit()

    response = client.post(f"/tasks/{task.id}/confirm-mapping")

    assert response.status_code == 200
    assert response.json()["status"] == "READY_TO_FILL"
    assert isinstance(response.json().get("profile_updates"), list)
    assert response.json()["profile_updates"]

    session.refresh(task)
    assert task.status == "READY_TO_FILL"


def test_confirm_mapping_succeeds_when_workflow_memory_save_fails(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_value = "manual@example.com"
    session.commit()

    with patch(
        "app.routers.tasks.save_confirmed_mappings_for_task",
        side_effect=RuntimeError("memory write failed"),
    ):
        response = client.post(f"/tasks/{task.id}/confirm-mapping")

    assert response.status_code == 200
    assert response.json()["status"] == "READY_TO_FILL"
    session.refresh(task)
    assert task.status == "READY_TO_FILL"


def test_confirm_mapping_writes_back_to_built_in_profile_key(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = "manual@example.com"
    session.commit()

    response = client.post(f"/tasks/{task.id}/confirm-mapping")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "READY_TO_FILL"
    assert payload["profile_updates"] == [
        {
            "field_id": field.id,
            "profile_key": "email",
            "previous_value": "ada@example.com",
            "new_value": "manual@example.com",
            "action": "updated",
        }
    ]

    session.refresh(task.profile)
    assert task.profile.email == "manual@example.com"


def test_confirm_mapping_does_not_report_update_when_value_is_unchanged(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = "ada@example.com"
    session.commit()

    response = client.post(f"/tasks/{task.id}/confirm-mapping")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "READY_TO_FILL"
    assert payload["profile_updates"] == []


def test_confirm_mapping_skips_one_time_fields(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.label = "Agree to terms"
    field.field_type = "checkbox"
    field.required = False
    field.mapped_value = "true"
    session.commit()

    response = client.post(f"/tasks/{task.id}/confirm-mapping")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "READY_TO_FILL"
    assert payload["profile_updates"] == []
    assert payload["profile_skipped"] == [
        {"field_id": field.id, "reason": "one_time_field", "detail": "Agree to terms"}
    ]

    session.refresh(task.profile)
    assert task.profile.custom_values == {}


def test_confirm_mapping_persists_portfolio_url_as_custom_value(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.label = "Show us your code portfolio"
    field.name = "developer_portfolio"
    field.selector = "#code-portfolio"
    field.field_type = "url"
    field.required = False
    field.mapped_profile_key = None
    field.mapped_value = "https://github.com/example"
    session.commit()

    response = client.post(f"/tasks/{task.id}/confirm-mapping")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "READY_TO_FILL"
    assert payload["profile_updates"] == [
        {
            "field_id": field.id,
            "profile_key": "custom:code_portfolio",
            "previous_value": None,
            "new_value": "https://github.com/example",
            "action": "created",
        }
    ]
    assert payload["profile_skipped"] == []

    session.refresh(task.profile)
    assert task.profile.custom_values == {"code_portfolio": "https://github.com/example"}


def test_manual_mapping_correction_skips_llm_call_for_same_form(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)

    response = client.put(
        f"/tasks/{task.id}/fields/{field.id}",
        json={"mapped_profile_key": "email"},
    )

    assert response.status_code == 200

    second_profile = Profile(
        profile_name="Second endpoint profile",
        full_name="Grace Hopper",
        email="grace@example.com",
    )
    second_task = Task(
        url="https://example.com/form",
        profile=second_profile,
        status="MAPPING_READY",
    )
    second_field = FormField(
        task=second_task,
        label="Where can we reach you?",
        selector="#contact",
        field_type="email",
        required=True,
    )
    session.add(second_task)
    session.add(second_field)
    session.commit()

    llm_json = json.dumps(
        {
            "mappings": [
                {
                    "field_id": second_field.id,
                    "mapped_profile_key": "email",
                    "confidence": 0.93,
                }
            ]
        }
    )

    with patch(
        "app.services.llm_client.LLMClient.suggest_mapping",
        return_value=LLMResult(success=True, content=None, raw_response=llm_json),
    ) as request_mapping:
        mapped = map_fields_with_llm(second_task.id, session, provider="deepseek")

    request_mapping.assert_not_called()
    assert mapped[0].mapped_profile_key == "email"
    assert mapped[0].mapped_value == "grace@example.com"
    assert mapped[0].confidence == 1.0


def test_manual_value_can_be_saved_to_profile_custom_value_and_reused(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.label = "Preferred work location"
    field.selector = "#location"
    field.field_type = "text"
    session.commit()

    response = client.put(
        f"/tasks/{task.id}/fields/{field.id}",
        json={
            "mapped_value": "Shanghai",
            "save_to_profile": True,
            "profile_custom_key": "preferred_location",
        },
    )

    assert response.status_code == 200
    assert response.json()["mapped_profile_key"] == "custom:preferred_location"
    assert response.json()["mapped_value"] == "Shanghai"

    session.refresh(task.profile)
    assert task.profile.custom_values == {"preferred_location": "Shanghai"}

    second_task = Task(
        url="https://example.com/form",
        profile=task.profile,
        status="MAPPING_READY",
    )
    second_field = FormField(
        task=second_task,
        label="Preferred work location",
        selector="#location",
        field_type="text",
        required=True,
    )
    session.add(second_task)
    session.add(second_field)
    session.commit()

    with patch("app.services.llm_client.LLMClient.suggest_mapping") as request_mapping:
        mapped = map_fields_with_llm(second_task.id, session, provider="deepseek")

    request_mapping.assert_not_called()
    assert mapped[0].mapped_profile_key == "custom:preferred_location"
    assert mapped[0].mapped_value == "Shanghai"
    assert mapped[0].confidence == 1.0


def test_fill_rejects_missing_required_values_before_browser_work(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    task.status = "READY_TO_FILL"
    field.mapped_profile_key = "email"
    field.mapped_value = None
    session.commit()

    response = client.post(f"/tasks/{task.id}/fill")

    assert response.status_code == 409
    assert "Required fields need values" in response.json()["detail"]


def test_fill_rejects_mapped_fields_before_user_confirms_mapping(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = "ada@example.com"
    session.commit()

    with patch(
        "app.routers.tasks.fill_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as fill_form:
        response = client.post(f"/tasks/{task.id}/fill")

    assert response.status_code == 409
    assert response.json() == {"detail": "Review and confirm mapping before filling"}
    fill_form.assert_not_awaited()


def test_analyze_pauses_when_login_is_required(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task_without_fields(session)

    with (
        patch(
            "app.routers.tasks.extract_form_analysis",
            new=AsyncMock(
                return_value=SimpleNamespace(fields=[], login_required=True),
            ),
        ) as extract_analysis,
        patch("app.routers.tasks.prepare_login_session") as prepare_login,
    ):
        response = client.post(f"/tasks/{task.id}/analyze")

    assert response.status_code == 200
    assert response.json()["status"] == "LOGIN_REQUIRED"
    assert response.json()["form_fields"] == []
    assert extract_analysis.await_count == 1
    prepare_login.assert_not_called()

    logs = list(
        session.scalars(
            select(ActionLog)
            .where(ActionLog.task_id == task.id)
            .order_by(ActionLog.step)
        )
    )
    assert [log.action for log in logs] == ["analyze_form", "login_required"]
    assert logs[-1].status == "WAITING"


def test_analyze_reuses_cached_form_analysis_for_same_url(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    first_task = create_task_without_fields(session)
    second_task = create_task_without_fields(session)
    extracted_field = ExtractedFormField(
        element_ref="field_1",
        form_title="Contact information",
        section_title=None,
        label="Email",
        selector="#email",
        field_type="email",
        placeholder=None,
        name="email",
        html_id="email",
        current_value=None,
        required=True,
    )

    with patch(
        "app.routers.tasks.extract_form_analysis",
        new=AsyncMock(
            return_value=SimpleNamespace(
                fields=[extracted_field],
                login_required=False,
            ),
        ),
    ) as extract_analysis:
        first_response = client.post(f"/tasks/{first_task.id}/analyze")
        second_response = client.post(f"/tasks/{second_task.id}/analyze")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert extract_analysis.await_count == 1
    assert first_response.json()["form_fields"][0]["selector"] == "#email"
    assert second_response.json()["form_fields"][0]["selector"] == "#email"


def test_analyze_persists_extract_form_runtime_call(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify legacy analysis records the browser read as a runtime tool call."""

    client, session = test_environment
    task = create_task_without_fields(session)
    extracted_field = ExtractedFormField(
        element_ref="field_1",
        form_title="Contact information",
        section_title=None,
        label="Email",
        selector="#email",
        field_type="email",
        placeholder=None,
        name="email",
        html_id="email",
        current_value=None,
        required=True,
    )

    with patch(
        "app.routers.tasks.extract_form_analysis",
        new=AsyncMock(
            return_value=SimpleNamespace(
                fields=[extracted_field],
                login_required=False,
            ),
        ),
    ):
        response = client.post(f"/tasks/{task.id}/analyze")

    assert response.status_code == 200
    call = session.get(AgentToolCall, f"task-{task.id}:extract_form")
    assert call is not None
    assert call.tool_name == "extract_form"
    assert call.status == "SUCCEEDED"
    assert call.governance_decision["decision"] == "ALLOW"
    result = session.get(AgentToolResult, f"task-{task.id}:extract_form")
    assert result is not None
    assert result.output_json["field_count"] == 1
    assert result.output_json["login_required"] is False


def test_analyze_supports_security_questionnaire_workflow(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify security questionnaires reuse the review-first form analysis path."""

    client, session = test_environment
    task = create_task_without_fields(session)
    task.workflow_type = "security_questionnaire"
    session.commit()
    extracted_field = ExtractedFormField(
        element_ref="field_1",
        form_title="Security questionnaire",
        section_title="Access control",
        label="Do you enforce multi-factor authentication?",
        selector="#mfa",
        field_type="text",
        placeholder=None,
        name="mfa",
        html_id="mfa",
        current_value=None,
        required=True,
        options=[],
    )

    with patch(
        "app.routers.tasks.extract_form_analysis",
        new=AsyncMock(
            return_value=SimpleNamespace(
                fields=[extracted_field],
                login_required=False,
            ),
        ),
    ):
        response = client.post(f"/tasks/{task.id}/analyze")

    assert response.status_code == 200
    assert response.json()["workflow_type"] == "security_questionnaire"
    assert response.json()["status"] == "MAPPING_READY"
    assert response.json()["form_fields"][0]["label"] == "Do you enforce multi-factor authentication?"


def test_analyze_supports_vendor_onboarding_workflow(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify vendor onboarding reuses the review-first form analysis path."""

    client, session = test_environment
    task = create_task_without_fields(session)
    task.workflow_type = "vendor_onboarding"
    session.commit()
    extracted_field = ExtractedFormField(
        element_ref="field_1",
        form_title="Vendor onboarding",
        section_title="Company profile",
        label="Vendor legal name",
        selector="#vendor-name",
        field_type="text",
        placeholder=None,
        name="vendor_name",
        html_id="vendor-name",
        current_value=None,
        required=True,
        options=[],
    )

    with patch(
        "app.routers.tasks.extract_form_analysis",
        new=AsyncMock(
            return_value=SimpleNamespace(
                fields=[extracted_field],
                login_required=False,
            ),
        ),
    ):
        response = client.post(f"/tasks/{task.id}/analyze")

    assert response.status_code == 200
    assert response.json()["workflow_type"] == "vendor_onboarding"
    assert response.json()["status"] == "MAPPING_READY"
    assert response.json()["form_fields"][0]["label"] == "Vendor legal name"


def test_rules_mapping_adds_source_backed_security_questionnaire_answers(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify Phase 2 source-backed suggestions are persisted for review."""

    client, session = test_environment
    profile = Profile(
        profile_name="Security profile",
        full_name="Ada Lovelace",
        email="security@example.com",
    )
    task = Task(
        url="file:///app/examples/security-questionnaire.html",
        profile=profile,
        status="MAPPING_READY",
        workflow_status="MAPPING_READY",
        workflow_type="security_questionnaire",
    )
    fields = [
        FormField(
            task=task,
            label="Do you enforce multi-factor authentication?",
            selector="#mfa",
            field_type="textarea",
            required=True,
        ),
        FormField(
            task=task,
            label="Do you encrypt data at rest?",
            selector="#encryption",
            field_type="select",
            required=True,
            options=[
                {"label": "Yes", "value": "yes", "selector": "#encryption"},
                {"label": "No", "value": "no", "selector": "#encryption"},
            ],
        ),
        FormField(
            task=task,
            label="Administrator password",
            selector="#password",
            field_type="password",
            required=False,
        ),
    ]
    session.add_all([task, *fields])
    session.commit()

    response = client.post(f"/tasks/{task.id}/map-fields?mode=rules")

    assert response.status_code == 200
    payload_by_label = {field["label"]: field for field in response.json()}
    assert payload_by_label["Do you enforce multi-factor authentication?"]["mapped_value"].startswith("Yes.")
    assert payload_by_label["Do you encrypt data at rest?"]["mapped_value"] == "yes"
    assert payload_by_label["Administrator password"]["mapped_value"] is None

    checkpoints = client.get(f"/tasks/{task.id}/checkpoints").json()
    mapping_checkpoint = next(item for item in checkpoints if item["stage"] == "MAPPING")
    suggestions = mapping_checkpoint["output"]["source_suggestions"]
    assert suggestions[0]["source"] == "mock-security-policy.md"
    assert suggestions[0]["status"] == "needs_review"


def test_login_and_analyze_retries_original_url_after_manual_login(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task_without_fields(session)
    task.status = "LOGIN_REQUIRED"
    session.commit()
    extracted_field = ExtractedFormField(
        element_ref="field_1",
        form_title="Contact information",
        section_title=None,
        label="Email",
        selector="#email",
        field_type="email",
        placeholder=None,
        name="email",
        html_id="email",
        current_value=None,
        required=True,
        options=[],
    )

    with (
        patch(
            "app.routers.tasks.prepare_login_session",
            new=AsyncMock(return_value=("browser-session", False)),
        ) as prepare_login,
        patch(
            "app.routers.tasks.extract_form_analysis",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    fields=[extracted_field],
                    login_required=False,
                ),
            ),
        ) as extract_analysis,
    ):
        response = client.post(f"/tasks/{task.id}/login-and-analyze")

    assert response.status_code == 200
    assert response.json()["status"] == "MAPPING_READY"
    assert response.json()["form_fields"][0]["selector"] == "#email"
    prepare_login.assert_awaited_once_with(
        url=task.url,
        profile_id=task.profile_id,
    )
    extract_analysis.assert_awaited_once_with(task.url, task.profile_id)

    logs = list(
        session.scalars(
            select(ActionLog)
            .where(ActionLog.task_id == task.id)
            .order_by(ActionLog.step)
        )
    )
    assert [log.action for log in logs] == [
        "manual_login",
        "resume_after_login",
        "extract_fields",
    ]


def test_login_and_analyze_persists_extract_form_runtime_call(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify post-login browser analysis records a runtime tool call."""

    client, session = test_environment
    task = create_task_without_fields(session)
    task.status = "LOGIN_REQUIRED"
    session.commit()
    extracted_field = ExtractedFormField(
        element_ref="field_1",
        form_title="Contact information",
        section_title=None,
        label="Email",
        selector="#email",
        field_type="email",
        placeholder=None,
        name="email",
        html_id="email",
        current_value=None,
        required=True,
        options=[],
    )

    with (
        patch(
            "app.routers.tasks.prepare_login_session",
            new=AsyncMock(return_value=("browser-session", False)),
        ),
        patch(
            "app.routers.tasks.extract_form_analysis",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    fields=[extracted_field],
                    login_required=False,
                ),
            ),
        ),
    ):
        response = client.post(f"/tasks/{task.id}/login-and-analyze")

    assert response.status_code == 200
    call = session.get(AgentToolCall, f"task-{task.id}:extract_form")
    assert call is not None
    assert call.tool_name == "extract_form"
    assert call.status == "SUCCEEDED"
    result = session.get(AgentToolResult, f"task-{task.id}:extract_form")
    assert result is not None
    assert result.output_json["field_count"] == 1
    assert result.output_json["login_required"] is False


def test_analyze_persists_field_options_for_review(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task = create_task_without_fields(session)
    extracted_field = ExtractedFormField(
        element_ref="field_1",
        form_title="Application",
        section_title="Preferences",
        label="Preferred location",
        selector="#remote",
        field_type="radio",
        placeholder=None,
        name="location",
        html_id="remote",
        current_value=None,
        required=True,
        options=[
            {"label": "Remote", "value": "remote", "selector": "#remote"},
            {"label": "Office", "value": "office", "selector": "#office"},
        ],
    )

    with patch(
        "app.routers.tasks.extract_form_analysis",
        new=AsyncMock(
            return_value=SimpleNamespace(
                fields=[extracted_field],
                login_required=False,
            ),
        ),
    ):
        response = client.post(f"/tasks/{task.id}/analyze")

    assert response.status_code == 200
    assert response.json()["form_fields"][0]["options"] == [
        {"label": "Remote", "value": "remote", "selector": "#remote"},
        {"label": "Office", "value": "office", "selector": "#office"},
    ]

    saved_field = session.get(FormField, response.json()["form_fields"][0]["id"])
    assert saved_field is not None
    assert saved_field.options == [
        {"label": "Remote", "value": "remote", "selector": "#remote"},
        {"label": "Office", "value": "office", "selector": "#office"},
    ]


def test_list_screenshots_omits_missing_files(
    test_environment: tuple[TestClient, Session],
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = test_environment
    task = create_task_without_fields(session)
    screenshots_dir = tmp_path / "screenshots"
    screenshots_dir.mkdir()
    existing_file = screenshots_dir / "existing.png"
    existing_file.write_bytes(b"image")
    monkeypatch.setattr("app.routers.tasks.BACKEND_DIR", tmp_path, raising=False)

    session.add_all(
        [
            Screenshot(
                task_id=task.id,
                file_path="screenshots/missing.png",
                stage="missing",
            ),
            Screenshot(
                task_id=task.id,
                file_path="screenshots/existing.png",
                stage="existing",
            ),
        ]
    )
    session.commit()

    response = client.get(f"/tasks/{task.id}/screenshots")

    assert response.status_code == 200
    assert [item["stage"] for item in response.json()] == ["existing"]


def test_confirm_mapping_respects_do_not_save_policy(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = "new@example.com"
    field.profile_memory_policy = "do_not_save"
    session.commit()

    response = client.post(f"/tasks/{task.id}/confirm-mapping")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "READY_TO_FILL"
    assert payload["profile_updates"] == []
    assert payload["profile_skipped"] == [
        {"field_id": field.id, "reason": "do_not_save", "detail": "Where can we reach you?"}
    ]

    session.refresh(task.profile)
    assert task.profile.email == "ada@example.com"


def test_confirm_mapping_respects_force_save_policy(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.label = "Preferred work location"
    field.selector = "#location"
    field.field_type = "text"
    field.required = False
    field.mapped_value = "Beijing"
    field.profile_memory_policy = "force_save"
    session.commit()

    response = client.post(f"/tasks/{task.id}/confirm-mapping")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "READY_TO_FILL"
    assert len(payload["profile_updates"]) == 1
    assert payload["profile_updates"][0]["new_value"] == "Beijing"

    session.refresh(task.profile)
    assert "preferred_work_location" in task.profile.custom_values
    assert task.profile.custom_values["preferred_work_location"] == "Beijing"


def test_confirm_mapping_force_save_blocks_sensitive_fields(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)
    field.label = "Agree to terms"
    field.field_type = "checkbox"
    field.required = False
    field.mapped_value = "true"
    field.profile_memory_policy = "force_save"
    session.commit()

    response = client.post(f"/tasks/{task.id}/confirm-mapping")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "READY_TO_FILL"
    assert payload["profile_updates"] == []
    assert payload["profile_skipped"] == [
        {"field_id": field.id, "reason": "force_save_blocked", "detail": "Agree to terms"}
    ]

    session.refresh(task.profile)
    assert task.profile.custom_values == {}


def test_confirm_mapping_policy_blocks_sensitive_memory_write(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify policy blocks sensitive writes even when value is present."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.label = "API key"
    field.mapped_profile_key = "custom:api_key"
    field.mapped_value = "secret-token"
    session.commit()

    response = client.post(f"/tasks/{task.id}/confirm-mapping")

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile_updates"] == []
    assert payload["profile_skipped"] == [
        {"field_id": field.id, "reason": "policy_blocked", "detail": "Sensitive credentials must not be written to profile memory."}
    ]


def test_fill_returns_409_when_required_field_needs_policy_approval(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify required review-required fields block fill until approved."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.label = "Agree to terms"
    field.field_type = "checkbox"
    field.required = True
    field.mapped_profile_key = "custom:terms"
    field.mapped_value = "true"
    field.confidence = 1.0
    task.status = "READY_TO_FILL"
    task.workflow_status = "READY_TO_FILL"
    session.commit()

    response = client.post(f"/tasks/{task.id}/fill")

    assert response.status_code == 409
    assert response.json()["detail"] == "Required fields require approval before filling: Agree to terms"


def test_fill_returns_409_when_required_proposal_is_not_approved(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify pending runtime proposals cannot reach browser fill."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = "pending@example.com"
    field.confidence = 0.99
    task.status = "READY_TO_FILL"
    task.workflow_status = "READY_TO_FILL"
    run = AgentRun(
        id=f"task-{task.id}",
        legacy_task_id=task.id,
        goal="Review before fill.",
        target_url=task.url,
        profile_id=task.profile_id,
        workflow_hint=task.workflow_type,
        status="WAITING_REVIEW",
        mode="deterministic",
    )
    run.final_result = {}
    proposal = AgentProposal(
        id=f"task-{task.id}-field-{field.id}",
        run=run,
        proposal_type="field_value",
        target_type="form_field",
        target_ref=str(field.id),
        proposed_value="pending@example.com",
        rationale="Review before fill.",
        confidence=0.99,
        risk_level="low",
        status="PENDING",
    )
    session.add_all([run, proposal])
    session.commit()

    with patch(
        "app.routers.tasks.fill_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as fill_form:
        response = client.post(f"/tasks/{task.id}/fill")

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Required fields require approval before filling: Where can we reach you?"
    )
    fill_form.assert_not_awaited()


def test_fill_can_retry_after_required_field_approval(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify fill stays retryable after approving a required field gate."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.label = "Agree to terms"
    field.field_type = "checkbox"
    field.required = True
    field.mapped_profile_key = "custom:terms"
    field.mapped_value = "true"
    field.confidence = 1.0
    task.status = "READY_TO_FILL"
    task.workflow_status = "READY_TO_FILL"
    session.commit()

    first_response = client.post(f"/tasks/{task.id}/fill")

    assert first_response.status_code == 409
    session.refresh(task)
    assert task.status == "READY_TO_FILL"

    approval = session.scalar(
        select(ApprovalRequest)
        .where(ApprovalRequest.task_id == task.id, ApprovalRequest.step_name == f"fill_field:{field.id}")
        .order_by(ApprovalRequest.id.desc())
    )
    assert approval is not None

    approve_response = client.post(f"/approvals/{approval.id}/approve")
    assert approve_response.status_code == 200

    with patch(
        "app.routers.tasks.fill_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as fill_form:
        fill_form.return_value = (SimpleNamespace(id=1), [])
        retry_response = client.post(f"/tasks/{task.id}/fill")

    assert retry_response.status_code == 200
    fill_form.assert_awaited_once()


def test_fill_persists_runtime_tool_call_result(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify legacy fill records the browser write as a runtime tool call."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.mapped_profile_key = "email"
    field.mapped_value = "ada@example.com"
    field.confidence = 0.99
    task.status = "READY_TO_FILL"
    task.workflow_status = "READY_TO_FILL"
    session.commit()

    with patch(
        "app.routers.tasks.fill_form_and_capture_screenshot",
        new_callable=AsyncMock,
    ) as fill_form:
        fill_form.return_value = (SimpleNamespace(id=5), [])
        response = client.post(f"/tasks/{task.id}/fill")

    assert response.status_code == 200
    call = session.get(AgentToolCall, f"task-{task.id}:fill_form")
    assert call is not None
    assert call.tool_name == "fill_form"
    assert call.status == "SUCCEEDED"
    assert call.risk_level == "medium"
    assert call.governance_decision["decision"] == "VERIFY_REQUIRED"
    result = session.get(AgentToolResult, f"task-{task.id}:fill_form")
    assert result is not None
    assert result.status == "SUCCEEDED"
    assert result.output_json == {
        "filled_count": 1,
        "screenshot_id": 5,
        "verification_count": 0,
    }


def test_confirm_mapping_requires_new_approval_when_memory_write_value_changes(
    test_environment: tuple[TestClient, Session],
) -> None:
    """Verify memory-write approvals are tied to the approved mapped value."""

    client, session = test_environment
    task, field = create_task_with_field(session)
    field.label = "Preference note"
    field.field_type = "text"
    field.required = False
    field.mapped_profile_key = "custom:consent_preference"
    field.mapped_value = "true"
    session.commit()

    first_response = client.post(f"/tasks/{task.id}/confirm-mapping")
    assert first_response.status_code == 200
    assert first_response.json()["profile_skipped"] == [
        {"field_id": field.id, "reason": "approval_required", "detail": "Consent-like profile writes require review."}
    ]

    first_approval = session.scalar(
        select(ApprovalRequest)
        .where(ApprovalRequest.task_id == task.id, ApprovalRequest.step_name == f"memory_write:{field.id}")
        .order_by(ApprovalRequest.id.desc())
    )
    assert first_approval is not None

    approve_response = client.post(f"/approvals/{first_approval.id}/approve")
    assert approve_response.status_code == 200

    field.mapped_value = "false"
    session.commit()

    second_response = client.post(f"/tasks/{task.id}/confirm-mapping")

    assert second_response.status_code == 200
    assert second_response.json()["profile_updates"] == []
    assert second_response.json()["profile_skipped"] == [
        {"field_id": field.id, "reason": "approval_required", "detail": "Consent-like profile writes require review."}
    ]

    pending_requests = list(
        session.scalars(
            select(ApprovalRequest).where(
                ApprovalRequest.task_id == task.id,
                ApprovalRequest.step_name == f"memory_write:{field.id}",
                ApprovalRequest.status == "PENDING",
            )
        )
    )
    assert len(pending_requests) == 1


def test_update_field_memory_policy_normalizes_none_to_auto(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, field = create_task_with_field(session)

    response = client.put(
        f"/tasks/{task.id}/fields/{field.id}",
        json={"profile_memory_policy": None, "mapped_value": "test"},
    )

    assert response.status_code == 200
    session.refresh(field)
    assert field.profile_memory_policy == "auto"


def test_list_checkpoints_returns_task_checkpoints(
    test_environment: tuple[TestClient, Session],
) -> None:
    client, session = test_environment
    task, _ = create_task_with_field(session)
    session.add(
        TaskCheckpoint(
            task_id=task.id,
            stage="ANALYSIS",
            status="SUCCESS",
            input_hash="test-hash",
            output={"field_count": 1},
        )
    )
    session.add(
        TaskCheckpoint(
            task_id=task.id,
            stage="MAPPING",
            status="FAILED",
            input_hash="test-hash-2",
            failure_reason="LLM_MAPPING_FAILED",
            error_message="Test error",
        )
    )
    session.commit()

    response = client.get(f"/tasks/{task.id}/checkpoints")

    assert response.status_code == 200
    checkpoints = response.json()
    assert len(checkpoints) == 2
    assert checkpoints[0]["stage"] == "MAPPING"
    assert checkpoints[0]["status"] == "FAILED"
    assert checkpoints[0]["failure_reason"] == "LLM_MAPPING_FAILED"
    assert checkpoints[0]["error_message"] == "Test error"
    assert checkpoints[1]["stage"] == "ANALYSIS"
    assert checkpoints[1]["status"] == "SUCCESS"


def test_map_fields_failure_sets_task_status_and_checkpoint(
    test_environment: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = test_environment
    task, _ = create_task_with_field(session)
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "test-deepseek-key")

    with patch(
        "app.routers.tasks.map_fields_with_llm_result",
        side_effect=Exception("LLM mapping failed"),
    ):
        response = client.post(f"/tasks/{task.id}/map-fields?provider=deepseek")

    assert response.status_code == 500

    session.refresh(task)
    assert task.status == "FAILED"

    checkpoints = list(
        session.scalars(
            select(TaskCheckpoint).where(TaskCheckpoint.task_id == task.id)
        )
    )
    assert len(checkpoints) == 1
    assert checkpoints[0].stage == "MAPPING"
    assert checkpoints[0].status == "FAILED"
    assert checkpoints[0].failure_reason == "LLM_MAPPING_FAILED"
    assert "LLM mapping failed" in checkpoints[0].error_message
