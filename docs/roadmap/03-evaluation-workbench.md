# Phase 3: Evaluation Workbench

## Goal

Turn Evaluation Center into the proof that the agent improves.

## Why

AI Engineer roles care about measurable behavior, regression detection, and benchmark design.

## Scope

Evaluate mapping quality across modes.

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
- Failure cases show reason and evidence.
- Benchmark report can be copied or downloaded.
- Existing tests pass without LLM API keys.

## Demo Story

Run rules-only, then memory-enabled evaluation, and show improved mapping accuracy plus fewer failures.

