# Phase 4: Agent Observability

## Goal

Make every workflow explainable through traces, tool calls, screenshots, source
evidence, and failure reports.

## Why

Modern AI Engineer roles increasingly expect evaluation plus observability, especially for agents.

## Scope

Improve Task Detail and Evaluation failure drilldown. Avoid making
observability the main UI experience.

## Current Status

Completed:

- Task Detail shows screenshots, verification evidence, workflow trace spans,
  agent reviews, LLM usage, background jobs, and debug report copy action.
- Advanced/debug data is collapsed by default unless the run state needs it.
- Workflow spans persist provider/model/token/cost/latency fields.
- Action traces and admin trace endpoints exist.
- Debug reports include source-backed suggestion evidence from mapping
  checkpoints without copying raw suggested values.

Not complete yet:

- suggestion evidence trace for every mapping or questionnaire answer;
- direct links from benchmark failures to trace spans and screenshots;
- refusal/source explanations for questionnaire answers;
- dedicated source-evidence trace spans separate from mapping checkpoints.

## Features

### Tool Call Trace

For each tool/action, record:

- phase
- tool name
- input summary
- output summary
- status
- latency
- error message
- screenshot id if available

### Suggestion Evidence Trace

For each suggested mapping or answer, record:

- source type
- source id
- matched label, question, or policy snippet
- match reason
- policy decision
- approval status

### LLM Trace

For each LLM call, record:

- provider
- model
- prompt summary
- output summary
- latency
- token usage
- estimated cost
- cache hit data if available

### Failure Drilldown

From benchmark failure, link to:

- extracted field
- predicted mapping
- expected mapping
- trace span
- screenshot
- suggested fix

### Debug Report

Generate one report containing:

- task status
- workflow timeline
- suggestion evidence
- failed fields
- LLM usage
- recent tool calls
- screenshots
- recommended next action

## Acceptance Criteria

- Task Detail shows trace timeline clearly.
- Benchmark failures can be traced to evidence.
- Suggested answers explain their source or refusal reason.
- Debug report avoids sensitive raw values.
- Trace data helps explain both model and system failures.

## Demo Story

Open a failed benchmark case, inspect trace evidence, explain the root cause, apply a memory fix, and rerun evaluation.

