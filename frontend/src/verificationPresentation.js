export function summarizeVerificationResults(results = []) {
  const summary = {
    verified: 0,
    failed: 0,
    skipped: 0,
    partial: 0,
    total: results.length,
  };

  for (const result of results) {
    switch (result.status) {
      case "VERIFIED":
        summary.verified++;
        break;
      case "FAILED":
        summary.failed++;
        break;
      case "SKIPPED":
        summary.skipped++;
        break;
      case "PARTIAL":
        summary.partial++;
        break;
      default:
        break;
    }
  }

  return summary;
}

export function verificationStatusLabel(status) {
  const labels = {
    VERIFIED: "Verified",
    FAILED: "Failed",
    SKIPPED: "Skipped",
    PARTIAL: "Partial",
  };

  return labels[status] || humanizeLabel(status);
}

export function verificationReasonLabel(reason) {
  if (!reason) {
    return null;
  }

  const labels = {
    SELECTOR_NOT_FOUND: "Selector not found",
    VALUE_MISMATCH: "Value mismatch",
    OPTION_NOT_SELECTED: "Option not selected",
    FIELD_DISABLED: "Field disabled",
    SENSITIVE_FIELD_SKIPPED: "Sensitive field skipped",
    PAGE_NAVIGATED_UNEXPECTEDLY: "Page navigated unexpectedly",
  };

  return labels[reason] || humanizeLabel(reason);
}

function humanizeLabel(str) {
  if (!str) {
    return "Unknown";
  }

  return str
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/(?:^|\s)\w/g, (char) => char.toUpperCase())
    .trim();
}