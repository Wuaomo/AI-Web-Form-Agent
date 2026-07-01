const metricLabels = {
  field_extraction_recall: "Field extraction recall",
  field_extraction_precision: "Field extraction precision",
  mapping_accuracy: "Mapping accuracy",
  required_field_coverage: "Required field coverage",
  non_fillable_rejection_rate: "Action rejection",
  login_detection_accuracy: "Login detection",
  fill_success_rate: "Fill success",
  llm_fallback_count: "LLM fallbacks",
};

export function formatMetricPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "N/A";
  }
  return `${Math.round(Number(value) * 100)}%`;
}

export function metricEntries(metrics = {}) {
  return Object.entries(metrics).map(([key, value]) => ({
    key,
    label: metricLabels[key] || key.replaceAll("_", " "),
    value: key === "llm_fallback_count" ? String(value) : formatMetricPercent(value),
  }));
}

export function caseFailureCount(caseResult = {}) {
  return (caseResult.failures || []).length;
}

export function summarizeBenchmarkRun(run = {}) {
  return {
    averageScore: formatMetricPercent(run.average_score),
    totalCases: run.total_cases || 0,
    totalFailures: (run.case_results || []).reduce(
      (count, caseResult) => count + caseFailureCount(caseResult),
      0,
    ),
  };
}

export function selectDefaultProviderId(providers = []) {
  const items = Array.isArray(providers) ? providers : [];
  if (items.length === 0) {
    return "";
  }

  const selected = items.find((provider) => provider && provider.selected === true);
  if (selected?.id) {
    return selected.id;
  }

  const configured = items.find((provider) => provider && provider.configured === true);
  if (configured?.id) {
    return configured.id;
  }

  return items[0]?.id || "";
}

export function shouldDisableBenchmarkRun(mode, provider) {
  if (mode !== "llm") {
    return false;
  }
  if (!provider) {
    return true;
  }
  return provider.configured !== true;
}

