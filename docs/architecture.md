# Architecture

AI Web Form Agent is a review-first AI browser workflow assistant. It reads web pages, extracts fields or questionnaire items, retrieves profile data and source evidence, suggests answers, requires human review, fills approved values in a real browser, verifies the result, and stops before final submission so the user stays in control.

## Product Positioning

The project is a portfolio-grade example of safe browser automation, not a production form-submission service. The default demo runs locally without LLM API keys. Optional LLM providers can improve semantic field mapping, but deterministic rules remain the baseline path.

## System Diagram

```mermaid
flowchart TD
  Goal["User Goal"] --> AgentRun["AgentRun / Task Facade"]
  AgentRun --> Template["Workflow Template Hint"]
  Template --> Planner["Planner"]
  Planner --> Runtime["Governed Agent Runtime"]
  Runtime --> ToolRuntime["Tool Runtime"]
  ToolRuntime --> Policy["PolicyEngine (Action Decisions)"]
  Policy --> Approval["ApprovalGateService"]
  Approval --> Executor["Tool Executor"]
  Executor --> Browser["Playwright Browser (Approved Only)"]
  Executor --> LangChain["LangChain (Optional Suggestions)"]
  Executor --> Memory["Workflow Memory"]
  Browser --> Verify["Verification"]
  Verify --> Trace["Trace + Screenshots"]
  Trace --> Eval["Evaluation Center"]
  Runtime -.->|"interrupt"| ReviewGate["Review Queue"]
  Runtime -.->|"interrupt"| SubmitGate["Submit Approval"]
```

## Backend Modules

- `app/main.py` wires the FastAPI app, routers, CORS, database startup, and screenshot serving.
- `app/database.py` owns SQLite setup and lightweight schema migrations.
- `app/routers/*` expose profiles, tasks, workflows, approvals, jobs, traces, LLM usage, benchmarks, and admin trace endpoints.
- `app/routers/workflows.py` exposes governed runtime start/state/review helpers plus deprecated old security questionnaire compatibility endpoints.
- `app/services/form_extractor.py` reads form fields from real pages through Playwright.
- `app/services/field_mapper.py` maps extracted fields to profile values with deterministic logic and optional provider help.
- `app/services/policy_answer_retrieval.py` suggests security questionnaire answers from local policy fixtures with source evidence.
- `app/services/browser_executor.py` fills the browser and captures execution evidence.
- `app/services/policy_engine.py` and `approval_gate_service.py` classify blocked and review-required actions.
- `app/services/workflow_trace_service.py` records workflow spans, screenshots, and diagnostic metadata.
- `app/services/agent_runtime/` contains shared AgentRun schemas, tool runtime, governance, review queue helpers, compact persistence, and the governed graph. The legacy Security Questionnaire graph remains as a deprecated compatibility fallback.
- `app/services/benchmark_runner.py` and related benchmark services run local fixture evaluations across rules/memory/LLM/runtime modes.

## Frontend Pages

- Runs dashboard: recent workflow runs, backend health, and quick links.
- Workflow templates: available workflow types and approval policy summaries.
- Profiles: reusable applicant data used during workflow execution.
- Create run: starts a workflow from a URL and profile.
- Task detail: run status, Run Cockpit, actions, screenshots, verification, approval controls, and legacy compatibility state where needed.
- Review mapping: Review Queue summary plus user inspection and correction before browser execution, including source evidence and safety flags for questionnaire workflows.
- Approvals: pending review gates.
- Evaluation: benchmark execution and comparison history with rules/memory/LLM/runtime mode comparison.

## Compatibility Workflow Loop (Security Questionnaire)

The Security Questionnaire primary path uses the generic governed runtime and AgentRun APIs. The old `/workflows/{task_id}/start`, `/workflows/{task_id}`, and `/workflows/{task_id}/review` path is a deprecated compatibility fallback for older clients:

1. **Primary start**: Task Detail/Create Run/Page Intake call `/workflows/{task_id}/governed/start`.
2. **Primary review**: Source-backed answers become AgentRun Review Queue `answer` proposals with compact evidence.
3. **Primary browser write**: Approved/edited proposals continue through `/agent-runs/{run_id}/continue` and shared Tool Runtime gates.
4. **Primary submit**: Final submit still requires explicit approval through the AgentRun continue boundary.
5. **Compatibility start/get/review**: The old security graph remains available but does not create AgentRun/ToolRuntime/proposal state on start.
6. **Compatibility fill/verify**: Old graph fill/verify nodes are skeleton-only and are not browser-write execution or verification trust evidence.

## Policy And Approval Model

The enabled form-fill template always requires approval before final submit. Passwords, OTPs, payment data, and destructive actions are blocked rather than automated. Low-confidence mappings and other risky steps are routed through review gates.

## Trace Model

Workflow traces capture phases, statuses, inputs, outputs, provider metadata, latency, cost estimates, screenshots, and error details. Traces are used for debugging and reviewer evidence, not for bypassing user review.

## Evaluation Model

Benchmarks use local HTML fixtures and expected JSON answers. They measure:

- **Core Quality**: extraction recall/precision, mapping accuracy, required-field coverage.
- **Safety**: `safety_pass_rate`, sensitive-field skip rate, unsupported-answer refusal rate.
- **Verification**: `verification_pass_rate`, fill success rate, workflow success rate.
- **Evidence**: `source_evidence_coverage`, answer accuracy.
- **Performance**: average/p95 case duration, failure rate.

Benchmark modes include:
- `rules`: Deterministic rule-based mapping and suggestions.
- `llm`: Optional LLM-enhanced mapping.
- `rag_llm`: LLM with memory retrieval.
- `langchain_rag_optional`: Falls back to rules when LLM provider is unavailable.
- `runtime`: Evaluates the full LangGraph workflow with review gates.
- `full_workflow`: End-to-end browser fill and verification.

## Architectural Boundaries

### LangGraph
- **Role**: Workflow orchestration with durable state.
- **Boundary**: Does NOT make security decisions; only enforces interrupt points.
- **Pattern**: `interrupt_before=[REVIEW_GATE_NODE, SUBMIT_GATE_NODE]` ensures human review.

### LangChain
- **Role**: Optional suggestion enhancement via LLMs and retrieval.
- **Boundary**: Does NOT execute browser actions; only provides suggestions.
- **Pattern**: Falls back to rules mode when providers are unavailable.

### PolicyEngine
- **Role**: Authoritative safety decision maker.
- **Boundary**: Owns all security classifications (block/warn/safe).
- **Pattern**: Independent of orchestration layer.

### ApprovalGateService
- **Role**: Human-in-the-loop approval enforcement.
- **Boundary**: Prevents any execution without explicit approval.
- **Pattern**: Persisted approval history for audit trails.

### Playwright
- **Role**: Approved browser execution and verification.
- **Boundary**: Only fills user-approved values; never auto-submits.
- **Pattern**: Captures DOM verification evidence for review.
