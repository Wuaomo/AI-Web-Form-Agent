# LLM Workflow Automation Harness Requirements

## 1. Project Vision

AI Web Form Agent will evolve from a review-first form automation project into a
review-first LLM workflow automation harness.

The system should demonstrate that an AI-assisted workflow can be:

- schedulable: long-running browser and LLM work is handled by background jobs;
- recoverable: failed workflows can resume from stable checkpoints;
- observable: LLM latency, token usage, cache behavior, fallback, and cost are measurable;
- verifiable: browser execution is checked after actions are performed;
- governable: benchmark regression, stress testing, safety review, and agent review are auditable.

The long-term goal is not to build a generic autonomous browser agent. The goal
is to build a controlled workflow infrastructure project that shows practical
AI engineering, reliability engineering, and benchmark-driven governance.

## 2. Target Positioning

Current positioning:

```text
Review-first browser automation system for safe web form filling.
```

Target positioning:

```text
Review-first LLM workflow automation harness with checkpoint recovery,
job scheduling, inference observability, benchmark governance, and controlled
agent review.
```

This direction aligns the project with AI infrastructure and systems
engineering roles that value scheduling, reliability, inference performance,
benchmarking, and engineering governance.

## 3. Non-Goals

The project must not expand into unsafe or unfocused automation.

Out of scope:

- generic free-form browser control;
- CAPTCHA solving or anti-bot bypass;
- automatic final submission;
- payment, purchase, delete, or destructive action automation;
- storing passwords, OTPs, payment card values, or one-time consent values;
- rewriting the main backend in Go;
- building an LLM training framework;
- allowing agents to directly control the browser.

## 4. Current Foundation

The current system already includes:

- FastAPI backend;
- React/Vite frontend;
- SQLite persistence through SQLAlchemy;
- Playwright browser execution;
- profile management;
- task creation;
- dynamic form extraction;
- rule-based and optional LLM-assisted mapping;
- mapping cache and user override memory;
- review-first mapping confirmation;
- screenshots and action logs;
- benchmark cases and persisted benchmark runs;
- final-submit approval boundary.

The future plan should reuse this foundation rather than replacing it.

## 5. Long-Term Architecture

Target architecture:

```text
React UI
  -> FastAPI API
    -> Workflow Reliability Layer
    -> Async Job Scheduler
    -> LLM Mapping and Observability
    -> Browser Execution Worker
    -> Execution Verification
    -> Benchmark Regression Harness
    -> Controlled Agent Review
    -> SQLite/PostgreSQL Persistence

Optional:
  -> Go Metrics Sidecar
```

FastAPI remains the main backend. The optional Go sidecar is only for
operational metrics and should not own task state, browser automation, or LLM
mapping.

## 6. Development Roadmap

### Phase 1: Workflow Reliability Foundation

Purpose:

Make existing workflows recoverable and diagnosable.

Core requirements:

- Add workflow stage constants for analysis, mapping, review, fill, approval,
  and submission.
- Add structured failure reasons.
- Add checkpoint persistence for successful and failed stages.
- Make analyze, mapping, and fill stages checkpoint-aware.
- Expose checkpoint history for debugging.
- Extend debug reports with latest success/failure checkpoints.
- Add recovery-aware UI labels.

Expected outcome:

```text
When a workflow fails, the system can explain where it failed, why it failed,
whether it can be retried, and which completed stages can be reused.
```

Primary value:

- reliability;
- checkpointing;
- fault diagnosis;
- safe retry behavior.

### Phase 2: Async Job Scheduler

Purpose:

Move long-running LLM and Playwright work out of synchronous API requests.

Core requirements:

- Add job, job attempt, and worker heartbeat models.
- Add a database-backed queue service.
- Add worker execution logic.
- Enqueue analyze, mapping, fill, and benchmark jobs.
- Track job status, attempts, retries, lock ownership, and error reasons.
- Add job status APIs and frontend status display.

Expected outcome:

```text
Users can create tasks quickly while background workers process browser and LLM
work according to retry and resource rules.
```

Primary value:

- scheduling;
- worker orchestration;
- retry handling;
- resource-aware execution.

### Phase 3: LLM Inference Observability

Purpose:

Make semantic mapping measurable as an inference pipeline.

Core requirements:

- Track LLM request latency.
- Track prompt tokens, completion tokens, total tokens, prompt cache hit tokens,
  and cache hit rate.
- Track provider errors and fallback usage.
- Track app-level mapping cache and user override cache effectiveness.
- Add estimated cost calculation.
- Add task-level and provider-level LLM usage summaries.
- Display compact LLM usage information in Task Detail.

Expected outcome:

```text
Every LLM mapping run can be explained in terms of latency, token usage, cache
behavior, fallback behavior, and estimated cost.
```

Primary value:

