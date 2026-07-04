# AI Web Form Agent

A review-first browser automation system that analyzes web forms, maps reusable
profile data to form fields, fills the page in a real browser, and pauses before
final submission.

The project is designed as a portfolio-grade example of safe browser
automation: dynamic form discovery, user review, execution evidence, evaluation
benchmarks, and clear guardrails around sensitive actions.

## Highlights

- **Dynamic form discovery**: extracts inputs, textareas, selects, checkboxes,
  radio controls, labels, placeholders, ARIA hints, options, and required
  fields from arbitrary pages.
- **Profile-based filling**: stores reusable profile data and maps it to
  discovered form fields through deterministic rules and optional
  provider-assisted semantic mapping.
- **Human review loop**: routes extracted fields through a Review Mapping screen
  so the user can inspect, correct, and confirm values before browser execution.
- **Safe browser execution**: uses Playwright to fill forms in Chromium while
  keeping final submission behind explicit approval.
- **Profile memory**: writes reviewed reusable values back to built-in or custom
  profile fields when safe, while skipping one-time or sensitive fields.
- **Observability**: records task status, action logs, screenshots, usage
  metrics, and detailed admin traces.
- **Evaluation suite**: runs local benchmark forms with persisted results and
  case-level failure details.

## Current Product Flow

```text
Create Profile
  -> Create Task
  -> Analyze Form
  -> Generate Field Mapping
  -> Review Mapping
  -> Confirm Mapping
  -> Fill Form
  -> Wait for Approval
  -> Submit only if the user approves
```

## Core Results

This repository already includes:

- A FastAPI backend with SQLite persistence.
- A React/Vite frontend with Dashboard, Profiles, Create Task, Task Detail,
  Review Mapping, and Benchmarks pages.
- A Playwright execution layer for real browser interaction.
- Extracted form field persistence and reusable task state.
- Rule-based and optional provider-assisted mapping.
- Mapping caches, user override memory, and form analysis cache.
- Screenshots and user-facing action logs for task evidence.
- Admin action traces for debugging browser execution.
- Local benchmark cases and persisted benchmark run history.
- Backend pytest coverage and frontend Node test coverage.

## Architecture

```text
React UI
  -> FastAPI API
    -> Task/Profile persistence (SQLite)
    -> Form extraction service
    -> Field mapping service
    -> Browser execution service (Playwright)
    -> Benchmark runner
```

The mapping layer proposes field-to-profile matches. The backend validates and
persists reviewed mappings. Playwright only executes mapped field values after
the user has confirmed them.

## Tech Stack

- Backend: Python, FastAPI, SQLAlchemy, SQLite
- Browser automation: Playwright
- Frontend: React, Vite
- Optional semantic mapping providers: OpenAI, Gemini, DeepSeek
- Testing: pytest, Node test runner

## Project Structure

```text
backend/                 FastAPI app, services, tests, examples
backend/app/routers/      API routes
backend/app/services/     extraction, mapping, browser, cache, benchmark logic
backend/benchmarks/       local benchmark forms and expected answers
frontend/                React/Vite UI
frontend/src/pages/       application pages
docs/                    architecture and demo documentation
AGENT_RULES.md           project constraints and safety boundaries
TASKS.md                 development roadmap
```

## Local Setup

Use two PowerShell terminals: one for the backend API and one for the frontend.

Backend setup:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m playwright install chromium
uvicorn app.main:app --reload
```

The API runs at:

```text
http://localhost:8000
```

Health check:

```text
http://localhost:8000/health
```

Frontend setup:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL printed in the terminal, usually:

```text
http://localhost:5173
```

## Optional Provider Setup

The system can run with deterministic rules only. To enable semantic mapping,
configure one provider before starting the backend:

```powershell
# DeepSeek
$env:LLM_PROVIDER="deepseek"
$env:DEEPSEEK_API_KEY="your-key"
$env:DEEPSEEK_MODEL="deepseek-v4-flash"

# OpenAI
$env:LLM_PROVIDER="openai"
$env:OPENAI_API_KEY="your-key"
$env:OPENAI_MODEL="gpt-4.1-mini"

# Gemini
$env:LLM_PROVIDER="gemini"
$env:GEMINI_API_KEY="your-key"
$env:GEMINI_MODEL="gemini-2.5-flash"
```

If a selected provider is unavailable, the API returns a setup hint and the
application can continue in rules mode.

## Optional Go Metrics Sidecar

An optional Go sidecar can aggregate task/job metrics and worker heartbeats in
memory. The FastAPI backend remains the source of truth; the sidecar only
receives event notifications and exposes read-only `/health` and `/metrics`
endpoints. The backend works normally without the sidecar.

Start the sidecar:

```powershell
cd sidecars/metrics-go
go run .
```

Enable event emission from the backend:

```powershell
$env:METRICS_SIDECAR_URL="http://localhost:9100"
```

Available metrics include total events, jobs by status, jobs by type, average
duration by job type, worker last seen, and retry count. See
[docs/go-metrics-sidecar.md](docs/go-metrics-sidecar.md) for full details.

## Demo Walkthrough

1. Create a profile with reusable contact and education information.
2. Create a task with a target form URL.
3. Analyze the page to extract form fields.
4. Generate field mappings.
5. Review and correct mapped values.
6. Confirm mappings and inspect profile updates.
7. Fill the form in the browser.
8. Review the screenshot while the task is waiting for approval.
9. Submit only after explicit user confirmation.
10. Run benchmarks to inspect mapping quality and failure details.

## Safety Boundaries

- No final submission without user approval.
- No CAPTCHA solving or anti-bot bypassing.
- No payment, purchase, delete, or destructive action automation.
- No password, OTP, payment card, or one-time consent values are saved as
  reusable profile memory.
- Manual login support is user-controlled and does not bypass authentication.

## Evaluation

The benchmark suite is designed to make form understanding measurable. It uses
local HTML fixtures and expected mapping JSON to track:

- field extraction recall and precision
- profile-key mapping accuracy
- required-field coverage
- non-fillable/action-field rejection
- login-gate detection
- case-level failure reasons

This keeps improvements grounded in repeatable tests instead of one-off demos.

## Roadmap

The next improvements focus on reliability and presentation:

1. Expand benchmark cases for realistic form patterns.
2. Add rules/semantic mode selection to the benchmark UI.
3. Improve select, radio, and checkbox option matching.
4. Surface required and low-confidence fields more clearly in Review Mapping.
5. Add a task timeline and debug report to Task Detail.
6. Package the project with architecture, demo, and safety documentation.

