export const benchmarkMetricOrder = [
  "field_extraction_recall",
  "field_extraction_precision",
  "mapping_accuracy",
  "required_field_coverage",
  "non_fillable_rejection_rate",
  "login_detection_accuracy",
  "fill_success_rate",
  "llm_fallback_count",
  "average_case_duration_ms",
  "p95_case_duration_ms",
  "llm_cache_hit_rate",
  "retry_success_rate",
  "failure_rate",
];

const metricLabels = {
  field_extraction_recall: "Field extraction recall",
  field_extraction_precision: "Field extraction precision",
  mapping_accuracy: "Mapping accuracy",
  required_field_coverage: "Required field coverage",
  non_fillable_rejection_rate: "Non-fillable rejection rate",
  login_detection_accuracy: "Login detection accuracy",
  fill_success_rate: "Fill success rate",
  llm_fallback_count: "LLM fallback count",
  average_case_duration_ms: "Average case duration",
  p95_case_duration_ms: "P95 case duration",
  llm_cache_hit_rate: "LLM cache hit rate",
  retry_success_rate: "Retry success rate",
  failure_rate: "Failure rate",
};

export function formatMetricPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "N/A";
  }
  return `${Math.round(Number(value) * 100)}%`;
}

export function formatMetricValue(key, value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "N/A";
  }

  if (key === "llm_fallback_count") {
    const numericValue = Number(value);
    return Number.isInteger(numericValue)
      ? String(numericValue)
      : numericValue.toFixed(2);
  }

  if (key.endsWith("_duration_ms")) {
    const ms = Number(value);
    if (ms >= 1000) {
      return `${(ms / 1000).toFixed(1)}s`;
    }
    return `${Math.round(ms)}ms`;
  }

  return formatMetricPercent(value);
}

export function metricEntries(metrics = {}) {
  const knownEntries = benchmarkMetricOrder.map((key) => ({
    key,
    label: metricLabels[key] || key.replaceAll("_", " "),
    value: formatMetricValue(key, metrics[key]),
  }));

  const extraEntries = Object.entries(metrics)
    .filter(([key]) => !benchmarkMetricOrder.includes(key))
    .map(([key, value]) => ({
      key,
      label: metricLabels[key] || key.replaceAll("_", " "),
      value: formatMetricValue(key, value),
    }));

  return [...knownEntries, ...extraEntries];
}

export function summaryMetricEntries(metrics = {}) {
  return benchmarkMetricOrder.map((key) => ({
    key,
    label: metricLabels[key] || key.replaceAll("_", " "),
    value: formatMetricValue(key, metrics[key]),
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

const legacyFailureReasonMap = {
  missing_extraction: "field_not_extracted",
  profile_key_mismatch: "wrong_profile_key",
  should_not_map: "action_field_should_skip",
};

const failureReasonLabels = {
  field_not_extracted: "Field not extracted",
  wrong_profile_key: "Wrong profile key",
  missing_required_value: "Missing required value",
  action_field_should_skip: "Action field should be skipped",
  option_value_mismatch: "Option value mismatch",
  low_confidence_mapping: "Low confidence mapping",
  unexpected_extra_mapping: "Unexpected extra mapping",
};

function humanizeFailureReason(reason) {
  if (!reason) {
    return "Unknown reason";
  }
  const text = String(reason).replaceAll("_", " ");
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}`;
}

export function normalizeFailureReason(reason) {
  if (!reason) {
    return "";
  }
  return legacyFailureReasonMap[reason] || reason;
}

export function failureReasonLabel(reason) {
  const normalized = normalizeFailureReason(reason);
  return failureReasonLabels[normalized] || humanizeFailureReason(normalized);
}

