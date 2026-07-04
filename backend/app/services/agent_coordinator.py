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


def hash_input_data(data: dict) -> str:
    """Return a SHA256 hash of the input data for caching purposes."""

    serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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


def run_agent_reviews(db: Session, task: Task) -> dict[str, AgentReview]:
    """Run all agent reviews in sequence and return results.

    Agents are called in a fixed order:
    1. Mapping Critic - reviews field-to-profile mappings
    2. Safety Review - checks for sensitive data handling
    3. Execution Verification - validates form filling execution

    Each agent returns a strict JSON decision that is validated before persistence.
    """

    results = {}
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

    mapping_review = run_mapping_critic_review(db, task, review_input)
    if mapping_review:
        input_hash = hash_input_data(review_input)
        saved_review = save_agent_review(
            db,
            task.id,
            AGENT_ROLE_MAPPING_CRITIC,
            mapping_review["decision"],
            input_hash,
            json.dumps(mapping_review, ensure_ascii=False),
            mapping_review.get("model"),
            mapping_review.get("provider"),
        )
        results[AGENT_ROLE_MAPPING_CRITIC] = saved_review

    safety_review = run_safety_review(db, task, review_input)
    if safety_review:
        input_hash = hash_input_data(review_input)
        saved_review = save_agent_review(
            db,
            task.id,
            AGENT_ROLE_SAFETY_REVIEW,
            safety_review["decision"],
            input_hash,
            json.dumps(safety_review, ensure_ascii=False),
            safety_review.get("model"),
            safety_review.get("provider"),
        )
        results[AGENT_ROLE_SAFETY_REVIEW] = saved_review

    execution_review = run_execution_verification_review(db, task, review_input)
    if execution_review:
        input_hash = hash_input_data(review_input)
        saved_review = save_agent_review(
            db,
            task.id,
            AGENT_ROLE_EXECUTION_VERIFICATION,
            execution_review["decision"],
            input_hash,
            json.dumps(execution_review, ensure_ascii=False),
            execution_review.get("model"),
            execution_review.get("provider"),
        )
        results[AGENT_ROLE_EXECUTION_VERIFICATION] = saved_review

    return results


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