import test from "node:test";
import assert from "node:assert/strict";

import {
  benchmarkMetricOrder,
  caseFailureCount,
  formatMetricPercent,
  formatMetricValue,
  metricEntries,
  selectDefaultProviderId,
  shouldDisableBenchmarkRun,
  summaryMetricEntries,
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
  assert.deepEqual(metricEntries(run.summary_metrics).slice(0, 3), [
    { key: "field_extraction_recall", label: "Field extraction recall", value: "100%" },
    { key: "field_extraction_precision", label: "Field extraction precision", value: "N/A" },
    { key: "mapping_accuracy", label: "Mapping accuracy", value: "50%" },
  ]);
  assert.equal(caseFailureCount(run.case_results[1]), 2);
});

test("summaryMetricEntries returns all summary metrics in stable order with English labels", () => {
  const entries = summaryMetricEntries({
    field_extraction_recall: 1,
    mapping_accuracy: 0.5,
    llm_fallback_count: 2,
  });

  assert.deepEqual(
    entries.map((entry) => entry.key),
    benchmarkMetricOrder,
  );
  assert.deepEqual(entries, [
    { key: "field_extraction_recall", label: "Field extraction recall", value: "100%" },
    { key: "field_extraction_precision", label: "Field extraction precision", value: "N/A" },
    { key: "mapping_accuracy", label: "Mapping accuracy", value: "50%" },
    { key: "required_field_coverage", label: "Required field coverage", value: "N/A" },
    {
      key: "non_fillable_rejection_rate",
      label: "Non-fillable rejection rate",
      value: "N/A",
    },
    { key: "login_detection_accuracy", label: "Login detection accuracy", value: "N/A" },
    { key: "fill_success_rate", label: "Fill success rate", value: "N/A" },
    { key: "llm_fallback_count", label: "LLM fallback count", value: "2" },
  ]);
});

test("formatMetricValue formats percentages, counts, and missing values correctly", () => {
  assert.equal(formatMetricValue("mapping_accuracy", 0.943), "94%");
  assert.equal(formatMetricValue("llm_fallback_count", 3), "3");
  assert.equal(formatMetricValue("llm_fallback_count", null), "N/A");
});

test("metricEntries keeps known metrics first and appends extra metrics", () => {
  const entries = metricEntries({
    mapping_accuracy: 0.5,
    llm_fallback_count: 1,
    custom_metric: 0.25,
  });

  assert.equal(entries[0].key, "field_extraction_recall");
  assert.equal(entries[2].key, "mapping_accuracy");
  assert.equal(entries.at(-2).key, "llm_fallback_count");
  assert.deepEqual(entries.at(-1), {
    key: "custom_metric",
    label: "custom metric",
    value: "25%",
  });
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

