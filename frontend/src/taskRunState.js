const nonFillableFieldTypes = new Set([
  "button",
  "file",
  "submit",
  "reset",
  "image",
]);

export function isFillableField(field) {
  return !nonFillableFieldTypes.has((field.field_type || "").toLowerCase());
}

function hasMappedValue(field) {
  return field.mapped_value !== null && field.mapped_value !== undefined && field.mapped_value !== "";
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

export function getTaskRunState(task) {
  return (
    stateByStatus[task?.status] || {
      statusLabel: task?.status || "Unknown",
      description: "Check the task details before continuing.",
      primaryAction: null,
      primaryLabel: "",
    }
  );
}
