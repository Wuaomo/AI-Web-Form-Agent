"""Detect actions that require human approval before they are executed."""

from dataclasses import dataclass

from playwright.async_api import Page

SENSITIVE_KEYWORDS = (
    "submit",
    "send",
    "confirm",
    "pay",
    "delete",
    "purchase",
    "register",
    "apply",
    "continue",
)

SUBMIT_LIKE_SELECTOR = (
    'button, input[type="submit"], input[type="button"], '
    '[role="button"]'
)


@dataclass(frozen=True)
class SafetyCheckResult:
    """Result of scanning the current page for approval-gated actions."""

    requires_approval: bool
    reasons: tuple[str, ...]


async def detect_submit_like_actions(page: Page) -> SafetyCheckResult:
    """Find visible controls that look like final or sensitive actions."""

    controls = page.locator(SUBMIT_LIKE_SELECTOR)
    reasons: list[str] = []

    for index in range(await controls.count()):
        control = controls.nth(index)
        if not await control.is_visible():
            continue

        # The DOM property includes browser defaults, such as a <button>
        # inside a form defaulting to type="submit".
        control_type = await control.evaluate(
            "(element) => (element.type || '').toLowerCase()"
        )
        text = " ".join(
            filter(
                None,
                (
                    await control.inner_text(),
                    await control.get_attribute("value"),
                    await control.get_attribute("aria-label"),
                    await control.get_attribute("title"),
                ),
            )
        ).strip()
        normalized_text = " ".join(text.lower().split())
        matched_keywords = [
            keyword
            for keyword in SENSITIVE_KEYWORDS
            if keyword in normalized_text
        ]

        if control_type == "submit" or matched_keywords:
            description = text or f'type="{control_type or "button"}"'
            reason = f'Sensitive action detected: "{description}"'
            if reason not in reasons:
                reasons.append(reason)

    return SafetyCheckResult(
        requires_approval=bool(reasons),
        reasons=tuple(reasons),
    )
