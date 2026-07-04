"""Deterministic coordinator for controlled multi-agent review system.

This coordinator calls specialist AI agents in a fixed order and persists
their strict JSON decisions. Agents do not directly control Playwright and
cannot approve final submission.
"""

import hashlib
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.agent_constants import (
    AGENT_ROLE_MAPPING_CRITIC,
    AGENT_ROLE_SAFETY_REVIEW,
    AGENT_ROLE_EXECUTION_VERIFICATION,
    AGENT_DECISION_PASS,
    AGENT_DECISION_REVIEW_REQUIRED,
    AGENT_DECISION_BLOCK,
)
from app.models import AgentReview, Task
from app.services.mapping_critic_agent import run_mapping_critic_review
from app.services.safety_review_agent import run_safety_review
from app.services.execution_verification_agent import run_execution_verification_review

logger = logging.getLogger(__name__)

AGENT_ROLE_TO_FUNCTION = {
    AGENT_ROLE_MAPPING_CRITIC: run_mapping_critic_review,
    AGENT_ROLE_SAFETY_REVIEW: run_safety_review,
    AGENT_ROLE_EXECUTION_VERIFICATION: run_execution_verification_review,
}

REQUIRED_AGENT_OUTPUT_KEYS = {"decision", "summary", "items"}


def build_agent_input_hash(payload: object) -> str:
    """Return deterministic hash for agent input."""

    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_agent_json(payload: object, required_keys: set[str] = REQUIRED_AGENT_OUTPUT_KEYS) -> dict[str, object]:
    """Validate agent JSON output and return a dict.

    Raises ValueError if required keys are missing.
    """

    if not isinstance(payload, dict):
        raise ValueError("Agent output must be a dictionary")

    missing_keys = required_keys - set(payload.keys())
    if missing_keys:
        raise ValueError(f"Missing required keys in agent output: {', '.join(missing_keys)}")

    return payload


def save_agent_review(
    db: Session,
    task_id: int,
    role: str,
    decision: str,
    input_hash: str,
    output_json: str,
    model: Optional[str] = None,
    provider: Optional[str] = None,
) -> AgentReview:
    """Persist an agent review decision to the database."""

    review = AgentReview(
        task_id=task_id,
        role=role,
        decision=decision,
        input_hash=input_hash,
        output_json=output_json,
        model=model,
        provider=provider,
    )
    db.add(review)
    db.flush()
    return review


def get_agent_reviews_for_task(db: Session, task_id: int) -> list[AgentReview]:
    """Return all agent reviews for a task."""

    return (
        db.query(AgentReview)
        .filter(AgentReview.task_id == task_id)
        .order_by(AgentReview.created_at)
        .all()
    )


def get_agent_review_by_role(db: Session, task_id: int, role: str) -> Optional[AgentReview]:
    """Return the most recent agent review for a specific role."""

    return (
        db.query(AgentReview)
        .filter(AgentReview.task_id == task_id, AgentReview.role == role)
        .order_by(AgentReview.created_at.desc())
        .first()
    )


def run_agent_review_sequence(task_id: int, db: Session, roles: list[str]) -> list[AgentReview]:
    """Run selected review agents in fixed order.

    Agents are executed in the order specified in the roles list.
    Each agent's output is validated for required keys (decision, summary, items).
    Invalid JSON becomes REVIEW_REQUIRED with evidence of the validation failure.
    Coordinator persists every accepted decision.
    """

    task = db.get(Task, task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")

    results = []
    review_input = {
        "task_id": task.id,
        "url": task.url,
        "status": task.status,
        "form_fields": [
            {
                "id": field.id,
                "label": field.label,
                "selector": field.selector,
                "field_type": field.field_type,
                "required": field.required,
                "mapped_profile_key": field.mapped_profile_key,
                "mapped_value": field.mapped_value,
                "confidence": field.confidence,
                "profile_memory_policy": field.profile_memory_policy,
            }
            for field in task.form_fields
        ],
    }

    input_hash = build_agent_input_hash(review_input)

    for role in roles:
        if role not in AGENT_ROLE_TO_FUNCTION:
            logger.warning(f"Unknown agent role: {role}, skipping")
            continue

        agent_function = AGENT_ROLE_TO_FUNCTION[role]

        try:
            agent_output = agent_function(db, task, review_input)

            validated_output = validate_agent_json(agent_output)

            decision = validated_output["decision"]
            if decision not in {AGENT_DECISION_PASS, AGENT_DECISION_REVIEW_REQUIRED, AGENT_DECISION_BLOCK}:
                raise ValueError(f"Invalid decision value: {decision}")

            saved_review = save_agent_review(
                db,
                task.id,
                role,
                decision,
                input_hash,
                json.dumps(validated_output, ensure_ascii=False),
                validated_output.get("model"),
                validated_output.get("provider"),
            )
            results.append(saved_review)

        except Exception as exc:
            logger.error(f"Agent {role} failed: {exc}")

            failure_output = {
                "decision": AGENT_DECISION_REVIEW_REQUIRED,
                "summary": f"Agent {role} validation failed",
                "items": [{"error": str(exc)}],
                "role": role,
                "model": None,
                "provider": None,
            }

            saved_review = save_agent_review(
                db,
                task.id,
                role,
                AGENT_DECISION_REVIEW_REQUIRED,
                input_hash,
                json.dumps(failure_output, ensure_ascii=False),
                None,
                None,
            )
            results.append(saved_review)

    return results


def run_agent_reviews(db: Session, task: Task) -> dict[str, AgentReview]:
    """Run all agent reviews in sequence and return results.

    Agents are called in a fixed order:
    1. Mapping Critic - reviews field-to-profile mappings
    2. Safety Review - checks for sensitive data handling
    3. Execution Verification - validates form filling execution

    Each agent returns a strict JSON decision that is validated before persistence.
    """

    roles = [AGENT_ROLE_MAPPING_CRITIC, AGENT_ROLE_SAFETY_REVIEW, AGENT_ROLE_EXECUTION_VERIFICATION]
    results = run_agent_review_sequence(task.id, db, roles)
    return {review.role: review for review in results}


def has_blocking_review(db: Session, task_id: int) -> bool:
    """Return whether any agent review has blocked the task."""

    blocking_review = (
        db.query(AgentReview)
        .filter(AgentReview.task_id == task_id, AgentReview.decision == AGENT_DECISION_BLOCK)
        .first()
    )
    return blocking_review is not None


def get_review_summary(db: Session, task_id: int) -> dict[str, str]:
    """Return a summary of all agent review decisions for a task."""

    reviews = get_agent_reviews_for_task(db, task_id)
    summary = {}
    for review in reviews:
        summary[review.role] = review.decision
    return summary