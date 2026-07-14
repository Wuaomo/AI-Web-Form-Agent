# Phase 8: Agent Reliability Benchmark Suite

## Goal

Measure whether the workflow can execute in a real browser and verify its
results, not only whether mapping labels look correct.

## Current Status

Implemented in this branch:

- `full_workflow` benchmark mode now runs locally without LLM API keys.
- The benchmark opens local HTML fixtures in Playwright.
- Rules-based mapping values are filled into the DOM.
- Filled values are read back through the existing browser verification helper.
- Summary metrics include workflow success, safety pass, verification pass, and
  failure rate signals.
- The Evaluation Center can run `full_workflow` mode.

Still not included:

- Real submit replay. The safety boundary still stops before final submission.
- Approval-gate coverage metrics.
- Recommended fixes generated from benchmark failure reasons.

