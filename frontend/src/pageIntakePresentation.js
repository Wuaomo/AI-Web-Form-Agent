const WORKFLOW_LABELS = {
  security_questionnaire: "Security Questionnaire",
  vendor_onboarding: "Vendor Onboarding",
  job_research_summary: "Job Research Summary",
  form_fill: "Form Fill",
  web_data_extract: "Web Data Extract",
};

const RISK_LABELS = {
  login_required: "Login required",
  captcha: "CAPTCHA blocked",
  otp: "One-time code blocked",
  payment: "Payment blocked",
  destructive_action: "Destructive action review",
  password: "Password blocked",
};

export function workflowLabel(workflowType) {
  return WORKFLOW_LABELS[workflowType] || workflowType;
}

export function riskLabel(flag) {
  return RISK_LABELS[flag] || flag;
}

export function confidenceLabel(value) {
  if (value >= 0.8) {
    return "High confidence";
  }
  if (value >= 0.6) {
    return "Medium confidence";
  }
  return "Needs review";
}

export function getPageIntakeCheckpoint(checkpoints = []) {
  const intakeCheckpoints = checkpoints.filter(
    (checkpoint) => checkpoint?.stage === "PAGE_INTAKE",
  );
  return intakeCheckpoints.length
    ? intakeCheckpoints[intakeCheckpoints.length - 1]
    : null;
}

export function buildPageIntakeBrief(checkpoints = []) {
  const checkpoint = getPageIntakeCheckpoint(checkpoints);
  const output = checkpoint?.output;
  if (!output) {
    return null;
  }
  const confidence = Number(output.confidence || 0);
  return {
    status: checkpoint.status,
    pageType: output.page_type || "unknown",
    workflowType: output.recommended_workflow || "unknown",
    workflowLabel: workflowLabel(output.recommended_workflow),
    confidence,
    confidenceText: `${confidenceLabel(confidence)} (${confidence.toFixed(2)})`,
    detectedFieldCount: Array.isArray(output.detected_fields)
      ? output.detected_fields.length
      : 0,
    riskLabels: Array.isArray(output.risk_flags)
      ? output.risk_flags.map(riskLabel)
      : [],
    evidenceItems: Array.isArray(output.evidence) ? output.evidence : [],
  };
}
