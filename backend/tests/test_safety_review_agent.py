"""Tests for safety review agent to ensure security rules are enforced."""

import pytest

from app.agent_constants import (
    AGENT_DECISION_PASS,
    AGENT_DECISION_REVIEW_REQUIRED,
    AGENT_DECISION_BLOCK,
)


def test_password_field_blocks():
    """Verify that password field produces BLOCK decision."""

    from app.services.safety_review_agent import run_safety_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Password",
                "selector": "input[name='password']",
                "field_type": "password",
                "required": True,
                "mapped_profile_key": None,
                "mapped_value": None,
                "confidence": 0.95,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_safety_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_BLOCK
    assert len(result["items"]) == 1
    assert result["items"][0]["field_id"] == 1
    assert result["items"][0]["issue"] == "BLOCKED_FIELD"
    assert "password" in result["items"][0]["message"].lower()


def test_payment_field_blocks():
    """Verify that payment field produces BLOCK decision."""

    from app.services.safety_review_agent import run_safety_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Payment Method",
                "selector": "select[name='payment']",
                "field_type": "select",
                "required": True,
                "mapped_profile_key": "payment_method",
                "mapped_value": "credit_card",
                "confidence": 0.9,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_safety_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_BLOCK
    assert len(result["items"]) == 1
    assert result["items"][0]["field_id"] == 1
    assert result["items"][0]["issue"] == "BLOCKED_FIELD"
    assert "payment" in result["items"][0]["message"].lower()


def test_terms_checkbox_requires_review():
    """Verify that terms checkbox produces REVIEW_REQUIRED decision."""

    from app.services.safety_review_agent import run_safety_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "I agree to the terms and conditions",
                "selector": "input[name='terms']",
                "field_type": "checkbox",
                "required": True,
                "mapped_profile_key": None,
                "mapped_value": None,
                "confidence": 0.85,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_safety_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_REVIEW_REQUIRED
    assert len(result["items"]) == 1
    assert result["items"][0]["field_id"] == 1
    assert result["items"][0]["issue"] == "REVIEW_REQUIRED_FIELD"
    assert "terms" in result["items"][0]["message"].lower()


def test_normal_email_field_passes():
    """Verify that normal email field produces PASS decision."""

    from app.services.safety_review_agent import run_safety_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Email Address",
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
                "label": "Full Name",
                "selector": "input[name='name']",
                "field_type": "text",
                "required": True,
                "mapped_profile_key": "full_name",
                "mapped_value": "John Doe",
                "confidence": 0.92,
                "profile_memory_policy": "auto",
            },
            {
                "id": 3,
                "label": "Phone Number",
                "selector": "input[name='phone']",
                "field_type": "tel",
                "required": False,
                "mapped_profile_key": "phone",
                "mapped_value": "+1-555-123-4567",
                "confidence": 0.88,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_safety_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_PASS
    assert len(result["items"]) == 0
    assert "No security issues" in result["summary"]


def test_otp_field_blocks():
    """Verify that OTP field produces BLOCK decision."""

    from app.services.safety_review_agent import run_safety_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "OTP Code",
                "selector": "input[name='otp']",
                "field_type": "text",
                "required": True,
                "mapped_profile_key": None,
                "mapped_value": None,
                "confidence": 0.9,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_safety_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_BLOCK
    assert len(result["items"]) == 1
    assert result["items"][0]["field_id"] == 1
    assert result["items"][0]["issue"] == "BLOCKED_FIELD"


def test_card_field_blocks():
    """Verify that card field produces BLOCK decision."""

    from app.services.safety_review_agent import run_safety_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Credit Card Number",
                "selector": "input[name='card_number']",
                "field_type": "text",
                "required": True,
                "mapped_profile_key": None,
                "mapped_value": None,
                "confidence": 0.95,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_safety_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_BLOCK
    assert len(result["items"]) == 1
    assert result["items"][0]["field_id"] == 1
    assert result["items"][0]["issue"] == "BLOCKED_FIELD"


def test_delete_field_blocks():
    """Verify that delete field produces BLOCK decision."""

    from app.services.safety_review_agent import run_safety_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Delete Account",
                "selector": "input[name='delete']",
                "field_type": "checkbox",
                "required": False,
                "mapped_profile_key": None,
                "mapped_value": None,
                "confidence": 0.85,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_safety_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_BLOCK
    assert len(result["items"]) == 1


def test_purchase_field_blocks():
    """Verify that purchase field produces BLOCK decision."""

    from app.services.safety_review_agent import run_safety_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Purchase Confirmation",
                "selector": "input[name='purchase']",
                "field_type": "checkbox",
                "required": True,
                "mapped_profile_key": None,
                "mapped_value": None,
                "confidence": 0.9,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_safety_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_BLOCK


def test_consent_checkbox_requires_review():
    """Verify that consent checkbox produces REVIEW_REQUIRED decision."""

    from app.services.safety_review_agent import run_safety_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "I consent to data processing",
                "selector": "input[name='consent']",
                "field_type": "checkbox",
                "required": True,
                "mapped_profile_key": None,
                "mapped_value": None,
                "confidence": 0.85,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_safety_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_REVIEW_REQUIRED
    assert len(result["items"]) == 1
    assert result["items"][0]["issue"] == "REVIEW_REQUIRED_FIELD"


def test_privacy_checkbox_requires_review():
    """Verify that privacy checkbox produces REVIEW_REQUIRED decision."""

    from app.services.safety_review_agent import run_safety_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Privacy Policy Agreement",
                "selector": "input[name='privacy']",
                "field_type": "checkbox",
                "required": True,
                "mapped_profile_key": None,
                "mapped_value": None,
                "confidence": 0.85,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_safety_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_REVIEW_REQUIRED
    assert len(result["items"]) == 1
    assert result["items"][0]["issue"] == "REVIEW_REQUIRED_FIELD"


def test_billing_field_blocks():
    """Verify that billing field produces BLOCK decision."""

    from app.services.safety_review_agent import run_safety_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Billing Address",
                "selector": "input[name='billing_address']",
                "field_type": "text",
                "required": True,
                "mapped_profile_key": "billing_address",
                "mapped_value": "456 Billing St",
                "confidence": 0.9,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_safety_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_BLOCK


def test_blocked_fields_take_precedence_over_review_required():
    """Verify that blocked fields take precedence over review required fields."""

    from app.services.safety_review_agent import run_safety_review

    mock_task = None
    mock_db = None

    review_input = {
        "form_fields": [
            {
                "id": 1,
                "label": "Password",
                "selector": "input[name='password']",
                "field_type": "password",
                "required": True,
                "mapped_profile_key": None,
                "mapped_value": None,
                "confidence": 0.95,
                "profile_memory_policy": "auto",
            },
            {
                "id": 2,
                "label": "Terms and Conditions",
                "selector": "input[name='terms']",
                "field_type": "checkbox",
                "required": True,
                "mapped_profile_key": None,
                "mapped_value": None,
                "confidence": 0.85,
                "profile_memory_policy": "auto",
            },
        ],
    }

    result = run_safety_review(mock_db, mock_task, review_input)

    assert result["decision"] == AGENT_DECISION_BLOCK
    assert len(result["items"]) == 2