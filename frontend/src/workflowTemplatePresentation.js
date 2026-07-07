export function isTemplateEnabled(template) {
  return template?.enabled === true;
}

export function templateAvailabilityLabel(template) {
  return isTemplateEnabled(template) ? "Available" : "Coming soon";
}

export function sortWorkflowTemplates(templates = []) {
  return [...templates].sort((left, right) => {
    if (isTemplateEnabled(left) !== isTemplateEnabled(right)) {
      return isTemplateEnabled(left) ? -1 : 1;
    }

    return String(left?.name || left?.id || "").localeCompare(
      String(right?.name || right?.id || ""),
    );
  });
}

export function buildWorkflowTemplateCreatePath(templateId) {
  return `/tasks/new?workflow_type=${encodeURIComponent(templateId)}`;
}

export function resolveWorkflowTypeSelection(
  templates = [],
  requestedWorkflowType,
) {
  const orderedTemplates = sortWorkflowTemplates(templates);
  const enabledFormFill = orderedTemplates.find(
    (template) => template?.id === "form_fill" && isTemplateEnabled(template),
  );
  const firstEnabledTemplate = orderedTemplates.find(isTemplateEnabled);
  const fallbackTemplate = enabledFormFill || firstEnabledTemplate || null;

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
    fallbackTemplate && fallbackTemplate.id === "form_fill"
      ? "Requested workflow template is unavailable. Using form_fill instead."
      : "Requested workflow template is unavailable.";

  return {
    selectedWorkflowType: fallbackId,
    notice: fallbackNotice,
  };
}
