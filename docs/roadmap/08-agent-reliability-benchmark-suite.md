# Phase 8: Agent Reliability Benchmark Suite

## Goal

Turn the project into a measurable AI workflow system with regression evidence,
not a demo that only works on one happy path.

## Why

For AI engineering interviews, the strongest proof is not that the app calls an
LLM. It is that the app measures correctness, refusal behavior, safety gates,
and end-to-end workflow success.

## Scope

Expand benchmarks from mapping quality into full workflow reliability.

## Current Status

Partially complete:

- Mapping/extraction benchmark suite exists.
- Regression comparison and Markdown reporting exist.
- Memory-enabled benchmark configuration exists.
- Local `full_workflow` benchmark mode now runs without LLM API keys.
- `full_workflow` opens local HTML fixtures in Playwright, maps fields, fills
  the DOM, and reads back browser verification results.
- Summary metrics include workflow success rate, safety pass rate, verification
  pass rate, and failure rate.
- Markdown reports include a Reliability Summary section.
- The Evaluation Center can run `full_workflow` mode.

Not complete yet:

- real submit replay;
- approval-gate coverage metrics;
- recommended-fix generation in reports.

## Benchmark Areas

- extraction quality
- mapping accuracy
- memory retrieval hit rate
- source evidence coverage
- unsupported-answer refusal rate
- sensitive-field block rate
- approval-gate coverage
- browser execution success rate
- verification pass rate
- regression count

## Reports

Reports should compare:

- rules only
- rules + reviewed memory
- LLM-assisted mapping
- LLM + reviewed memory

Each report should include:

- metric table
- top failures
- safety pass rate
- regression summary
- recommended fixes

## Acceptance Criteria

- A local benchmark run works without LLM API keys.
- Memory-enabled runs can be compared with rules-only runs.
- Safety regressions are visible.
- Reports are clear enough to include in the portfolio README.
