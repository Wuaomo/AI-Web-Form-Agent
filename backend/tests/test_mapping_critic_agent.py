"""Tests for mapping critic agent to ensure high-quality review without automatic changes."""

import pytest

from app.agent_constants import (
    AGENT_DECISION_PASS,
    AGENT_DECISION_REVIEW_REQUIRED,
)


def test_required_missing_field_creates_review_item():
    """Verify that a required unmapped field creates a review item."""

    from app.services.mapping_critic_agent import run_mapping_critic_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Email",
                "selector": "input[name='email']",
                "field_type": "text",
                "required": True,
                "mapped_profile_key": None,
                "mapped_value": None,
                "confidence": 0.9,
                "profile_memory_policy": "auto",
            },
            {
                "id": 2,
                "label": "Name",
                "selector": "input[name='name']",
                "field_type": "text",
                "required": False,
                "mapped_profile_key": "full_name",
                "mapped_value": "John Doe",
                "confidence": 0.85,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_mapping_critic_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_REVIEW_REQUIRED
    assert len(result["items"]) == 1
    assert result["items"][0]["field_id"] == 1
    assert result["items"][0]["issue"] == "REQUIRED_UNMAPPED"
    assert "Email" in result["items"][0]["message"]


def test_low_confidence_field_creates_review_item():
    """Verify that a low confidence field creates a review item."""

    from app.services.mapping_critic_agent import run_mapping_critic_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Address",
                "selector": "input[name='address']",
                "field_type": "text",
                "required": True,
                "mapped_profile_key": "home_address",
                "mapped_value": "123 Main St",
                "confidence": 0.6,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_mapping_critic_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_REVIEW_REQUIRED
    assert len(result["items"]) == 1
    assert result["items"][0]["field_id"] == 1
    assert result["items"][0]["issue"] == "LOW_CONFIDENCE"
    assert "Address" in result["items"][0]["message"]
    assert result["items"][0]["confidence"] == 0.6


def test_all_high_confidence_required_fields_produce_pass():
    """Verify that all high-confidence required fields produce PASS."""

    from app.services.mapping_critic_agent import run_mapping_critic_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Email",
                "selector": "input[name='email']",
                "field_type": "email",
                "required": True,
                "mapped_profile_key": "email",
                "mapped_value": "test@example.com",
                "confidence": 0.95,
                "profile_memory_policy": "auto",
            },
            {
                "id": 2,
                "label": "Phone",
                "selector": "input[name='phone']",
                "field_type": "tel",
                "required": True,
                "mapped_profile_key": "phone",
                "mapped_value": "+1-555-123-4567",
                "confidence": 0.88,
                "profile_memory_policy": "auto",
            },
            {
                "id": 3,
                "label": "Name",
                "selector": "input[name='name']",
                "field_type": "text",
                "required": False,
                "mapped_profile_key": "full_name",
                "mapped_value": "John Doe",
                "confidence": 0.92,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_mapping_critic_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_PASS
    assert len(result["items"]) == 0
    assert "valid and complete" in result["summary"]


def test_empty_mapped_value_for_required_field_creates_review_item():
    """Verify that required field with empty mapped value creates review item."""

    from app.services.mapping_critic_agent import run_mapping_critic_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Email",
                "selector": "input[name='email']",
                "field_type": "email",
                "required": True,
                "mapped_profile_key": "email",
                "mapped_value": "",
                "confidence": 0.95,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_mapping_critic_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_REVIEW_REQUIRED
    assert len(result["items"]) == 1
    assert result["items"][0]["field_id"] == 1
    assert result["items"][0]["issue"] == "EMPTY_MAPPED_VALUE"


def test_duplicate_profile_key_creates_review_items():
    """Verify that duplicate profile key mappings create review items."""

    from app.services.mapping_critic_agent import run_mapping_critic_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Email",
                "selector": "input[name='email1']",
                "field_type": "email",
                "required": True,
                "mapped_profile_key": "email",
                "mapped_value": "test@example.com",
                "confidence": 0.95,
                "profile_memory_policy": "auto",
            },
            {
                "id": 2,
                "label": "Confirm Email",
                "selector": "input[name='email2']",
                "field_type": "email",
                "required": True,
                "mapped_profile_key": "email",
                "mapped_value": "test@example.com",
                "confidence": 0.90,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_mapping_critic_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_REVIEW_REQUIRED
    assert len(result["items"]) == 2
    issue_types = [item["issue"] for item in result["items"]]
    assert issue_types.count("DUPLICATE_KEY") == 2


def test_multiple_issues_create_multiple_review_items():
    """Verify that multiple issues create separate review items."""

    from app.services.mapping_critic_agent import run_mapping_critic_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Email",
                "selector": "input[name='email']",
                "field_type": "email",
                "required": True,
                "mapped_profile_key": None,
                "mapped_value": None,
                "confidence": 0.95,
                "profile_memory_policy": "auto",
            },
            {
                "id": 2,
                "label": "Address",
                "selector": "input[name='address']",
                "field_type": "text",
                "required": True,
                "mapped_profile_key": "address",
                "mapped_value": "123 Main St",
                "confidence": 0.5,
                "profile_memory_policy": "auto",
            },
            {
                "id": 3,
                "label": "Phone",
                "selector": "input[name='phone']",
                "field_type": "tel",
                "required": False,
                "mapped_profile_key": "phone",
                "mapped_value": "",
                "confidence": 0.85,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_mapping_critic_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_REVIEW_REQUIRED
    assert len(result["items"]) == 2

    issue_types = [item["issue"] for item in result["items"]]
    assert "REQUIRED_UNMAPPED" in issue_types
    assert "LOW_CONFIDENCE" in issue_types


def test_optional_unmapped_field_passes():
    """Verify that optional unmapped fields do not trigger review."""

    from app.services.mapping_critic_agent import run_mapping_critic_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Email",
                "selector": "input[name='email']",
                "field_type": "email",
                "required": True,
                "mapped_profile_key": "email",
                "mapped_value": "test@example.com",
                "confidence": 0.95,
                "profile_memory_policy": "auto",
            },
            {
                "id": 2,
                "label": "Twitter",
                "selector": "input[name='twitter']",
                "field_type": "text",
                "required": False,
                "mapped_profile_key": None,
                "mapped_value": None,
                "confidence": 0.6,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_mapping_critic_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_REVIEW_REQUIRED
    assert len(result["items"]) == 1
    assert result["items"][0]["issue"] == "LOW_CONFIDENCE"
    assert result["items"][0]["field_id"] == 2


def test_confidence_at_threshold_passes():
    """Verify that confidence exactly at threshold (0.75) passes."""

    from app.services.mapping_critic_agent import run_mapping_critic_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Address",
                "selector": "input[name='address']",
                "field_type": "text",
                "required": True,
                "mapped_profile_key": "address",
                "mapped_value": "123 Main St",
                "confidence": 0.75,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_mapping_critic_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_PASS
    assert len(result["items"]) == 0