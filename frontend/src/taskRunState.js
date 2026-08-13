import { isReviewableField } from "./reviewMappingPresentation.js";
import { phaseLabel, sortSpans } from "./workflowTracePresentation.js";

export function isFillableField(field) {
  return isReviewableField(field);
}

function hasMappedValue(field) {
  return field.mapped_value !== null && field.mapped_value !== undefined && field.mapped_value !== "";
}

function getTaskStatus(task) {
  return task?.workflow_status || task?.status;
}

function isWindowsFileUrl(url = "") {
  return /^file:\/\/\/[a-z]:/i.test(url);
}

function textIncludes(text, terms) {
  const normalized = String(text || "").toLowerCase();
  return terms.some((term) => normalized.includes(term));
}

function recoveryHintFor(task, detail, source) {
  const combined = `${task?.url || ""} ${detail || ""} ${source || ""}`;

  if (isWindowsFileUrl(task?.url) || textIncludes(combined, ["file:///c:/"])) {
    return "If this is the Docker demo, use a container path such as file:///app/examples/security-questionnaire.html. Docker cannot read Windows host file URLs.";
  }

  if (textIncludes(combined, ["login", "sign in", "authentication"])) {
    return "The agent will not bypass login. Use manual login for real sites, or switch to a public/local demo page for a no-login run.";
  }

  if (textIncludes(combined, ["provider", "api key", "llm", "model"])) {
    return "For local demos, switch mapping to rules mode or configure an LLM provider before retrying suggestions.";
  }

  if (textIncludes(combined, ["timeout", "net::", "network", "url"])) {
    return "Check that the URL is reachable from the backend browser. In Docker, prefer HTTP URLs or file:///app/examples/... demo files.";
  }

  if (textIncludes(combined, ["selector", "playwright", "browser"])) {
    return "Re-run analysis before retrying execution. The page structure or browser session may have changed.";
  }

  return "Open Advanced / Debug for trace evidence, then retry the failed step.";
}

export function getTaskRunSummary(task) {
  const fields = task?.form_fields || [];
  const fillableFields = fields.filter(isFillableField);

  return {
    totalFields: fields.length,
    mappedFields: fillableFields.filter(hasMappedValue).length,
    missingRequiredFields: fillableFields.filter(
      (field) => field.required && !hasMappedValue(field),
    ).length,
    skippedFields: fields.length - fillableFields.length,
  };
}

export function getVisibleRunSummaryItems(task) {
  const summary = getTaskRunSummary(task);
  return [
    {
      key: "totalFields",
      label: "Fields found",
      value: summary.totalFields,
    },
    {
      key: "mappedFields",
      label: "Mapped",
      value: summary.mappedFields,
    },
    {
      key: "missingRequiredFields",
      label: "Need input",
      value: summary.missingRequiredFields,
    },
  ];
}

const stateByStatus = {
  CREATED: {
    statusLabel: "Not prepared",
    description: "Prepare the workflow before reviewing any values.",
    primaryAction: "prepare",
    primaryLabel: "Prepare workflow",
  },
  ANALYZING: {
    statusLabel: "Preparing",
    description: "The page is being analyzed.",
    primaryAction: null,
    primaryLabel: "",
  },
  LOGIN_REQUIRED: {
    statusLabel: "Login required",
    description: "Log in once, then the page can be analyzed.",
    primaryAction: "login",
    primaryLabel: "Continue after login",
  },
  LOGIN_IN_PROGRESS: {
    statusLabel: "Login in progress",
    description: "Finish login in the browser window, then close it.",
    primaryAction: null,
    primaryLabel: "",
  },
  MAPPING_READY: {
    statusLabel: "Needs review",
    description: "Review suggested answers with source evidence before browser execution.",
    primaryAction: "review",
    primaryLabel: "Review values",
  },
  REVIEWING: {
    statusLabel: "Needs review",
    description: "Review suggested answers with source evidence before browser execution.",
    primaryAction: "review",
    primaryLabel: "Review values",
  },
  READY_TO_FILL: {
    statusLabel: "Ready to apply",
    description: "Reviewed values are ready for browser execution.",
    primaryAction: "fill",
    primaryLabel: "Apply values",
  },
  FILLING: {
    statusLabel: "Applying",
    description: "Reviewed values are being applied in the browser.",
    primaryAction: null,
    primaryLabel: "",
  },
  WAITING_APPROVAL: {
    statusLabel: "Waiting for approval",
    description: "Values have been applied and verified. Review the screenshot before final submission.",
    primaryAction: "approve",
    primaryLabel: "Approve submit",
  },
  COMPLETED: {
    statusLabel: "Completed",
    description: "Submitted after approval.",
    primaryAction: null,
    primaryLabel: "",
  },
  FAILED: {
    statusLabel: "Failed",
    description: "Something went wrong. Retry preparation after checking details.",
    primaryAction: "prepare",
    primaryLabel: "Retry preparation",
  },
};

