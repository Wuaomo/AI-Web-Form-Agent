export const benchmarkMetricOrder = [
  "field_extraction_recall",
  "field_extraction_precision",
  "mapping_accuracy",
  "required_field_coverage",
  "answer_accuracy",
  "source_evidence_coverage",
  "unsupported_refusal_rate",
  "sensitive_skip_rate",
  "questionnaire_completion_rate",
  "non_fillable_rejection_rate",
  "login_detection_accuracy",
  "fill_success_rate",
  "workflow_success_rate",
  "safety_pass_rate",
  "verification_pass_rate",
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
  answer_accuracy: "Answer accuracy",
  source_evidence_coverage: "Source evidence coverage",
  unsupported_refusal_rate: "Unsupported refusal rate",
  sensitive_skip_rate: "Sensitive skip rate",
  questionnaire_completion_rate: "Questionnaire completion rate",
  non_fillable_rejection_rate: "Non-fillable rejection rate",
  login_detection_accuracy: "Login detection accuracy",
  fill_success_rate: "Fill success rate",
  workflow_success_rate: "Workflow success rate",
  safety_pass_rate: "Safety pass rate",
  verification_pass_rate: "Verification pass rate",
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
  const detail = parseModeDetail(run.mode_detail);
  return {
    averageScore: formatMetricPercent(run.average_score),
    totalCases: run.total_cases || 0,
    totalFailures: (run.case_results || []).reduce(
      (count, caseResult) => count + caseFailureCount(caseResult),
      0,
    ),
    durationMs: run.duration_ms || 0,
    regressionCount: run.regression_count || 0,
    improvementCount: run.improvement_count || 0,
    mode: run.mode || "rules",
    provider: run.provider || null,
    stressMode: detail.stressMode,
    memoryMode: detail.memoryMode,
    modeDetail: detail.modeDetail,
    baselineRunId: run.baseline_run_id || null,
  };
}

export function formatDuration(durationMs) {
  if (durationMs === null || durationMs === undefined || Number.isNaN(Number(durationMs))) {
    return "N/A";
  }
  const ms = Number(durationMs);
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(1)}s`;
  }
  return `${Math.round(ms)}ms`;
}

export function formatRegressionStatus(regressionCount, improvementCount) {
  if (regressionCount > 0 && improvementCount > 0) {
    return `${improvementCount} improved, ${regressionCount} regressed`;
  }
  if (regressionCount > 0) {
    return `${regressionCount} regressed`;
  }
  if (improvementCount > 0) {
    return `${improvementCount} improved`;
  }
  return "No changes";
}

export function sortCaseResults(caseResults = []) {
  return [...caseResults].sort((a, b) => {
    const failuresA = caseFailureCount(a);
    const failuresB = caseFailureCount(b);

    if (failuresA > 0 && failuresB === 0) {
      return -1;
    }
    if (failuresA === 0 && failuresB > 0) {
      return 1;
    }

    return 0;
  });
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
  if (mode !== "llm" && mode !== "rag_llm") {
    return false;
  }
  if (!provider) {
    return true;
  }
  return provider.configured !== true;
}

export function buildModeDetail(stressMode, memoryMode) {
  return `stress_mode=${stressMode};memory_mode=${memoryMode}`;
}

export function parseModeDetail(modeDetail) {
  if (!modeDetail) {
    return { stressMode: null, memoryMode: null, modeDetail: null };
  }
  const text = String(modeDetail);
  if (!text.includes("=")) {
    return { stressMode: null, memoryMode: null, modeDetail: text };
  }
  const parts = text.split(";").map((part) => part.trim()).filter(Boolean);
  const entries = Object.fromEntries(
    parts.map((part) => {
      const [key, ...rest] = part.split("=");
      return [key, rest.join("=")];
    }),
  );
  return {
    stressMode: entries.stress_mode || null,
    memoryMode: entries.memory_mode || null,
    modeDetail: text,
  };
}

export function compareRunMetrics(currentMetrics = {}, baselineMetrics = {}) {
  return benchmarkMetricOrder.map((key) => {
    const current = currentMetrics[key];
    const baseline = baselineMetrics[key];
    const delta =
      current === null ||
      current === undefined ||
      baseline === null ||
      baseline === undefined ||
      Number.isNaN(Number(current)) ||
      Number.isNaN(Number(baseline))
        ? null
        : Number(current) - Number(baseline);
    return {
      key,
      label: metricLabels[key] || key.replaceAll("_", " "),
      current: formatMetricValue(key, current),
      baseline: formatMetricValue(key, baseline),
      delta: formatMetricDeltaValue(key, delta),
    };
  });
}

export function formatMetricDeltaValue(key, delta) {
  if (delta === null || delta === undefined || Number.isNaN(Number(delta))) {
    return "—";
  }

  if (key === "llm_fallback_count") {
    const numericValue = Number(delta);
    const rounded = Number.isInteger(numericValue) ? numericValue : Number(numericValue.toFixed(2));
    return rounded > 0 ? `+${rounded}` : String(rounded);
  }

  if (key.endsWith("_duration_ms")) {
    const ms = Number(delta);
    if (ms === 0) {
      return "0ms";
    }
    const sign = ms > 0 ? "+" : "-";
    return `${sign}${formatDuration(Math.abs(ms))}`;
  }

  const percentagePoints = Math.round(Number(delta) * 100);
  if (percentagePoints === 0) {
    return "0%";
  }
  const sign = percentagePoints > 0 ? "+" : "";
  return `${sign}${percentagePoints}%`;
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
  wrong_answer: "Wrong answer",
  missing_source_evidence: "Missing source evidence",
  unsupported_answer_should_refuse: "Unsupported answer should be refused",
  sensitive_value_should_block: "Sensitive value should be blocked",
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

