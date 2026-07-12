# Agent Instructions

Read this file first in every coding session.

For detailed project boundaries and architecture, also read:

- `AGENT_RULES.md`
- `docs/roadmap/00-ai-engineer-alignment-roadmap.md`

## Current Goal

Build AI Web Form Agent as a portfolio-ready full-stack AI browser workflow
assistant, not just a form filler.

Use `docs/roadmap/` as the source of truth for future project direction.

Current roadmap order:

1. Phase 1: Browser Workflow Assistant
2. Phase 2: Retrieval Memory Layer
3. Phase 3: Evaluation Workbench
4. Phase 4: Agent Observability
5. Phase 5: Portfolio Packaging

## Product Principles

- User path first, engineering evidence second.
- Do not add more dashboards or panels unless they directly improve the user workflow.
- Advanced/debug data should be collapsed by default.
- The local demo must work without LLM API keys.
- Optional LLM providers must not break rules-mode behavior.
- Keep the project interview-ready: clear demo, clear architecture, measurable improvement.

## Safety Boundaries

- Never auto-submit forms without explicit user approval.
- Never bypass login, CAPTCHA, payment, OTP, or destructive actions.
- Never store passwords, payment data, OTPs, CAPTCHA, or one-time consent values in memory.
- Keep human review before browser execution.

## Development Rules

- Prefer small, testable changes.
- Reuse existing FastAPI, React, Playwright, SQLite patterns.
- Do not add new dependencies unless clearly necessary.
- Run relevant tests before claiming completion.
- For frontend changes, run `cd frontend && npm test && npm run build`.
- For backend changes, run `cd backend && python -m pytest`.

## Docker Notes

- In Docker, demo local files use container paths like `file:///app/examples/llm-registration.html`.
- Do not use Windows host paths like `file:///C:/Users/...` for Docker-run browser analysis.
- Backend reads local secrets from `.env`; never commit `.env`.

## Do Not Do

- Do not resurrect old `docs/trae-upgrade`, `docs/superpowers/plans`, or `docs/superpowers/specs` phase systems.
- Do not frame the project as only a form filler.
- Do not make observability the main UI experience.
- Do not add production auth, multi-user account systems, cloud browser fleets, or broad scraping features.
