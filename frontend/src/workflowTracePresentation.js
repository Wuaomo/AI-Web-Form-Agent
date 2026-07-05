const phaseLabels = {
  extraction: "Extraction",
  mapping: "Mapping",
  approval: "Approval",
  browser: "Browser",
  verification: "Verification",
};

const statusLabels = {
  STARTED: "Started",
  SUCCESS: "Success",
  FAILED: "Failed",
  SKIPPED: "Skipped",
};

export function phaseLabel(phase) {
  return phaseLabels[phase] || phase || "Unknown";
}

export function spanStatusLabel(status) {
  return statusLabels[status] || status || "Unknown";
}

export function sortSpans(spans = []) {
  return [...spans].sort((left, right) => {
    const leftTime = Date.parse(left.created_at || "") || 0;
    const rightTime = Date.parse(right.created_at || "") || 0;
    if (leftTime !== rightTime) {
      return leftTime - rightTime;
    }
    return (left.id || 0) - (right.id || 0);
  });
}

export function summarizeSpan(span) {
  const details = [];

  if (span?.provider && span?.model) {
    details.push(`${span.provider}/${span.model}`);
  } else if (span?.provider) {
    details.push(span.provider);
  } else if (span?.model) {
    details.push(span.model);
  }

  if (span?.latency_ms > 0) {
    details.push(`${span.latency_ms} ms`);
  }

  if (span?.total_tokens > 0) {
    details.push(`${span.total_tokens} tokens`);
  }

  if (typeof span?.estimated_cost === "number" && span.estimated_cost > 0) {
    details.push(`$${span.estimated_cost.toFixed(4)}`);
  }

  if (span?.error_message) {
    details.push(span.error_message);
  }

  return details.join(" | ");
}
