# Phase 4: Agent Observability

## Goal

Make every workflow debuggable through traces, tool calls, screenshots, and failure reports.

## Why

Modern AI Engineer roles increasingly expect evaluation plus observability, especially for agents.

## Scope

Improve Task Detail and Evaluation failure drilldown.

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
- failed fields
- LLM usage
- recent tool calls
- screenshots
- recommended next action

## Acceptance Criteria

- Task Detail shows trace timeline clearly.
- Benchmark failures can be traced to evidence.
- Debug report avoids sensitive raw values.
- Trace data helps explain both model and system failures.

## Demo Story

Open a failed benchmark case, inspect trace evidence, explain the root cause, apply a memory fix, and rerun evaluation.

