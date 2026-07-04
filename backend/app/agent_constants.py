"""Agent role and decision constants for controlled multi-agent review system.

These constants define the specialized AI review roles that participate in
the form automation workflow, and the decision outcomes each agent can return.
All values are stable uppercase strings suitable for database storage and API responses.

Agent Roles:
    MAPPING_CRITIC - Reviews field-to-profile mappings for accuracy and completeness
    SAFETY_REVIEW - Checks for sensitive data handling and security concerns
    EXECUTION_VERIFICATION - Validates that form filling was executed correctly

Agent Decisions:
    PASS - Agent approves the review item
    REVIEW_REQUIRED - Agent identifies issues requiring human review
    BLOCK - Agent identifies critical issues blocking progression
"""

AGENT_ROLE_MAPPING_CRITIC = "MAPPING_CRITIC"
AGENT_ROLE_SAFETY_REVIEW = "SAFETY_REVIEW"
AGENT_ROLE_EXECUTION_VERIFICATION = "EXECUTION_VERIFICATION"

AGENT_DECISION_PASS = "PASS"
AGENT_DECISION_REVIEW_REQUIRED = "REVIEW_REQUIRED"
AGENT_DECISION_BLOCK = "BLOCK"