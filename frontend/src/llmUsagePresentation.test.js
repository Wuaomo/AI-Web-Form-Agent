import assert from "node:assert/strict";
import test from "node:test";

import {
  formatLatency,
  formatEstimatedCost,
  formatCacheHitRate,
  summarizeLlmUsage,
} from "./llmUsagePresentation.js";

test("formatLatency returns milliseconds for values under 1000", () => {
  assert.equal(formatLatency(500), "500ms");
  assert.equal(formatLatency(999), "999ms");
});

test("formatLatency returns seconds for values 1000 and above", () => {
  assert.equal(formatLatency(1200), "1.2s");
  assert.equal(formatLatency(2500), "2.5s");
  assert.equal(formatLatency(10000), "10.0s");
});

test("formatLatency handles zero", () => {
  assert.equal(formatLatency(0), "0ms");
});

test("formatLatency handles null and undefined", () => {
  assert.equal(formatLatency(null), "-");
  assert.equal(formatLatency(undefined), "-");
});

test("formatEstimatedCost returns 'Not estimated' for zero", () => {
  assert.equal(formatEstimatedCost(0), "Not estimated");
});

test("formatEstimatedCost returns 'Not estimated' for null and undefined", () => {
  assert.equal(formatEstimatedCost(null), "Not estimated");
  assert.equal(formatEstimatedCost(undefined), "Not estimated");
});

test("formatEstimatedCost returns formatted dollar amount for positive values", () => {
  assert.equal(formatEstimatedCost(0.01), "$0.0100");
  assert.equal(formatEstimatedCost(0.15), "$0.1500");
  assert.equal(formatEstimatedCost(1.23456), "$1.2346");
});

test("formatCacheHitRate returns percentage rounded to nearest integer", () => {
  assert.equal(formatCacheHitRate(0.8546), "85%");
  assert.equal(formatCacheHitRate(0.5), "50%");
  assert.equal(formatCacheHitRate(1.0), "100%");
  assert.equal(formatCacheHitRate(0.0), "0%");
});

test("formatCacheHitRate handles null, undefined, and NaN", () => {
  assert.equal(formatCacheHitRate(null), "-");
  assert.equal(formatCacheHitRate(undefined), "-");
  assert.equal(formatCacheHitRate(NaN), "-");
});

test("summarizeLlmUsage returns safe empty values for missing summary", () => {
  const result = summarizeLlmUsage(null);
  assert.equal(result.requestCount, "-");
  assert.equal(result.promptTokens, "-");
  assert.equal(result.completionTokens, "-");
  assert.equal(result.totalTokens, "-");
  assert.equal(result.cacheHitRate, "-");
  assert.equal(result.averageLatency, "-");
  assert.equal(result.p95Latency, "-");
  assert.equal(result.fallbackCount, "-");
  assert.equal(result.estimatedCost, "Not estimated");
});

test("summarizeLlmUsage returns safe empty values for undefined summary", () => {
  const result = summarizeLlmUsage(undefined);
  assert.equal(result.requestCount, "-");
  assert.equal(result.estimatedCost, "Not estimated");
});

test("summarizeLlmUsage formats all fields correctly for valid summary", () => {
  const summary = {
    request_count: 11,
    prompt_tokens: 27678,
    completion_tokens: 1845,
    total_tokens: 29523,
    cache_hit_rate: 0.2497,
    average_latency_ms: 1200,
    p95_latency_ms: 2200,
    fallback_count: 2,
    estimated_cost: 0.15,
  };

  const result = summarizeLlmUsage(summary);

  assert.equal(result.requestCount, "11");
  assert.equal(result.promptTokens, "27,678");
  assert.equal(result.completionTokens, "1,845");
  assert.equal(result.totalTokens, "29,523");
  assert.equal(result.cacheHitRate, "25%");
  assert.equal(result.averageLatency, "1.2s");
  assert.equal(result.p95Latency, "2.2s");
  assert.equal(result.fallbackCount, "2");
  assert.equal(result.estimatedCost, "$0.1500");
});

test("summarizeLlmUsage formats latency values correctly", () => {
  const summary = {
    request_count: 5,
    average_latency_ms: 800,
    p95_latency_ms: 1500,
  };

  const result = summarizeLlmUsage(summary);

  assert.equal(result.averageLatency, "800ms");
  assert.equal(result.p95Latency, "1.5s");
});