# AI Web Form Agent

[![CI](https://github.com/Wuaomo/AI-Web-Form-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Wuaomo/AI-Web-Form-Agent/actions/workflows/ci.yml)

A review-first AI browser workflow assistant built with FastAPI, React, Playwright, SQLite, and LangGraph. It extracts web forms, proposes values from profile data and source evidence, lets users review them, fills approved values, and verifies the browser state. Final submission requires separate approval.

The primary demo is a **Security Questionnaire Assistant**. The local rules-based demo works without LLM API keys; optional providers support model-assisted field mapping.

## What You Can Do

| Workflow | Current behavior |
| --- | --- |
| Security Questionnaire | Extract questions, suggest answers from local policy documents or reviewed memory, inspect evidence, review, fill, and verify. |
| Vendor Onboarding | Reuse profile data through the same review and approved-fill workflow. |
| Generic Form Fill | Map profile data to fields, correct suggestions, fill approved values, and read them back. |
| Web Data Extraction | Extract page headings, text blocks, links, tables, and forms with screenshot evidence. |
| Job Research Summary | Produce a deterministic, rules-based summary from extracted page content. |

Data Entry and Job Application templates are registered but disabled.

## Quick Start

Prerequisites: Docker with Compose, plus Python on the host to run the demo seed script.

Run from the repository root in PowerShell. Create the local environment file if it does not exist; API keys can stay empty:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
```

Once the backend is ready at [http://localhost:8000/health](http://localhost:8000/health), seed a demo profile:

```powershell
python scripts/seed_demo.py
```

Open [http://localhost:5173](http://localhost:5173).

1. Select the **Demo Applicant** profile and create a **Security Questionnaire** run.
2. Use `file:///app/examples/security-questionnaire.html` as the target URL.
3. Run the no-key preparation flow and inspect suggested answers and their sources.
4. Approve, edit, or reject values in Review Mapping, then confirm the reviewed mappings.
5. Fill the approved values and inspect DOM verification results and screenshots.
6. Stop before submission, or explicitly approve the final submit action.

For Vendor Onboarding, use `file:///app/examples/vendor-onboarding.html`. For Generic Form Fill, use `file:///app/examples/llm-registration.html`.

Docker URLs must use container paths such as `file:///app/examples/...`, rather than Windows host paths. Outside Docker, use a file URL pointing to the fixture on the backend machine.

Stop the demo with `docker compose down`. The current Compose configuration does not mount a database volume; export any state you need before recreating containers.

## Local Development

Start the backend:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m playwright install chromium
uvicorn app.main:app --reload
```

In another terminal, start the frontend:

```powershell
cd frontend
npm ci
npm run dev
```

The frontend runs at [http://localhost:5173](http://localhost:5173), and the API at [http://localhost:8000](http://localhost:8000).

For optional provider configuration, see [.env.example](.env.example). Docker Compose passes the root `.env` file to the backend. For manual startup, export the variables in your shell or start Uvicorn with `--env-file ../.env` from `backend/`. Keep keys out of version control. Rules mode remains available without a provider.

## Architecture

```text
React UI
  -> FastAPI APIs
    -> Agent planner and LangGraph workflow orchestration
    -> Typed tool runtime and action-level governance
    -> Proposal review and approval gates
    -> Playwright browser execution
    -> DOM verification, screenshots, and traces

Supporting services:
  SQLite: runs, plans, tool calls, reviews, jobs, memory, and benchmarks
  Retrieval: reviewed memory and policy document sections
  Optional LLM client: model-assisted field mapping and structured planning
```

The deterministic planner prepares workflow-specific tool steps. An optional structured LLM planner is exposed through the backend; tool calls still pass through validation and governance. Reviewed browser writes use `POST /agent-runs/{run_id}/continue`.

Run Cockpit and Review Mapping show compact runtime state, proposals, evidence, and verification summaries. Detailed traces, action logs, usage/cost estimates, and debug reports support failure investigation.

SQLite stores runtime records and supports reconstruction at supported review pauses. The graph's default checkpointer is in memory; this is not a guarantee of recovery at every execution point or restoration of a browser session.

See [architecture notes](docs/architecture.md) for the module map. Some sections describe legacy paths; the implementation limits below define the scope of current claims.

## Knowledge and Memory

- Profiles provide reusable field values.
- Reviewed workflow memory stores reusable, non-sensitive mappings and answers, with stale indicators and deletion controls.
- Bundled policy documents and user-imported Markdown/TXT sources provide evidence for questionnaire suggestions.
- Retrieval currently uses lexical matching. It does not implement a full semantic or hybrid retrieval pipeline.

Suggestions include source references for human review. Missing evidence should result in an unsupported answer rather than an invented value.

## Safety and Implementation Limits

- Browser filling requires human review. Final submission requires separate explicit approval.
- Passwords, OTPs, payment data, CAPTCHA, and destructive actions are blocked; login and CAPTCHA barriers are not bypassed.
- Sensitive data and one-time consent values must not become reusable memory.
- Existing plans can pause and continue, but general observation-driven replanning is not implemented.
- Generic browser click/navigation proposals do not have a complete execution path. Current browser writes cover reviewed form filling and submission.
- MCP/OpenAPI adapters support configured, allowlisted read-only tools. External write execution is not supported.
- The LangChain answer-generation adapter is a placeholder. Existing LLM field mapping uses the project's provider client.
- Review agents are fixed-order rule-based checks, not autonomous collaborating LLM agents.
- DOM readback verifies field values. A submit click and screenshot do not establish that a remote system accepted or saved the submission.

This is a local workflow assistant and portfolio project. It does not provide production authentication, multi-user isolation, cloud browser fleets, or a guarantee of compatibility with arbitrary websites.

See the [safety model](docs/safety-model.md).

## Evaluation and Tests

The evaluation workbench uses local HTML fixtures and expected answers. It stores runs, supports comparison, and exports Markdown reports.

| Mode | What it measures |
| --- | --- |
| `rules` | Local extraction and deterministic mapping/suggestion quality. |
| `llm` / `rag_llm` | Provider-assisted mapping, with optional memory retrieval; requires provider configuration. |
| `runtime` | Governed extraction/mapping steps and synthetic governance probes. It does not execute browser filling or simulate process-restart recovery. |
| `full_workflow` | Local Playwright filling and field readback. It is distinct from a complete product workflow through user approval and remote submission. |

Runtime completion-derived verification flags and the current recovery metric should not be interpreted as browser readback or crash-recovery success rates. Local benchmark outcomes do not establish reliability on enterprise websites.

See the [benchmark fixtures](backend/benchmarks/README.md) and [illustrative report](docs/evaluation-report-sample.md). The sample report is not a measured production result.

Backend tests:

```powershell
cd backend
python -m pytest
```

Frontend tests and build:

```powershell
cd frontend
npm test
npm run build
```

[GitHub Actions](https://github.com/Wuaomo/AI-Web-Form-Agent/actions/workflows/ci.yml) runs backend tests and frontend tests/build on pushes and pull requests. The CI badge links to current results rather than a fixed test-count snapshot.

## Optional Metrics Sidecar

The Go sidecar aggregates operational events and is not included in the default Compose stack. The backend can run without it. See [setup and endpoints](docs/go-metrics-sidecar.md).
