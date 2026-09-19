export function pendingApprovalRequests(approvalRequests = []) {
  return approvalRequests.filter((item) => item.status === "PENDING");
}

export function shouldShowApprovalsOnMain(approvalRequests = []) {
  return pendingApprovalRequests(approvalRequests).length > 0;
}

export function resolveTaskExtractionResult(runtime, checkpointResult = null) {
  return runtime?.workflow_result?.extraction || checkpointResult;
}

export function resolveTaskResearchSummary(runtime, checkpointResult = null) {
  return runtime?.workflow_result?.research_summary || checkpointResult;
}
