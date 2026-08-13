export function pendingApprovalRequests(approvalRequests = []) {
  return approvalRequests.filter((item) => item.status === "PENDING");
}

export function shouldShowApprovalsOnMain(approvalRequests = []) {
  return pendingApprovalRequests(approvalRequests).length > 0;
}
