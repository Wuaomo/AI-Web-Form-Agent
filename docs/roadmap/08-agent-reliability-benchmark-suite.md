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

Not complete yet:

- full workflow benchmark mode;
- questionnaire answer benchmark cases;
- source evidence coverage;
- refusal and sensitive-field block metrics for answer suggestions;
- browser execution success and verification pass rate as report-level
  reliability metrics.

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
