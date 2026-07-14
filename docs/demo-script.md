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

1. Open the Runs dashboard and point out the backend health badge.
2. Open Profiles and show `Demo Applicant`.
3. Open Workflows and show the enabled Form Fill, extraction, job summary, and security questionnaire workflows.
4. Create a run from a local or simple test form URL and select the demo profile.
5. Analyze the form and show extracted fields.
6. Generate mappings and open Review Mapping.
7. Correct or confirm any low-confidence field.
8. Confirm mappings so the browser execution can fill the form.
9. Open the task detail page and show action logs, screenshot evidence, and verification status.
10. Stop at final submit approval and explain that the app does not submit without the user's explicit decision.
11. Open Evaluation and show how local benchmark runs track mapping quality, source evidence coverage, refusal rate, and sensitive-field skip rate.

## Security Questionnaire Variant

1. Create a Security Questionnaire Workflow run with the Docker demo URL.
2. Analyze the page and generate mappings in rules mode.
3. Open Review Mapping and show source-backed answers from `mock-security-policy.md`.
4. Explain that the answers are suggestions with `needs review` status, then confirm only after inspection.
5. Copy the debug report and point out that source evidence is included without raw suggested values.

## Reviewer Talking Points

- The default demo uses local data and does not require LLM API keys.
- Optional providers can improve semantic mapping, but the rule-based path keeps the demo deterministic.
- The app treats browser automation as a reviewed workflow, not an invisible bot.
- Questionnaire answers can use local policy evidence without requiring an LLM key.
- Screenshots, traces, and benchmark reports make behavior inspectable.
- Evaluation measures answer accuracy, source coverage, unsupported refusal, and sensitive-field skip behavior.

## Teardown

```powershell
docker compose down
```
