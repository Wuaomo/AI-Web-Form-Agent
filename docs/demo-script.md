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
3. Open Workflows and show that the Form Fill Workflow is enabled while other templates are staged for future use.
4. Create a run from a local or simple test form URL and select the demo profile.
5. Analyze the form and show extracted fields.
6. Generate mappings and open Review Mapping.
7. Correct or confirm any low-confidence field.
8. Confirm mappings so the browser execution can fill the form.
9. Open the task detail page and show action logs, screenshot evidence, and verification status.
10. Stop at final submit approval and explain that the app does not submit without the user's explicit decision.
11. Open Evaluation and show how local benchmark runs track mapping quality.

## Reviewer Talking Points

- The default demo uses local data and does not require LLM API keys.
- Optional providers can improve semantic mapping, but the rule-based path keeps the demo deterministic.
- The app treats browser automation as a reviewed workflow, not an invisible bot.
- Screenshots, traces, and benchmark reports make behavior inspectable.

## Teardown

```powershell
docker compose down
```
