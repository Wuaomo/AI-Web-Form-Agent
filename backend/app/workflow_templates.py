"""Static workflow template registry for platform-facing workflow selection."""

from copy import deepcopy

from app.workflow_constants import (
    WORKFLOW_TYPE_DATA_ENTRY,
    WORKFLOW_TYPE_FORM_FILL,
    WORKFLOW_TYPE_JOB_APPLICATION,
    WORKFLOW_TYPE_WEB_DATA_EXTRACT,
)

WORKFLOW_TEMPLATES: dict[str, dict[str, object]] = {
    WORKFLOW_TYPE_FORM_FILL: {
        "id": WORKFLOW_TYPE_FORM_FILL,
        "name": "Form Fill Workflow",
        "description": (
            "Analyze a web form, map profile data, review values, fill fields, "
            "verify, and wait for submit approval."
        ),
        "enabled": True,
        "steps": [
            "open_url",
            "extract_form",
            "map_fields",
            "review_mapping",
            "confirm_mapping",
            "fill_form",
            "verify_fields",
            "wait_for_submit_approval",
            "submit_form",
        ],
        "approval_policy": {
            "submit": "always_required",
            "password": "blocked",
            "otp": "blocked",
            "payment": "blocked",
            "low_confidence_mapping": "review_required",
        },
    },
    WORKFLOW_TYPE_WEB_DATA_EXTRACT: {
        "id": WORKFLOW_TYPE_WEB_DATA_EXTRACT,
        "name": "Web Data Extraction Workflow",
        "description": "Open a page, extract structured data, review the result, and save it.",
        "enabled": False,
        "steps": [
            "open_url",
            "extract_dom",
            "identify_target_data",
            "extract_structured_json",
            "review_extraction",
            "save_result",
        ],
        "approval_policy": {
            "external_navigation": "review_required",
        },
    },
    WORKFLOW_TYPE_DATA_ENTRY: {
        "id": WORKFLOW_TYPE_DATA_ENTRY,
        "name": "Data Entry Workflow",
        "description": "Map a structured record into a web application form and verify the saved result.",
        "enabled": False,
        "steps": [
            "open_url",
            "extract_form",
            "map_structured_record",
            "review_mapping",
            "fill_form",
            "verify_fields",
            "save_after_approval",
        ],
        "approval_policy": {
            "save": "review_required",
            "destructive_action": "blocked",
        },
    },
    WORKFLOW_TYPE_JOB_APPLICATION: {
        "id": WORKFLOW_TYPE_JOB_APPLICATION,
        "name": "Job Application Workflow",
        "description": (
            "Apply to a job using a profile while preserving user review and "
            "submit approval."
        ),
        "enabled": False,
        "steps": [
            "open_url",
            "detect_login_gate",
            "extract_job_context",
            "extract_application_form",
            "map_profile_and_resume_context",
            "review_mapping",
            "fill_form",
            "verify_fields",
            "wait_for_submit_approval",
            "submit_form",
        ],
        "approval_policy": {
            "submit": "always_required",
            "password": "blocked",
            "otp": "blocked",
            "payment": "blocked",
        },
    },
}


def list_workflow_templates(include_disabled: bool = True) -> list[dict[str, object]]:
    """Return static workflow templates for API responses and validation."""

    templates = [
        deepcopy(template)
        for template in WORKFLOW_TEMPLATES.values()
        if include_disabled or bool(template.get("enabled"))
    ]
    return templates


def get_workflow_template(template_id: str) -> dict[str, object] | None:
    """Return one workflow template by id, if it exists."""

    template = WORKFLOW_TEMPLATES.get(template_id)
    if template is None:
        return None
    return deepcopy(template)


def require_enabled_template(template_id: str) -> dict[str, object]:
    """Return an enabled template or raise a descriptive validation error."""

    template = get_workflow_template(template_id)
    if template is None:
        raise ValueError(f"Workflow template not found: {template_id}")

    if not bool(template.get("enabled")):
        raise ValueError(f"Workflow template is not enabled: {template_id}")

    return template
