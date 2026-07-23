# Demo Script

This is a 3 to 5 minute local demo for reviewers.

## Setup

```powershell
docker compose up --build
```

In another terminal:

```powershell
python scripts/seed_demo.py
```

Open:

```text
http://localhost:5173
```

## Walkthrough

### Security Questionnaire Assistant (Primary Demo)

1. Open the Runs dashboard and point out the backend health badge.
2. Open Profiles and show `Demo Applicant`.
3. Open Workflows and show Security Questionnaire as the first available template.
4. Create a run with **Security Questionnaire** selected and click "Use Docker demo form".
5. Select the `Demo Applicant` profile.
6. Click "Create run" - the form will be analyzed and mappings generated in rules mode (no LLM API key required).
7. Open Review Mapping and show source-backed answers from `mock-security-policy.md`.
8. Explain that answers are suggestions with `needs review` status, showing document name, matched section, and match score.
9. Confirm only after reviewing the source evidence.
10. Open the task detail page and show action logs, screenshot evidence, and verification status.
11. Stop at final submit approval and explain that the app does not submit without explicit user decision.
12. Open Evaluation and show how local benchmark runs track mapping quality, source evidence coverage, refusal rate, and sensitive-field skip rate.

### Vendor Onboarding (Secondary)

1. Create a new run and select **Vendor Onboarding**.
2. Analyze the page and generate mappings in rules mode.
3. Open Review Mapping and show that safe contact fields can be reviewed while vendor-specific or sensitive fields stay under human control.
4. Confirm mappings, fill the page, inspect verification evidence, and stop before final submit approval.

### Generic Form Fill (Optional)

1. Create a new run and select **Generic Form Fill**.
2. Enter a test form URL or use the Docker demo form.
3. Analyze the form and show extracted fields.
4. Generate mappings and open Review Mapping.
5. Correct or confirm any low-confidence field.
6. Confirm mappings so the browser execution can fill the form.
7. Inspect screenshot and verification evidence.
8. Stop at final submit approval.

## Reviewer Talking Points

- The default demo uses local data and does not require LLM API keys.
- The Security Questionnaire Assistant is the primary demo, showing source-backed answers from local policy documents.
- Answers are always suggestions with evidence - human review is required before execution.
- Optional providers can improve semantic mapping, but the rule-based path keeps the demo deterministic.
- The app treats browser automation as a reviewed workflow, not an invisible bot.
- Vendor onboarding demonstrates a second domain workflow using the same reviewed browser execution path.
- Screenshots, traces, and benchmark reports make behavior inspectable.
- Evaluation measures answer accuracy, source coverage, unsupported refusal, and sensitive-field skip behavior.

## Teardown

```powershell
docker compose down
```
