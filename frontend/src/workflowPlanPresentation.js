export function getWorkflowPlanSteps(plan) {
  if (!plan || !Array.isArray(plan.steps)) {
    return [];
  }
  return plan.steps;
}

export function workflowPlanApprovalLabel(step) {
  return step?.requires_approval ? "Approval required" : null;
}
