export function formatLatency(ms) {
  if (ms === null || ms === undefined) return "-";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatEstimatedCost(value) {
  if (value === null || value === undefined || value === 0) {
    return "Not estimated";
  }
  return `$${value.toFixed(4)}`;
}

export function formatCacheHitRate(value) {
  if (value === null || value === undefined || isNaN(value)) return "-";
  return `${Math.round(value * 100)}%`;
}

export function summarizeLlmUsage(summary) {
  if (!summary) {
    return {
      requestCount: "-",
      promptTokens: "-",
      completionTokens: "-",
      totalTokens: "-",
      cacheHitRate: "-",
      averageLatency: "-",
      p95Latency: "-",
      fallbackCount: "-",
      estimatedCost: "Not estimated",
    };
  }

  return {
    requestCount: summary.request_count?.toLocaleString() || "-",
    promptTokens: summary.prompt_tokens?.toLocaleString() || "-",
    completionTokens: summary.completion_tokens?.toLocaleString() || "-",
    totalTokens: summary.total_tokens?.toLocaleString() || "-",
    cacheHitRate: formatCacheHitRate(summary.cache_hit_rate),
    averageLatency: formatLatency(summary.average_latency_ms),
    p95Latency: formatLatency(summary.p95_latency_ms),
    fallbackCount: summary.fallback_count?.toLocaleString() || "-",
    estimatedCost: formatEstimatedCost(summary.estimated_cost),
  };
}