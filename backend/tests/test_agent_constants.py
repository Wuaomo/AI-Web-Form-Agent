"""Tests for agent constants to ensure stability and consistency."""

import pytest


def test_agent_role_constants_exist_and_uppercase():
    """Verify all agent role constants exist and are uppercase."""
    from app.agent_constants import (
        AGENT_ROLE_MAPPING_CRITIC,
        AGENT_ROLE_SAFETY_REVIEW,
        AGENT_ROLE_EXECUTION_VERIFICATION,
    )

    roles = [
        AGENT_ROLE_MAPPING_CRITIC,
        AGENT_ROLE_SAFETY_REVIEW,
        AGENT_ROLE_EXECUTION_VERIFICATION,
    ]

    for role in roles:
        assert role.isupper(), f"Agent role {role} is not uppercase"


def test_agent_role_constants_are_unique():
    """Verify agent role constants have unique values."""
    from app.agent_constants import (
        AGENT_ROLE_MAPPING_CRITIC,
        AGENT_ROLE_SAFETY_REVIEW,
        AGENT_ROLE_EXECUTION_VERIFICATION,
    )

    roles = [
        AGENT_ROLE_MAPPING_CRITIC,
        AGENT_ROLE_SAFETY_REVIEW,
        AGENT_ROLE_EXECUTION_VERIFICATION,
    ]

    assert len(roles) == len(set(roles)), "Agent role constants are not unique"


def test_agent_decision_constants_exist_and_uppercase():
    """Verify all agent decision constants exist and are uppercase."""
    from app.agent_constants import (
        AGENT_DECISION_PASS,
        AGENT_DECISION_REVIEW_REQUIRED,
        AGENT_DECISION_BLOCK,
    )

    decisions = [
        AGENT_DECISION_PASS,
        AGENT_DECISION_REVIEW_REQUIRED,
        AGENT_DECISION_BLOCK,
    ]

    for decision in decisions:
        assert decision.isupper(), f"Agent decision {decision} is not uppercase"


def test_agent_decision_constants_are_unique():
    """Verify agent decision constants have unique values."""
    from app.agent_constants import (
        AGENT_DECISION_PASS,
        AGENT_DECISION_REVIEW_REQUIRED,
        AGENT_DECISION_BLOCK,
    )

    decisions = [
        AGENT_DECISION_PASS,
        AGENT_DECISION_REVIEW_REQUIRED,
        AGENT_DECISION_BLOCK,
    ]

    assert len(decisions) == len(set(decisions)), "Agent decision constants are not unique"