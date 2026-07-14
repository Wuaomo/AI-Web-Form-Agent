# AI Engineer Alignment Roadmap

## Target Positioning

Upgrade AI Web Form Agent from a form-filling demo into a full-stack browser workflow assistant with:

- Browser automation workflows
- Retrieval-augmented memory
- Human review and approval gates
- Evaluation benchmarks
- Trace-based observability
- Reproducible AI workflow experiments

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
6. Domain Workflow Templates
7. Retrieval Quality and Memory Governance
8. Agent Reliability Benchmark Suite

## Current Implementation Snapshot

- Phase 7C memory management: reviewed workflow memory can be listed and
  deleted through admin endpoints, and the React console has a Memory page for
  source, profile key, stale status, and deletion.
- Phase 8C browser replay benchmark: `full_workflow` benchmark mode opens local
  HTML fixtures in Playwright, maps profile values, fills the DOM, reads values
  back, and reports verification pass evidence without requiring LLM API keys.

## Product Story

The project should be presented as a review-first browser workflow assistant. Form filling remains the first concrete workflow, but the broader system should show how an AI assistant can read pages, extract information, use memory, take reviewed actions, and prove improvement through evaluation.

## Non-Goals

- No automatic final submission.
- No CAPTCHA solving.
- No login bypass.
- No general-purpose uncontrolled browser agent.
- No fine-tuning or model editing until the core system is credible.