- inference observability;
- performance profiling;
- cost awareness;
- cache optimization.

### Phase 4: Benchmark Regression Harness

Purpose:

Turn benchmarks into an engineering governance tool.

Core requirements:

- Extend benchmark runs with duration, baseline, regression count, and
  improvement count.
- Add summary metric comparison against a baseline run.
- Add benchmark modes for standard, cache-cold, cache-warm, and stress-style
  runs.
- Add quality metrics and workflow performance metrics.
- Generate copyable Markdown benchmark reports.
- Update the Benchmarks page to show baseline comparison and regression status.

Expected outcome:

```text
Each change to extraction, mapping, scheduling, or cache behavior can be judged
against quality and performance baselines.
```

Primary value:

- automated benchmarking;
- regression governance;
- stress testing;
- measurable reliability.

### Phase 5: Execution Verification

Purpose:

Prove that browser execution actually wrote expected values into the page.

Core requirements:

- Add field verification result persistence.
- Read actual values from the browser after fill.
- Compare expected and actual values without storing raw sensitive values.
- Persist verified, failed, skipped, and partial verification outcomes.
- Add verification APIs.
- Display verification summary in Task Detail.
- Include verification outcomes in debug reports.

Expected outcome:

```text
The system can distinguish between "Playwright command was issued" and "the
page actually contains the expected value."
```

Primary value:

- execution correctness;
- browser automation reliability;
- post-action validation;
- audit evidence.

### Phase 6: Controlled Multi-Agent Review

Purpose:

Use specialized AI review roles only where they improve safety and quality.

Core requirements:

- Add stable agent role and decision constants.
- Add persistent agent review records.
- Add deterministic coordinator logic.
- Implement Mapping Critic Agent.
- Implement Safety Review Agent.
- Implement Execution Verification Agent.
- Validate all agent outputs as strict JSON.
- Expose agent reviews in UI without showing raw prompts.

Expected outcome:

```text
Agents review mappings, safety risks, and verification results, but they never
directly operate the browser or approve final submission.
```

Primary value:

- controlled multi-agent architecture;
- AI-assisted review;
- safety governance;
- auditable agent decisions.

### Phase 7: Optional Go Metrics Sidecar

Purpose:

Demonstrate backend infrastructure awareness through a small optional Go
service.

Core requirements:

- Build a Go sidecar with `/health`, `/events`, and `/metrics`.
- Accept job and checkpoint events from FastAPI.
- Aggregate queue depth, worker heartbeat, job counts, retry counts, and
  latency metrics.
- Keep the Python backend functional when the sidecar is unavailable.
- Document local setup.

Expected outcome:

```text
The Go sidecar provides operational metrics without taking ownership of core
workflow state.
```

Primary value:

- backend infrastructure;
- operational metrics;
- Go experience;
- low-risk service decomposition.

## 7. Recommended Execution Order

The recommended order is:

```text
1. Workflow Reliability Foundation
2. Async Job Scheduler
3. LLM Inference Observability
4. Benchmark Regression Harness
5. Execution Verification
6. Controlled Multi-Agent Review
7. Optional Go Metrics Sidecar
```

Rationale:

- Reliability must come before scheduling.
- Scheduling creates the foundation for stress testing and worker metrics.
- LLM observability should be added before using cache and latency numbers in
  benchmark reports.
- Execution verification should come after the workflow is recoverable and
  measurable.
- Multi-agent review should only be added after deterministic evidence exists.
- Go sidecar is optional and should not distract from core product quality.

## 8. Cross-Phase Engineering Rules

All phases must follow these rules:

- Write tests before changing behavior.
- Keep backend behavior covered by pytest.
- Keep frontend presentation helpers covered by Node tests.
- Keep final submission behind explicit user approval.
- Keep sensitive values out of logs, debug reports, and metrics dashboards.
- Use English UI text and English code comments.
- Prefer small services with clear interfaces over large route-level logic.
- Do not introduce unrelated product scope.

## 9. Global Acceptance Criteria

The long-term project is successful when:

- workflows can be queued, retried, and recovered;
- LLM usage is measurable by latency, tokens, cache, fallback, and cost;
- benchmark runs can detect quality and performance regressions;
- browser execution is verified after actions;
- agent review is controlled and auditable;
- safety boundaries remain clear;
- a reviewer can understand the system from README, docs, benchmark reports,
  and UI evidence.

## 10. Resume-Oriented Outcome

After these phases, the project can be described as:

```text
Built a review-first LLM workflow automation harness with checkpoint-based
recovery, async job scheduling, LLM inference observability, automated
benchmark regression metrics, post-execution verification, and controlled
multi-agent review.
```

This communicates:

- AI workflow engineering;
- infrastructure reliability;
- inference performance awareness;
- benchmark-driven governance;
- safety-conscious agent design.

