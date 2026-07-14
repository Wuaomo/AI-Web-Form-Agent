# Phase 6: Domain Workflow Templates

## Goal

Add a few concrete, review-first workflow templates that prove the system is
more than a generic form filler.

## Why

AI application projects look stronger when they solve real workflows end to end.
The project should stay narrow, but show that the same architecture can support
more than one browser task.

## Scope

Add domain templates only when they reuse the existing workflow pipeline:

- page analysis
- field extraction
- reviewed memory retrieval
- mapping and answer suggestion
- policy gates
- browser execution
- verification and traces

## Current Status

Completed:

- Security Questionnaire Workflow exists as an enabled Phase 1 domain template.
- Job Application Workflow exists as a disabled template.
- Web Data Extraction and Job / Research Summary already prove the template
  registry can support non-form-fill workflows.

Not complete yet:

- Vendor Onboarding Workflow template.
- Safety/test/UI review path for any newly enabled domain template.

## Candidate Templates

Start from the security questionnaire workflow added earlier, then add only the
next narrow template that reuses the same safety and review path:

1. Security Questionnaire Workflow
2. Job Application Workflow
3. Vendor Onboarding Workflow

Only one template should be enabled by default until its safety model, tests,
and UI review path are complete.

## Security Questionnaire Workflow

Use local mock assets:

- `examples/security-questionnaire.html`
- `examples/mock-security-policy.md`
- `examples/company-profile.md`

The workflow should:

- extract security and compliance questions from the page;
- retrieve candidate answers from reviewed memory or mock policy docs;
- show source evidence for each suggested answer;
- mark unsupported answers as needs review;
- block sensitive, auth, payment, CAPTCHA, OTP, and destructive fields;
- fill the browser only after user review;
- stop before final submission.

## Acceptance Criteria

- At least one domain template works in the local demo without LLM API keys.
- The template reuses existing planner, policy, memory, execution, and trace
  services.
- Unsupported or sensitive answers are not guessed.
- The demo explains why each suggested answer was used.
