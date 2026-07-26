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
