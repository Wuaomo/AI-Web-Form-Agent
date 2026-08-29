"""Action-level governance for runtime tool calls."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.services.agent_runtime.schemas import GovernanceDecision

if TYPE_CHECKING:
    from app.services.agent_runtime.tool_runtime import AgentTool


MAPPING_TOOL_NAMES = {"map_fields", "generate_field_mappings"}
SUBMIT_TOOL_NAMES = {"submit_form", "confirm_submit"}
SENSITIVE_TERMS = {
    "captcha",
    "card",
    "credit card",
    "otp",
    "passcode",
    "password",
    "payment",
    "verification code",
}


class GovernanceEngine:
    """Classify whether a runtime tool call may execute."""

    def evaluate_tool_call(
        self,
        tool: "AgentTool",
        tool_input: dict[str, Any],
    ) -> GovernanceDecision:
        """Return the runtime governance decision for one tool call."""

        if tool.risk_level == "blocked":
            return GovernanceDecision(
                decision="BLOCKED",
                reason="Tool is marked blocked.",
                risk_level="blocked",
                blocked_reason="Tool is marked blocked.",
            )

        if tool.mutates_browser and _has_sensitive_browser_input(tool_input):
            return GovernanceDecision(
                decision="BLOCKED",
                reason="Sensitive browser action is not allowed.",
                risk_level="blocked",
                blocked_reason="Sensitive browser action is not allowed.",
            )

        if tool.mutates_external_system or tool.name in SUBMIT_TOOL_NAMES:
            return GovernanceDecision(
                decision="APPROVAL_REQUIRED",
                reason="Tool may commit an external or final browser action.",
                risk_level=tool.risk_level,
            )

        if tool.mutates_browser:
            return GovernanceDecision(
                decision="REVIEW_REQUIRED",
                reason="Tool changes browser state and needs human review first.",
                risk_level=tool.risk_level,
            )

        if tool.name in MAPPING_TOOL_NAMES:
            return GovernanceDecision(
                decision="RECORD_ONLY",
                reason="Field mapping is non-destructive but should be recorded.",
                risk_level=tool.risk_level,
            )

        return GovernanceDecision(
            decision="ALLOW",
            reason="Read-only tool call is allowed.",
            risk_level=tool.risk_level,
        )


def _has_sensitive_browser_input(tool_input: dict[str, Any]) -> bool:
    haystack = " ".join(str(value).lower() for value in tool_input.values())
    return any(term in haystack for term in SENSITIVE_TERMS)


__all__ = ["GovernanceEngine"]
