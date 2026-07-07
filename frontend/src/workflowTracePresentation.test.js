import assert from "node:assert/strict";
import test from "node:test";

import {
  buildTraceSummary,
  getVisibleTraceSpans,
  phaseLabel,
  shouldShowTraceExpansion,
  sortSpans,
  spanStatusLabel,
  summarizeSpan,
  traceJsonText,
} from "./workflowTracePresentation.js";

test("phaseLabel falls back to original value for unknown phases", () => {
  assert.equal(phaseLabel("custom_phase"), "custom_phase");
  assert.equal(phaseLabel("mapping"), "Mapping");
});

test("spanStatusLabel falls back to original value for unknown statuses", () => {
  assert.equal(spanStatusLabel("PAUSED"), "PAUSED");
  assert.equal(spanStatusLabel("SUCCESS"), "Success");
});

test("sortSpans orders rows chronologically by created_at then id", () => {
  const spans = [
    { id: 3, created_at: "2026-07-05T10:00:00Z" },
    { id: 1, created_at: "2026-07-05T09:00:00Z" },
    { id: 2, created_at: "2026-07-05T10:00:00Z" },
  ];

  const sorted = sortSpans(spans);

  assert.deepEqual(sorted.map((span) => span.id), [1, 2, 3]);
});

test("summarizeSpan includes provider and model when present", () => {
  const summary = summarizeSpan({
    provider: "openai",
    model: "gpt-4.1-mini",
    latency_ms: 187,
    total_tokens: 321,
    estimated_cost: 0.0123,
  });

  assert.equal(summary, "openai/gpt-4.1-mini | 187 ms | 321 tokens | $0.0123");
});

test("buildTraceSummary exposes latest status and failed counts", () => {
  const summary = buildTraceSummary([
    {
      id: 1,
      phase: "mapping",
      name: "Request mapping",
      status: "FAILED",
      created_at: "2026-07-07T10:00:00Z",
    },
    {
      id: 2,
      phase: "approval",
      name: "Await submit approval",
      status: "STARTED",
      created_at: "2026-07-07T10:01:00Z",
    },
  ]);

  assert.deepEqual(summary, {
    latestStatus: "Started",
    totalSpanCount: 2,
    failedSpanCount: 1,
    lastSpanLabel: "Approval / Await submit approval",
  });
});

test("getVisibleTraceSpans defaults to the latest three failed spans and expands to ten", () => {
  const spans = Array.from({ length: 12 }, (_, index) => ({
    id: index + 1,
    phase: "mapping",
    name: `Failed span ${index + 1}`,
    status: "FAILED",
    created_at: `2026-07-07T10:${String(index).padStart(2, "0")}:00Z`,
  }));

  assert.deepEqual(
    getVisibleTraceSpans(spans).map((span) => span.id),
    [12, 11, 10],
  );
  assert.equal(getVisibleTraceSpans(spans, true).length, 10);
  assert.equal(shouldShowTraceExpansion(spans), true);
  assert.equal(shouldShowTraceExpansion(spans.slice(0, 2)), false);
});

test("traceJsonText formats trace payload as indented JSON", () => {
  assert.equal(traceJsonText([{ id: 1 }]), '[\n  {\n    "id": 1\n  }\n]');
});