const failureStateByStage = {
  ANALYSIS: {
    statusLabel: "Analysis failed",
    description: "Failed to analyze the page structure. Check the URL or network connection.",
    primaryAction: "prepare",
    primaryLabel: "Retry analysis",
  },
  MAPPING: {
    statusLabel: "Suggestion failed",
    description: "Failed to retrieve evidence and suggest answers. Check LLM provider configuration or review the page URL.",
    primaryAction: "map",
    primaryLabel: "Retry suggestion",
  },
  FILL: {
    statusLabel: "Execution failed",
    description: "Failed to apply values in the browser. Check the browser session or field selectors.",
    primaryAction: "fill",
    primaryLabel: "Retry execution",
  },
};

function getFailedStage(checkpoints) {
  const failedCheckpoints = checkpoints.filter((cp) => cp.status === "FAILED");
  if (failedCheckpoints.length === 0) {
    return null;
  }
  return failedCheckpoints[failedCheckpoints.length - 1].stage;
}

export function getTaskRunState(task, checkpoints = []) {
  const taskStatus = getTaskStatus(task);
  const baseState = stateByStatus[taskStatus];
  if (!baseState) {
    return {
      statusLabel: taskStatus || "Unknown",
      description: "Check the task details before continuing.",
      primaryAction: null,
      primaryLabel: "",
    };
  }

  if (taskStatus === "FAILED") {
    const failedStage = getFailedStage(checkpoints);
    if (failedStage && failureStateByStage[failedStage]) {
      return failureStateByStage[failedStage];
    }
  }

  return baseState;
}

export function getLoginRequiredSummary(task) {
  if (getTaskStatus(task) !== "LOGIN_REQUIRED") {
    return null;
  }

  return {
    title: "Login required",
    detail: "This page needs a user login before analysis can continue.",
    source: "Login gate",
    recoveryHint: recoveryHintFor(task, "login required", "Login gate"),
  };
}

const failureTitleByTracePhase = {
  extraction: "Analysis failed",
  mapping: "Mapping failed",
  browser: "Fill failed",
  verification: "Verification failed",
  approval: "Approval failed",
};

export function getRunFailureSummary(task, checkpoints = [], traceSpans = []) {
  if (getTaskStatus(task) !== "FAILED") {
    return null;
  }

  const latestFailedSpan = sortSpans(traceSpans)
    .filter((span) => span?.status === "FAILED")
    .at(-1);

  if (latestFailedSpan) {
    const title =
      failureTitleByTracePhase[latestFailedSpan.phase] ||
      getTaskRunState(task, checkpoints).statusLabel;
    const detail = latestFailedSpan.error_message || "Check advanced details for the failed step.";
    const source = `${phaseLabel(latestFailedSpan.phase)} / ${latestFailedSpan.name || "Unknown"}`;
    return {
      title,
      detail,
      source,
      recoveryHint: recoveryHintFor(task, detail, source),
    };
  }

  const latestFailedCheckpoint = checkpoints
    .filter((checkpoint) => checkpoint?.status === "FAILED")
    .at(-1);
  const detail =
    latestFailedCheckpoint?.error_message ||
    latestFailedCheckpoint?.failure_reason ||
    "Check advanced details for the failed step.";
  const source = latestFailedCheckpoint?.stage || "Run";

  return {
    title: getTaskRunState(task, checkpoints).statusLabel,
    detail,
    source,
    recoveryHint: recoveryHintFor(task, detail, source),
  };
}

export function shouldOpenAdvancedByDefault() {
  return false;
}
