# Phase 3: Evaluation Workbench

## Goal

Turn Evaluation Center into proof that the AI workflow improves and remains
safe.

## Why

AI Engineer roles care about measurable behavior, regression detection, and
benchmark design. The project should measure retrieval, refusal, safety gates,
and end-to-end workflow success, not only mapping accuracy.

## Scope

Evaluate workflow quality across modes.

## Current Status

Completed:

- Local benchmark fixtures and expected JSON outputs exist.
- Evaluation Center can run rules, LLM, and RAG-style LLM modes.
- Memory mode and stress mode are represented in benchmark run details.
- Benchmark reports include summary metrics, failures, top failure reasons, and
  regression/improvement comparison.
- Markdown report export is implemented.

Not complete yet:

- full workflow benchmark mode;
- source evidence coverage metric;
- unsupported-answer refusal rate;
- sensitive-field block rate beyond existing form safety cases;
- approval-gate coverage metric;
- browser execution success and verification pass metrics as first-class
  workflow reliability metrics.

## Evaluation Modes

- rules only
- rules + memory
- LLM only
- LLM + memory
- optional embedding retrieval baseline

## Metrics

- extraction recall
- extraction precision
- mapping accuracy
- required field coverage
- wrong mapping count
- memory hit rate
- source evidence coverage
- unsupported-answer refusal rate
- sensitive-field block rate
- approval-gate coverage
- browser execution success rate
- verification pass rate
- LLM fallback count
- latency
- estimated token cost
- regression count

## Failure Taxonomy

Use stable failure reasons:

- field_not_extracted
- wrong_profile_key
- missing_required_value
- action_field_should_skip
- option_value_mismatch
- low_confidence_mapping
- unexpected_extra_mapping
- unsupported_answer_should_refuse
- sensitive_value_should_block
- missing_source_evidence
- approval_gate_missing
- browser_verification_failed

## Reports

Add Markdown export:

```text
Run ID
Mode
Score
Metric table
Top failures
Regression summary
Recommended fixes
```

## Acceptance Criteria

- Evaluation Center compares at least two modes.
- Memory-enabled mode reports memory hit rate.
- Reports include refusal rate, safety pass rate, and source evidence coverage.
- Failure cases show reason and evidence.
- Benchmark report can be copied or downloaded.
- Existing tests pass without LLM API keys.

## Demo Story

Run rules-only, then memory-enabled evaluation, and show improved mapping or
answer quality without reducing safety pass rate.

