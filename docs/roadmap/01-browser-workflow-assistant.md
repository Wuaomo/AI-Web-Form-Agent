# Phase 1: Browser Workflow Assistant

## Goal

Expand the app beyond form filling into a small browser workflow assistant.

## Why

A pure form filler feels too narrow. A browser workflow assistant can read pages, extract information, summarize tasks, and assist form completion while keeping human review.

## Scope

Add two workflows:

1. Web Data Extraction
2. Job / Research Summary

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
- Optional LLM generates:
  - summary
  - key requirements
  - action checklist
  - risks / missing information
- User can copy the report.

## Reuse Existing Code

- Reuse workflow templates.
- Reuse Playwright browser execution.
- Reuse screenshots and trace service.
- Reuse LLM provider config.
- Reuse Task Detail display where possible.

## Acceptance Criteria

- User can run Web Extraction from the UI.
- Extraction result is persisted.
- Task Detail shows extracted data and screenshot.
- Job Summary produces a copyable report.
- Existing form-fill workflow still works.

## Demo Story

Open a job page, extract requirements, generate a checklist, then use the form-fill workflow for the application form.

