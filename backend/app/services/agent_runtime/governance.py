"""Action-level governance for runtime tool calls."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.services.agent_runtime.schemas import GovernanceDecision
from app.services.policy_engine import evaluate_memory_write
from app.workflow_constants import (
    POLICY_DECISION_BLOCK,
    POLICY_DECISION_REVIEW_REQUIRED,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MEDIUM,
)

if TYPE_CHECKING:
    from app.services.agent_runtime.tool_runtime import AgentTool, ToolExecutionContext


MAPPING_TOOL_NAMES = {"map_fields", "generate_field_mappings"}
MEMORY_WRITE_TOOL_NAMES = {"memory_write", "save_memory", "save_reviewed_memory"}
SUBMIT_TOOL_NAMES = {"submit_form", "confirm_submit"}
SENSITIVE_TERMS = {
    "2fa",
    "api key",
    "captcha",
    "card",
    "credit card",
    "cvv",
    "otp",
    "one time",
    "one-time",
    "passcode",
    "password",
    "payment",
    "secret",
    "token",
    "verification code",
}
RISK_LEVEL_MAP = {
    RISK_LEVEL_LOW: "low",
    RISK_LEVEL_MEDIUM: "medium",
    RISK_LEVEL_HIGH: "high",
}


class GovernanceEngine:
    """Classify whether a runtime tool call may execute."""

    def evaluate_tool_call(
        self,
        tool: "AgentTool",
        tool_input: dict[str, Any],
        *,
        tool_call_id: str | None = None,
        context: "ToolExecutionContext | None" = None,
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

        has_prior_approval = _has_prior_approval(tool, tool_call_id, context)

        if tool.name in MEMORY_WRITE_TOOL_NAMES:
            policy = evaluate_memory_write(
                profile_key=str(tool_input.get("profile_key") or ""),
                value=str(tool_input.get("value") or ""),
                field_label=str(tool_input.get("field_label") or ""),
            )
            risk_level = RISK_LEVEL_MAP.get(policy.risk_level, tool.risk_level)
            if policy.decision == POLICY_DECISION_BLOCK:
                return GovernanceDecision(
                    decision="BLOCKED",
                    reason=policy.reason,
                    risk_level="blocked",
                    blocked_reason=policy.reason,
                )
            if not has_prior_approval:
                return GovernanceDecision(
                    decision="REVIEW_REQUIRED",
                    reason=policy.reason
                    if policy.decision == POLICY_DECISION_REVIEW_REQUIRED
                    else "Memory writes require review after filtering.",
                    risk_level=risk_level,
                )
            return GovernanceDecision(
                decision="RECORD_ONLY",
                reason="Filtered memory write has prior review approval.",
                risk_level=risk_level,
            )

        if tool.mutates_external_system or tool.name in SUBMIT_TOOL_NAMES:
            if has_prior_approval:
                return GovernanceDecision(
                    decision="VERIFY_REQUIRED",
                    reason="Approved write requires verification after execution.",
                    risk_level=tool.risk_level,
                )
            return GovernanceDecision(
                decision="APPROVAL_REQUIRED",
                reason="Tool may commit an external or final browser action.",
                risk_level=tool.risk_level,
            )

        if tool.mutates_browser:
            if has_prior_approval:
                return GovernanceDecision(
                    decision="VERIFY_REQUIRED",
                    reason="Approved browser write requires verification after execution.",
                    risk_level=tool.risk_level,
                )
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
    haystack = " ".join(_flatten_values(tool_input)).lower()
    return any(term in haystack for term in SENSITIVE_TERMS)


def _flatten_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [part for nested in value.values() for part in _flatten_values(nested)]
    if isinstance(value, list | tuple | set):
        return [part for nested in value for part in _flatten_values(nested)]
    return [str(value)]


def _has_prior_approval(
    tool: "AgentTool",
    tool_call_id: str | None,
    context: "ToolExecutionContext | None",
) -> bool:
    if context is None:
        return False

    approved_ids = context.metadata.get("approved_tool_call_ids", [])
    if tool_call_id is not None and tool_call_id in approved_ids:
        return True

    approved_tools = context.metadata.get("approved_tool_names", [])
    return tool.name in approved_tools


__all__ = ["GovernanceEngine"]
