/**
 * Presentation helpers for the AgentStep timeline.
 * Converts raw agent step data into user-readable labels and formatting.
 */

function toolLabel(toolName) {
  const labels = {
    open_url: "Open URL",
    extract_form: "Extract form",
    map_fields: "Map fields",
    request_human_approval: "Request approval",
    fill_form: "Fill form",
    verify_fields: "Verify fields",
    submit_form: "Submit form",
  };
  return labels[toolName] || toolName;
}

function statusLabel(status) {
  const labels = {
    PENDING: "Pending",
    STARTED: "In progress",
    SUCCESS: "Completed",
    FAILED: "Failed",
    APPROVAL_PENDING: "Awaiting approval",
  };
  return labels[status] || status;
}

function statusClass(status) {
  const classes = {
    PENDING: "agent-step-status-pending",
    STARTED: "agent-step-status-active",
    SUCCESS: "agent-step-status-success",
    FAILED: "agent-step-status-failed",
    APPROVAL_PENDING: "agent-step-status-pending",
  };
  return classes[status] || "agent-step-status-pending";
}

function evidenceLabel(evidence) {
  const labels = {
    screenshot: "Screenshot",
    trace_output: "Trace output",
    verification_results: "Verification",
    approval_request: "Approval request",
  };
  return labels[evidence] || evidence;
}

function formatTimestamp(timestamp) {
  if (!timestamp) return null;
  return new Date(timestamp).toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function presentAgentStep(step) {
  return {
    ...step,
    toolLabel: toolLabel(step.tool),
    statusLabel: statusLabel(step.status),
    statusClass: statusClass(step.status),
    evidenceLabels: step.evidence?.map(evidenceLabel) || [],
    startedAtFormatted: formatTimestamp(step.started_at),
    finishedAtFormatted: formatTimestamp(step.finished_at),
  };
}

export function hasFailedSteps(steps) {
  return steps.some((step) => step.status === "FAILED");
}

export function hasPendingApproval(steps) {
  return steps.some((step) => step.status === "APPROVAL_PENDING");
}

export function isStepCompleted(step) {
  return step.status === "SUCCESS";
}

export function isStepFailed(step) {
  return step.status === "FAILED";
}

export function isStepPending(step) {
  return step.status === "PENDING";
}
