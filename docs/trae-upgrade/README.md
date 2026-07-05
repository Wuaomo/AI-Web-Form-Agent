# Trae Upgrade Plan Index

## Purpose

This folder contains the phased upgrade plan for turning the current AI Web Form Agent into a review-first AI workflow automation platform.

Use these files one phase at a time. Do not ask Trae to implement all phases in one prompt.

## Execution Order

1. `00-product-positioning-and-target-architecture.md`
   - Product positioning and target architecture.
   - Documentation only.

2. `01-workflow-core-state-machine.md`
   - Adds workflow type/status and transition validation.
   - Preserves existing task flow.

3. `02-workflow-run-trace-system.md`
   - Adds trace spans for workflow observability.
   - Adds trace API and frontend trace card.

4. `03-policy-engine-and-approval-gates.md`
   - Adds deterministic policy decisions.
   - Adds persisted approval requests.

5. `04-workflow-templates.md`
   - Adds workflow template definitions and template API.
   - Keeps only `form_fill` enabled.

6. `05-planner-and-tool-protocol.md`
   - Adds deterministic planner and tool registry.
   - Stores a workflow plan on each task.

7. `06-rag-workflow-memory.md`
   - Adds SQLite-backed workflow memory.
   - Adds retrieval examples for LLM mapping.

8. `07-evaluation-center.md`
   - Extends benchmarks into evaluation runs.
   - Adds mode comparison, baseline deltas, and richer reports.

9. `08-frontend-workflow-console.md`
   - Reorganizes UI around runs, workflows, approvals, traces, and evaluation.

10. `09-deployment-ci-demo-package.md`
    - Adds Docker, CI, demo data, architecture docs, and README polish.

## Recommended Trae Workflow

For each phase:

1. Paste only that phase file into Trae.
2. Tell Trae to implement exactly that phase.
3. Run the tests listed in that phase.
4. Review the diff before moving to the next phase.
5. Commit after each phase.

## Do Not Skip First

Do these first:

- Phase 01: workflow state machine
- Phase 02: trace system
- Phase 03: policy and approval gates

These three phases create the professional workflow foundation. Later phases depend on their vocabulary and APIs.

## Safety Rule

Do not weaken existing safety boundaries:

- no CAPTCHA solving
- no anti-bot bypass
- no payment automation
- no password/OTP storage
- no final submission without explicit approval

## Portfolio Target

After all phases, the project should be described as:

> A review-first AI workflow automation platform for structured web tasks, with planner-controlled tool use, human approval gates, policy enforcement, Playwright execution, trace observability, workflow memory, and evaluation-driven improvement.
