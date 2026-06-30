import test from "node:test";
import assert from "node:assert/strict";

import {
  caseFailureCount,
  formatMetricPercent,
  metricEntries,
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

