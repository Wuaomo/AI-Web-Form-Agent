# Safety Model

AI Web Form Agent is built around reviewed automation. The browser can apply values, but sensitive or irreversible steps are blocked or paused for user approval.

## Architectural Safety Boundaries

### LangGraph: Orchestration Layer (Not Security Decision Layer)

LangGraph is the workflow orchestration engine that:
- Defines the execution order: analyze → retrieve → suggest → review → fill → verify → submit.
- Enforces interrupt points before sensitive actions: `interrupt_before=[REVIEW_GATE_NODE, SUBMIT_GATE_NODE]`.
- Maintains durable state with checkpoints for resume/replay.
- Does NOT make security decisions — it only orchestrates the flow and pauses at gates.

### LangChain: Suggestion Layer (Not Execution Layer)

LangChain is an optional enhancement for:
- Structured field mapping using LLMs.
- Retrieval of source-backed answers from policy documents.
- Improved suggestion quality for questionnaire items.
- Does NOT execute browser actions — it only provides suggestions.
- The system works without LangChain/LLMs in rules mode.

### PolicyEngine: Safety Decision Owner

The PolicyEngine is the authoritative safety decision maker:
- Blocks sensitive fields (passwords, OTPs, payment data).
- Refuses unsupported questionnaire answers.
- Flags risky operations with block/warn/safe classifications.
- Enforces action controls based on field type and policy rules.

### ApprovalGateService: Human-in-the-Loop

The ApprovalGateService ensures human oversight:
- Requires explicit approval before browser execution.
- Requires explicit approval before final submission.
- Stores approval history for audit trails.
- Prevents auto-submission without user consent.

### Playwright: Approved Execution Only

Playwright is restricted to:
- Filling only user-approved values.
- Verifying filled values in the DOM.
- Capturing screenshots for evidence.
- No auto-submission, auto-login, or destructive operations.

## Blocked Actions

- Password and OTP entry.
- Payment-card and purchase flows.
- CAPTCHA solving or anti-bot bypass.
- Destructive actions such as delete, cancel, or irreversible account changes.
- Automatic login or authentication bypass.

## Review-Required Actions

- Final form submission.
- Low-confidence field mappings.
- External navigation that changes the workflow target.
- Saving reusable profile memory from reviewed values.
- Any action classified by policy as requiring human approval.

## Data Not Stored As Memory

The app avoids saving one-time or sensitive values as reusable profile memory, including passwords, OTPs, payment cards, consent values, session tokens, and CAPTCHA responses.

## CAPTCHA And Anti-Bot Boundary

CAPTCHA and anti-bot challenges are treated as stop signs. The project does not attempt to solve, evade, or automate around them.

## Final Submission Approval

All workflows wait before final submit. The user must inspect the browser-executed page and approve the final submission step. Without approval, the workflow remains paused.

## Memory Safety

Profile memory is limited to reusable, reviewed fields. The user can inspect and edit profiles through the UI. The backend records mappings and traces for transparency, not for silent future submission.

## Default Demo Boundary

The default Docker demo runs without LLM API keys. Optional providers can be enabled for semantic mapping, but provider failures fall back to setup hints instead of forcing paid or network-dependent behavior.
