import test from "node:test";
import assert from "node:assert/strict";

import {
  caseFailureCount,
  formatMetricPercent,
  metricEntries,
  selectDefaultProviderId,
  shouldDisableBenchmarkRun,
  summarizeBenchmarkRun,
} from "./benchmarkPresentation.js";

test("formatMetricPercent formats ratios as whole percentages", () => {
  assert.equal(formatMetricPercent(0.943), "94%");
  assert.equal(formatMetricPercent(1), "100%");
  assert.equal(formatMetricPercent(null), "N/A");
});

test("summarizeBenchmarkRun exposes score cards and failure counts", () => {
  const run = {
    average_score: 0.75,
    total_cases: 2,
    summary_metrics: {
      field_extraction_recall: 1,
      mapping_accuracy: 0.5,
    },
    case_results: [
      { failures: [] },
      { failures: [{ selector: "#email" }, { selector: "#phone" }] },
    ],
  };

  assert.deepEqual(summarizeBenchmarkRun(run), {
    averageScore: "75%",
    totalCases: 2,
    totalFailures: 2,
  });
  assert.deepEqual(metricEntries(run.summary_metrics), [
    { key: "field_extraction_recall", label: "Field extraction recall", value: "100%" },
    { key: "mapping_accuracy", label: "Mapping accuracy", value: "50%" },
  ]);
  assert.equal(caseFailureCount(run.case_results[1]), 2);
});

test("selectDefaultProviderId prefers selected providers, then configured providers, then first entry", () => {
  assert.equal(selectDefaultProviderId([]), "");
  assert.equal(selectDefaultProviderId(null), "");

  assert.equal(
    selectDefaultProviderId([
      { id: "openai", configured: true },
      { id: "deepseek", configured: true, selected: true },
    ]),
    "deepseek",
  );

  assert.equal(
    selectDefaultProviderId([
      { id: "openai", configured: false },
      { id: "gemini", configured: true },
    ]),
    "gemini",
  );

  assert.equal(
    selectDefaultProviderId([
      { id: "openai", configured: false },
      { id: "gemini", configured: false },
    ]),
    "openai",
  );
});

test("shouldDisableBenchmarkRun enforces provider configuration for llm mode", () => {
  assert.equal(shouldDisableBenchmarkRun("rules", null), false);
  assert.equal(shouldDisableBenchmarkRun("rules", { configured: false }), false);
  assert.equal(shouldDisableBenchmarkRun("llm", null), true);
  assert.equal(shouldDisableBenchmarkRun("llm", { configured: false }), true);
  assert.equal(shouldDisableBenchmarkRun("llm", { configured: true }), false);
});

