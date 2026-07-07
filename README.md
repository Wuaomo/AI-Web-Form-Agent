# Review-first AI Workflow Automation

AI Web Form Agent is a local browser automation app that analyzes web forms, maps reusable profile data to fields, fills the page in Chromium, and pauses before final submission.

## What It Is

This project demonstrates safe, inspectable workflow automation for web forms. It combines a FastAPI backend, SQLite persistence, Playwright browser execution, and a React/Vite frontend.

The default demo runs without LLM API keys. Optional providers can assist semantic mapping, but deterministic rules remain available.

## Why It Matters

Browser agents are risky when they submit forms invisibly. This app keeps the user in the loop with mapping review, approval gates, screenshots, action logs, traces, and local benchmark evidence.

## Core Workflow

```text
Create Profile
  -> Create Run
  -> Analyze Form
  -> Generate Mapping
  -> Review Mapping
  -> Confirm Mapping
  -> Fill Form
  -> Verify Fields
  -> Wait for Submit Approval
```

## Supported Templates

- Form Fill Workflow: enabled for the local demo.
- Web Data Extraction Workflow: registered but disabled.
- Data Entry Workflow: registered but disabled.
- Job Application Workflow: registered but disabled.

## Architecture

```text
React UI
  -> FastAPI API
    -> SQLite profiles, tasks, jobs, approvals, traces
    -> Form extraction and field mapping services
    -> Policy and approval gates
    -> Playwright browser execution
    -> Benchmark runner and reports
```

See [docs/architecture.md](docs/architecture.md) for the module map, workflow loop, trace model, and evaluation model.

## Safety Model

- Final submit always waits for user approval.
- Passwords, OTPs, payment data, CAPTCHA, and destructive actions are blocked.
- Low-confidence mappings require review.
- One-time or sensitive values are not saved as reusable profile memory.

See [docs/safety-model.md](docs/safety-model.md).

## Evaluation

The benchmark suite uses local HTML fixtures and expected JSON answers to track extraction quality, mapping accuracy, required-field coverage, action rejection, login-gate handling, and regression details.

See [docs/evaluation-report-sample.md](docs/evaluation-report-sample.md) and [backend/benchmarks/README.md](backend/benchmarks/README.md).

## Local Setup

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

## Docker Demo

Start the demo from the repository root:

```powershell
docker compose up --build
```

The stack exposes:

- backend: `http://localhost:8000`
- frontend: `http://localhost:5173`

Seed demo data in another terminal:

```powershell
python scripts/seed_demo.py
```

The seed script creates `Demo Applicant` through the running API and does not require LLM credentials.

Stop the demo:

```powershell
docker compose down
```

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

## Portfolio Notes

This repository is intended to show a review-first agent architecture: workflow templates, policy gates, approval center, profile memory, trace evidence, evaluation runs, and a runnable local demo. It does not claim production deployment, production authentication, cloud hosting, or CAPTCHA bypass.
