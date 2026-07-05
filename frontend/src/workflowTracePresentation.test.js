import assert from "node:assert/strict";
import test from "node:test";

import {
  phaseLabel,
  sortSpans,
  spanStatusLabel,
  summarizeSpan,
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
