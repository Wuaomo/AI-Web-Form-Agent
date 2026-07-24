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
5. Select the `Demo Applicant` profile and click "Create run".
6. On the Task Detail page, show the "Agent workflow" panel at the bottom of the run section.
7. Click "Start agent workflow" - the workflow will analyze the page, extract questions, retrieve policy sources, and suggest answers.
8. When the workflow pauses at "Review pending", click "Review suggestions" to go to Review Mapping.
9. In Review Mapping, show:
   - Source evidence from `mock-security-policy.md` (document name, matched section).
   - Confidence scores for each suggestion.
   - Safety flags (block/warn/safe) from the policy engine.
   - Approve/reject buttons for each field.
10. Approve all suggestions or selectively approve/reject individual fields.
11. Click "Submit review" - the workflow resumes, fills only approved values, and verifies them.
12. Return to Task Detail and show:
    - Updated workflow state showing "Verifying result" or "Completed".
    - Action logs, screenshot evidence, and verification status.
13. Stop at final submit approval and explain that the app does not submit without explicit user decision.
14. Open Evaluation and show how local benchmark runs compare rules/memory/LLM/runtime modes, tracking:
    - `safety_pass_rate`: Policy compliance and sensitive field handling.
    - `verification_pass_rate`: Browser fill accuracy.
    - `source_evidence_coverage`: Evidence-backed answer quality.

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
- The Security Questionnaire Assistant is the primary demo, showing source-backed answers from local policy documents via a LangGraph workflow.
- The workflow orchestration includes interrupt points before sensitive actions (review, submit).
- Answers are always suggestions with evidence - human review is required before execution.
- Optional providers can improve semantic mapping, but the rule-based path keeps the demo deterministic.
- The app treats browser automation as a reviewed workflow, not an invisible bot.
- Vendor onboarding demonstrates a second domain workflow using the same reviewed browser execution path.
- Screenshots, traces, and benchmark reports make behavior inspectable.
- Evaluation measures answer accuracy, source coverage, unsupported refusal, sensitive-field skip behavior, safety pass rate, and verification pass rate.

## Teardown

```powershell
docker compose down
```
