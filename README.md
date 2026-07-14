# AI Web Form Agent

Review-first AI browser workflow assistant for structured web tasks.

The app reads browser pages, extracts structured fields or questions, retrieves reviewed knowledge when available, proposes safe actions with evidence, executes in Chromium after review, records trace evidence, and pauses before final submission.

## What It Is

This project demonstrates safe, inspectable AI workflow automation. It combines a FastAPI backend, SQLite persistence, Playwright execution, workflow templates, reviewed memory, local policy retrieval, policy/approval gates, workflow traces, local evaluation runs, and a React/Vite console.

The default demo runs without LLM API keys. Optional providers can assist semantic mapping, but deterministic rules remain available.

## Not Just A Form Filler

Form filling is the first concrete workflow, but the system is built around a broader agent loop:

```text
read a browser page
  -> extract fields, questions, and page context
  -> retrieve reviewed memory or local policy evidence
  -> propose mappings and answers
  -> require human review
  -> execute safe browser actions
  -> verify results and record traces
  -> evaluate behavior with local benchmarks
```

## Why It Matters

Browser agents are risky when they submit forms invisibly. This app keeps the user in the loop with mapping review, approval gates, screenshots, action logs, traces, and local benchmark evidence.

## Current App Surface

- Workflow console for runs, templates, approvals, traces, and evaluation.
- Review mapping flow before browser execution.
- Deterministic planner and tool registry for enabled workflow templates.
- Policy engine and persisted approval requests for risky steps.
- SQLite-backed workflow memory for reviewed reusable values.
- Source-backed questionnaire suggestions from local mock policy documents.
- Trace spans, screenshots, action logs, verification evidence, and usage/cost summaries.
- Local benchmark/evaluation center with comparison reports.

## Core Workflow

```text
Create Profile
  -> Create Run
  -> Analyze Form
  -> Plan Workflow
  -> Generate Mapping
  -> Review Mapping
  -> Apply Policy Gates
  -> Confirm Mapping
  -> Fill Form
  -> Verify Fields
  -> Wait for Submit Approval
```

## Supported Templates

- Form Fill Workflow: enabled for the local demo.
- Web Data Extraction Workflow: enabled.
- Job Research Summary Workflow: enabled.
- Security Questionnaire Workflow: enabled for source-backed compliance-style questionnaires.
- Vendor Onboarding Workflow: enabled for review-first vendor intake forms.
- Data Entry Workflow: registered but disabled.
- Job Application Workflow: registered but disabled.

## Architecture

```text
React UI
  -> FastAPI API
    -> SQLite profiles, tasks, jobs, approvals, traces
    -> Workflow templates, planner, and tool registry
    -> Form extraction and field mapping services
    -> Policy and approval gates
    -> Workflow memory and source-backed retrieval examples
    -> Playwright browser execution
    -> Benchmark runner and reports
```

See [docs/architecture.md](docs/architecture.md) for the module map, workflow loop, trace model, and evaluation model.

## Safety Model

- Final submit always waits for user approval.
- Passwords, OTPs, payment data, CAPTCHA, and destructive actions are blocked.
- Low-confidence mappings require review.
- One-time or sensitive values are not saved as reusable profile memory.
- Unsupported questionnaire answers are left empty instead of guessed.

See [docs/safety-model.md](docs/safety-model.md).

## Memory And Retrieval

The project uses two deliberately small retrieval paths:

- Reviewed workflow memory stores confirmed, reusable, non-sensitive field mappings.
- Local mock policy documents provide source-backed answers for security questionnaires.

Questionnaire suggestions carry source evidence such as document name, matched section, match score, and `needs_review` status. The user still reviews values before browser execution.

## Evaluation

The benchmark suite uses local HTML fixtures and expected JSON answers to track extraction quality, mapping accuracy, required-field coverage, action rejection, login-gate handling, questionnaire answer accuracy, source evidence coverage, unsupported-answer refusal, sensitive-field skip rate, and regression details.

See [docs/evaluation-report-sample.md](docs/evaluation-report-sample.md) and [backend/benchmarks/README.md](backend/benchmarks/README.md).

| Area | Evidence |
| --- | --- |
| Form mapping | 16 local benchmark fixtures and expected JSON files |
| Retrieval | reviewed memory mode with source/stale governance and source-backed questionnaire suggestions |
| Safety | action-control rejection, login-gate detection, sensitive skip rules |
| Observability | workflow spans, screenshots, verification results, debug reports |
| Regression tracking | stored benchmark runs, comparison metrics, Markdown export |

