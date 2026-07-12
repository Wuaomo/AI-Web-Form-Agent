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
    description: "Prepare the form before reviewing any values.",
    primaryAction: "prepare",
    primaryLabel: "Prepare form",
  },
  ANALYZING: {
    statusLabel: "Preparing",
    description: "The form is being analyzed.",
    primaryAction: null,
    primaryLabel: "",
  },
  LOGIN_REQUIRED: {
    statusLabel: "Login required",
    description: "Log in once, then the form can be analyzed.",
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
    description: "Review the mapped values before filling the form.",
    primaryAction: "review",
    primaryLabel: "Review mapping",
  },
  REVIEWING: {
    statusLabel: "Needs review",
    description: "Review the mapped values before filling the form.",
    primaryAction: "review",
    primaryLabel: "Review mapping",
  },
  READY_TO_FILL: {
    statusLabel: "Ready to fill",
    description: "The reviewed mapping is ready to apply to the form.",
    primaryAction: "fill",
    primaryLabel: "Fill form",
  },
  FILLING: {
    statusLabel: "Filling",
    description: "The reviewed values are being entered into the form.",
    primaryAction: null,
    primaryLabel: "",
  },
  WAITING_APPROVAL: {
    statusLabel: "Waiting for approval",
    description: "Check the filled form screenshot before final submission.",
    primaryAction: "approve",
    primaryLabel: "Approve submit",
  },
  COMPLETED: {
    statusLabel: "Completed",
    description: "The form was submitted after approval.",
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
    description: "Failed to analyze the form structure. Check the URL or network connection.",
    primaryAction: "prepare",
    primaryLabel: "Retry analysis",
  },
  MAPPING: {
    statusLabel: "Mapping failed",
    description: "Failed to map form fields to profile values. Check LLM provider configuration.",
    primaryAction: "map",
    primaryLabel: "Retry mapping",
  },
  FILL: {
    statusLabel: "Fill failed",
    description: "Failed to fill the form. Check the browser session or form selectors.",
    primaryAction: "fill",
    primaryLabel: "Retry fill",
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
