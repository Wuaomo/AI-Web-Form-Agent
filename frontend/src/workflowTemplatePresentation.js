export function isTemplateEnabled(template) {
  return template?.enabled === true;
}

export function templateAvailabilityLabel(template) {
  return isTemplateEnabled(template) ? "Available" : "Coming soon";
}

const WORKFLOW_PRIORITY_ORDER = [
  "security_questionnaire",
  "form_fill",
  "vendor_onboarding",
  "web_data_extract",
  "job_research_summary",
];

function getWorkflowPriority(template) {
  const id = template?.id || "";
  const priority = WORKFLOW_PRIORITY_ORDER.indexOf(id);
  return priority >= 0 ? priority : WORKFLOW_PRIORITY_ORDER.length;
}

export function sortWorkflowTemplates(templates = []) {
  return [...templates].sort((left, right) => {
    if (isTemplateEnabled(left) !== isTemplateEnabled(right)) {
      return isTemplateEnabled(left) ? -1 : 1;
    }

    const leftPriority = getWorkflowPriority(left);
    const rightPriority = getWorkflowPriority(right);
    if (leftPriority !== rightPriority) {
      return leftPriority - rightPriority;
    }

    return String(left?.name || left?.id || "").localeCompare(
      String(right?.name || right?.id || ""),
    );
  });
}

export function buildWorkflowTemplateCreatePath(templateId) {
  return `/tasks/new?workflow_type=${encodeURIComponent(templateId)}`;
}

export function dockerDemoFormUrl() {
  return "file:///app/examples/llm-registration.html";
}

export function dockerDemoUrlForWorkflow(workflowType) {
  if (workflowType === "security_questionnaire") {
    return "file:///app/examples/security-questionnaire.html";
  }
  if (workflowType === "vendor_onboarding") {
    return "file:///app/examples/vendor-onboarding.html";
  }
  return dockerDemoFormUrl();
}

export function requiresLlmProviderForCreate(workflowType) {
  return ![
    "web_data_extract",
    "job_research_summary",
    "security_questionnaire",
    "vendor_onboarding",
  ].includes(workflowType);
}

export function mappingModeForWorkflow(workflowType) {
  return requiresLlmProviderForCreate(workflowType) ? "llm" : "rules";
}

export function resolveWorkflowTypeSelection(
  templates = [],
  requestedWorkflowType,
) {
  const orderedTemplates = sortWorkflowTemplates(templates);
  const enabledSecurityQuestionnaire = orderedTemplates.find(
    (template) => template?.id === "security_questionnaire" && isTemplateEnabled(template),
  );
  const firstEnabledTemplate = orderedTemplates.find(isTemplateEnabled);
  const fallbackTemplate = enabledSecurityQuestionnaire || firstEnabledTemplate || null;

  if (!requestedWorkflowType) {
    return {
      selectedWorkflowType: fallbackTemplate?.id || "",
      notice: "",
    };
  }

  const requestedTemplate = orderedTemplates.find(
    (template) => template?.id === requestedWorkflowType,
  );

  if (requestedTemplate && isTemplateEnabled(requestedTemplate)) {
    return {
      selectedWorkflowType: requestedTemplate.id,
      notice: "",
    };
  }

  const fallbackId = fallbackTemplate?.id || "";
  const fallbackNotice =
    fallbackTemplate && fallbackTemplate.id === "security_questionnaire"
      ? "Requested workflow template is unavailable. Using security_questionnaire instead."
      : "Requested workflow template is unavailable.";

  return {
    selectedWorkflowType: fallbackId,
    notice: fallbackNotice,
  };
}
