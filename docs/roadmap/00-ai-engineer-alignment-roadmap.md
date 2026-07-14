# AI Engineer Alignment Roadmap

## Target Positioning

Upgrade AI Web Form Agent from a form-filling demo into a full-stack AI
browser workflow assistant with:

- Browser automation workflows
- Retrieval-backed reviewed memory
- Human review and approval gates
- Evaluation benchmarks
- Trace-based observability
- Reproducible AI workflow experiments

The project should not be repositioned as a chatbot. The stronger story is:

```text
read a browser page
  -> extract required information
  -> retrieve reviewed knowledge when available
  -> propose safe actions with evidence
  -> require human review
  -> execute in the browser
  -> verify and evaluate the result
```

## Target AI Engineer Skills

This roadmap is designed to demonstrate:

- LLM workflow engineering
- RAG and memory systems
- Agent tool use and planning
- Evaluation dataset design
- Failure analysis and observability
- Full-stack AI product development

## Phases

1. Browser Workflow Assistant
2. Retrieval Memory Layer
3. Evaluation Workbench
4. Agent Observability
5. Portfolio Packaging

## Current Implementation Snapshot

This branch already includes meaningful work from the earlier roadmap. Keep it
as evidence instead of replacing it with the newer JD-aligned demo direction.

Completed or mostly completed:

- Phase 1 base workflows: form fill, web data extraction, and job/research
  summary workflows exist in backend/frontend paths.
- Phase 1 security questionnaire workflow: enabled workflow template, planner
  path, local demo fixture, and review-first form execution path exist.
- Phase 2 mapping memory baseline: confirmed mappings can be saved as workflow
  memory, skipped for sensitive/one-time fields, and reused as retrieval
  fallback for future field mapping.
- Phase 2 source-backed questionnaire baseline: security questionnaire mappings
  can suggest answers from local mock policy docs, persist source evidence to the
  mapping checkpoint, and show that evidence in Review Mapping.
- Phase 3 evaluation baseline: local benchmark fixtures, rules/LLM/RAG-style
  modes, memory mode, regression comparison, and Markdown reports exist.
- Phase 3 questionnaire evaluation: source-backed answer accuracy, source
  evidence coverage, unsupported refusal, sensitive skip, and completion metrics
  are measured in the benchmark suite.
- Phase 4 observability baseline: action traces, workflow spans, screenshots,
  verification evidence, LLM usage, and debug reports exist.
- Phase 5 packaging baseline: README, architecture, safety model, demo script,
  benchmark docs, and test commands exist.

Still missing from the revised direction:

- memory governance beyond confirmed form-field mappings;
- portfolio assets that show the questionnaire workflow.

## Post-Portfolio Extensions

6. Domain Workflow Templates
7. Retrieval Quality and Memory Governance
8. Agent Reliability Benchmark Suite

## Product Story

The project should be presented as a review-first browser workflow assistant.
Form filling remains the first concrete workflow, but the broader system should
show how an AI assistant can read pages, extract information, use reviewed
memory, take reviewed browser actions, and prove improvement through
evaluation.

The JD-aligned demo path is a security/compliance-style questionnaire workflow:

```text
security questionnaire page
  -> extract questions and fields
  -> suggest answers from reviewed memory or mock policy docs
  -> show source evidence
  -> block sensitive or unsupported answers
  -> fill only after human review
  -> stop before final submission
```

## Non-Goals

- No automatic final submission.
- No CAPTCHA solving.
- No login bypass.
- No general-purpose uncontrolled browser agent.
- No fine-tuning or model editing until the core system is credible.
- No chatbot UI unless it directly supports a reviewed browser workflow.