## Observability

Task Detail keeps advanced evidence collapsed by default while preserving the data needed to explain failures:

- workflow trace spans with phase, status, latency, provider/model, token, and cost fields;
- screenshots and field verification results after browser execution;
- action logs, background jobs, LLM usage summaries, and agent reviews;
- copyable debug reports that include source evidence without copying raw suggested values.

## Quick Start

The fastest demo path is Docker:

```powershell
docker compose up --build -d
python scripts/seed_demo.py
```

Open `http://localhost:5173`.

Stop the demo:

```powershell
docker compose down
```

## Manual Local Setup

Backend:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m playwright install chromium
uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

Backend health:

```text
http://localhost:8000/health
```

## Docker Details

The Docker stack exposes:

- backend: `http://localhost:8000`
- frontend: `http://localhost:5173`

Seed demo data in another terminal:

```powershell
python scripts/seed_demo.py
```

The seed script creates `Demo Applicant` through the running API and does not require LLM credentials.

## Optional LLM Providers

Copy `.env.example` to `.env` or set variables in PowerShell before starting the backend:

```powershell
$env:LLM_PROVIDER="openai"
$env:OPENAI_API_KEY="your-key"
$env:OPENAI_MODEL="gpt-4.1-mini"
```

Supported provider settings are documented in `.env.example`. If a selected provider is unavailable, the app can continue in rules mode.

## Optional Metrics Sidecar

The Go metrics sidecar is not part of the default Docker demo. It remains optional for local experiments.

```powershell
cd sidecars/metrics-go
go run .
```

Then point the backend at it:

```powershell
$env:METRICS_SIDECAR_URL="http://localhost:9100"
```

See [docs/go-metrics-sidecar.md](docs/go-metrics-sidecar.md).

## Demo Walkthrough

Use [docs/demo-script.md](docs/demo-script.md) for a 3 to 5 minute reviewer demo.

Short version:

1. Start Docker compose.
2. Seed `Demo Applicant`.
3. Open Profiles and Workflows.
4. Create a form-fill run.
5. Review mappings before execution.
6. Inspect screenshot and verification evidence.
7. Stop at final submit approval.
8. Show Evaluation for repeatable benchmark evidence.

Security questionnaire path:

1. Create a Security Questionnaire Workflow run with the Docker demo URL.
2. Generate mappings in rules mode.
3. Open Review Mapping and inspect answers suggested from `mock-security-policy.md`.
4. Confirm only after reviewing the source evidence.

Vendor onboarding path:

1. Create a Vendor Onboarding Workflow run with the Docker demo URL.
2. Generate mappings in rules mode.
3. Review safe contact mappings and leave unsupported vendor-specific fields for manual review.
4. Confirm mappings, fill, verify, and stop before final submit approval.

## Latest Local Verification

Last checked on this branch:

```text
backend:  python -m pytest       -> 408 passed, 1 warning
frontend: npm test               -> 190 passed
frontend: npm run build          -> passed
```

## Test Commands

Backend:

```powershell
cd backend
python -m pytest
```

Frontend:

```powershell
cd frontend
npm test
npm run build
```

Docker package:

```powershell
docker compose build
```

CI runs backend tests and frontend tests/build through `.github/workflows/ci.yml`.

## Current Boundaries

This repository is intended to show a review-first agent architecture: workflow templates, policy gates, approval center, profile memory, source-backed retrieval, trace evidence, evaluation runs, and a runnable local demo. It does not claim production deployment, production authentication, cloud hosting, broad scraping, or CAPTCHA bypass.

## Resume Bullets

- Built a full-stack AI browser workflow assistant with FastAPI, React, Playwright, SQLite, optional LLM providers, reviewed memory, policy gates, trace observability, and benchmark evaluation.
- Implemented a review-first security questionnaire workflow that suggests answers from local policy evidence, shows source metadata, blocks sensitive fields, refuses unsupported answers, and stops before final submission.
- Designed an evaluation workbench comparing rules, LLM, and memory-assisted behavior across local fixtures with failure taxonomy, regression tracking, source evidence coverage, refusal metrics, latency, and cost signals.
