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
    description: "Review suggested values before browser execution.",
    primaryAction: "review",
    primaryLabel: "Review values",
  },
  REVIEWING: {
    statusLabel: "Needs review",
    description: "Review suggested values before browser execution.",
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
    description: "Check the screenshot before final submission.",
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
    statusLabel: "Mapping failed",
    description: "Failed to map fields to profile values. Check LLM provider configuration.",
    primaryAction: "map",
    primaryLabel: "Retry mapping",
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
    return {
      title:
        failureTitleByTracePhase[latestFailedSpan.phase] ||
        getTaskRunState(task, checkpoints).statusLabel,
      detail: latestFailedSpan.error_message || "Check advanced details for the failed step.",
      source: `${phaseLabel(latestFailedSpan.phase)} / ${latestFailedSpan.name || "Unknown"}`,
    };
  }

  const latestFailedCheckpoint = checkpoints
    .filter((checkpoint) => checkpoint?.status === "FAILED")
    .at(-1);

  return {
    title: getTaskRunState(task, checkpoints).statusLabel,
    detail:
      latestFailedCheckpoint?.error_message ||
      latestFailedCheckpoint?.failure_reason ||
      "Check advanced details for the failed step.",
    source: latestFailedCheckpoint?.stage || "Run",
  };
}

export function shouldOpenAdvancedByDefault() {
  return false;
}
