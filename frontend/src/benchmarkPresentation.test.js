import test from "node:test";
import assert from "node:assert/strict";

import {
  benchmarkMetricOrder,
  caseFailureCount,
  failureReasonLabel,
  formatDuration,
  formatMetricPercent,
  formatMetricValue,
  formatRegressionStatus,
  metricEntries,
  normalizeFailureReason,
  selectDefaultProviderId,
  shouldDisableBenchmarkRun,
  sortCaseResults,
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

  const summary = summarizeBenchmarkRun(run);
  assert.equal(summary.averageScore, "75%");
  assert.equal(summary.totalCases, 2);
  assert.equal(summary.totalFailures, 2);
  assert.equal(summary.durationMs, 0);
  assert.equal(summary.regressionCount, 0);
  assert.equal(summary.improvementCount, 0);
  assert.equal(summary.mode, "rules");
  assert.equal(summary.provider, null);
  assert.equal(summary.stressMode, null);
  assert.equal(summary.baselineRunId, null);

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
    { key: "average_case_duration_ms", label: "Average case duration", value: "N/A" },
    { key: "p95_case_duration_ms", label: "P95 case duration", value: "N/A" },
    { key: "llm_cache_hit_rate", label: "LLM cache hit rate", value: "N/A" },
    { key: "retry_success_rate", label: "Retry success rate", value: "N/A" },
    { key: "failure_rate", label: "Failure rate", value: "N/A" },
  ]);
});

test("formatMetricValue formats percentages, counts, and missing values correctly", () => {
  assert.equal(formatMetricValue("mapping_accuracy", 0.943), "94%");
  assert.equal(formatMetricValue("llm_fallback_count", 3), "3");
  assert.equal(formatMetricValue("llm_fallback_count", 0.5), "0.50");
  assert.equal(formatMetricValue("llm_fallback_count", 1.25), "1.25");
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
  assert.equal(entries.at(-2).key, "failure_rate");
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

test("normalizeFailureReason maps legacy failure reasons to stable taxonomy strings", () => {
  assert.equal(normalizeFailureReason("missing_extraction"), "field_not_extracted");
  assert.equal(normalizeFailureReason("profile_key_mismatch"), "wrong_profile_key");
  assert.equal(normalizeFailureReason("should_not_map"), "action_field_should_skip");
  assert.equal(normalizeFailureReason("field_not_extracted"), "field_not_extracted");
});

test("failureReasonLabel returns human-readable English labels for stable failure reasons", () => {
  assert.equal(failureReasonLabel("wrong_profile_key"), "Wrong profile key");
  assert.equal(failureReasonLabel("field_not_extracted"), "Field not extracted");
  assert.equal(failureReasonLabel("action_field_should_skip"), "Action field should be skipped");
  assert.equal(failureReasonLabel("profile_key_mismatch"), "Wrong profile key");
});

test("formatDuration formats milliseconds correctly", () => {
  assert.equal(formatDuration(500), "500ms");
  assert.equal(formatDuration(1500), "1.5s");
  assert.equal(formatDuration(0), "0ms");
  assert.equal(formatDuration(null), "N/A");
  assert.equal(formatDuration(undefined), "N/A");
});

test("formatRegressionStatus formats regression and improvement counts", () => {
  assert.equal(formatRegressionStatus(0, 0), "No changes");
  assert.equal(formatRegressionStatus(2, 0), "2 regressed");
  assert.equal(formatRegressionStatus(0, 3), "3 improved");
  assert.equal(formatRegressionStatus(1, 2), "2 improved, 1 regressed");
});

test("sortCaseResults sorts failed cases first", () => {
  const cases = [
    { id: 1, failures: [] },
    { id: 2, failures: [{ selector: "#name" }] },
    { id: 3, failures: [] },
    { id: 4, failures: [{ selector: "#email" }, { selector: "#phone" }] },
  ];

  const sorted = sortCaseResults(cases);

  assert.equal(sorted[0].id, 2);
  assert.equal(sorted[1].id, 4);
  assert.equal(sorted[2].id, 1);
  assert.equal(sorted[3].id, 3);
});

test("summarizeBenchmarkRun includes duration and regression counts", () => {
  const run = {
    average_score: 0.75,
    total_cases: 5,
    duration_ms: 2500,
    regression_count: 1,
    improvement_count: 2,
    mode: "llm",
    provider: "openai",
    mode_detail: "cache_warm",
    baseline_run_id: 10,
    case_results: [
      { failures: [] },
      { failures: [{ selector: "#email" }] },
    ],
  };

  const summary = summarizeBenchmarkRun(run);

  assert.equal(summary.averageScore, "75%");
  assert.equal(summary.totalCases, 5);
  assert.equal(summary.totalFailures, 1);
  assert.equal(summary.durationMs, 2500);
  assert.equal(summary.regressionCount, 1);
  assert.equal(summary.improvementCount, 2);
  assert.equal(summary.mode, "llm");
  assert.equal(summary.provider, "openai");
  assert.equal(summary.stressMode, "cache_warm");
  assert.equal(summary.baselineRunId, 10);
});

