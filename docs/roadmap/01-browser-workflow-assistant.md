# Phase 1: Browser Workflow Assistant

## Goal

Build a review-first browser workflow assistant that reads pages, extracts information, suggests actions with evidence, and executes only after human review.

## Why

A pure form filler feels too narrow. A browser workflow assistant should read a
page, identify what information is required, propose next actions, and execute
only after human review.

## Scope

Keep the completed earlier workflow paths, then add one JD-aligned workflow:

1. Web Data Extraction
2. Job / Research Summary
3. Security Questionnaire Workflow

## Current Status

Completed:

- Form Fill Workflow is the main local demo workflow.
- Web Data Extraction Workflow is implemented with Playwright page extraction,
  persistence, trace/checkpoint data, and frontend display.
- Job / Research Summary Workflow is implemented with deterministic summary,
  key requirements, action checklist, risks, and copyable report output.
- Security Questionnaire Workflow is enabled, planned, backed by a local demo
  fixture, and reuses the review-first form analysis, mapping, fill,
  verification, and submit-approval path.

Not complete yet:

- Source-backed questionnaire answer suggestions.
- Local mock security policy and company profile fixtures.

## Features

### Web Data Extraction

- User enters a URL.
- Backend opens the page with Playwright.
- Extract:
  - title
  - headings
  - main text blocks
  - links
  - tables
  - forms if present
- Save extraction result, screenshot, logs, and trace spans.
- Frontend displays structured extracted data.

### Job / Research Summary

- User enters a URL and goal.
- System extracts page content.
- Deterministic rules generate:
  - summary
  - key requirements
  - action checklist
  - risks / missing information
- User can copy the report.

### Security Questionnaire Workflow

- User opens a local security/compliance-style questionnaire page.
- System extracts questions, fields, labels, hints, and required markers.
- System identifies:
  - answerable fields
  - missing information
  - unsupported questions
  - sensitive or unsafe fields
- User reviews suggested values before browser execution.
- Browser fills only approved values and stops before final submission.

## Reuse Existing Code

- Reuse workflow templates.
- Reuse Playwright browser execution.
- Reuse screenshots and trace service.
- Reuse LLM provider config.
- Reuse Task Detail display where possible.
- Reuse policy gates and approval requests.

## Acceptance Criteria

- User can run Web Extraction from the UI.
- Extraction result is persisted.
- Task Detail shows extracted data and screenshot.
- Job Summary produces a copyable report.
- Security Questionnaire Workflow runs locally without LLM API keys.
- Task Detail shows required information, missing information, and blocked
  fields.
- Existing form-fill workflow still works.

## Demo Story

Current demo: open a job or research page, extract structured content, generate
a research summary, then use the form-fill workflow.

Next demo: open a security questionnaire fixture, extract required answers,
review suggested values, fill safe fields, and stop before final submission.

