export async function applyFieldValueEdit({
  apiClient,
  taskId,
  runId,
  field,
  mappedValue,
  reviewItemsByFieldId,
}) {
  return applyFieldReviewDecision({
    apiClient,
    taskId,
    runId,
    field,
    decision: "edited",
    editedValue: mappedValue,
    reviewItemsByFieldId,
  });
}

export function getReviewMappingRunId(task) {
  return task?.agent_run_id || task?.agent_runtime?.run_id || null;
}

export function shouldLoadLegacySecurityWorkflowFallback(task) {
  return false;
}

export async function loadReviewItemsForReviewMapping({
  apiClient,
  taskId,
  task,
}) {
  const runId = getReviewMappingRunId(task);
  if (runId) {
    try {
      return await apiClient.listAgentRunReviewItems(runId);
    } catch {
      // Keep the migration fallback until Review Mapping fully leaves /tasks.
    }
  }
  return apiClient.listTaskReviewItems(taskId);
}

export async function applyReviewItemDecision({
  apiClient,
  taskId,
  runId,
  reviewItem,
  decision,
  editedValue,
}) {
  const payload = buildReviewDecisionPayload(decision, editedValue);
  if (runId) {
    await apiClient.reviewAgentRunItem(runId, reviewItem.id, payload);
  } else {
    await apiClient.reviewTaskItem(taskId, reviewItem.id, payload);
  }
  return {
    reviewItem: applyDecisionToReviewItem(reviewItem, decision, editedValue),
  };
}

export async function applyFieldReviewDecision({
  apiClient,
  taskId,
  runId,
  field,
  decision,
  editedValue,
  reviewItemsByFieldId,
}) {
  const reviewItem = reviewItemsByFieldId.get(field.id);
  if (reviewItem) {
    const result = await applyReviewItemDecision({
      apiClient,
      taskId,
      runId,
      reviewItem,
      decision,
      editedValue,
    });
    return {
      usedGenericReview: true,
      field: applyDecisionToField(field, decision, editedValue, reviewItem),
      reviewItem: result.reviewItem,
    };
  }

  if (decision === "edited") {
    const updated = await apiClient.updateTaskField(taskId, field.id, {
      mapped_value: editedValue || null,
    });
    return { usedGenericReview: false, field: updated };
  }

  if (decision === "rejected") {
    const updated = await apiClient.updateTaskField(taskId, field.id, {
      mapped_profile_key: null,
      mapped_value: null,
    });
    return { usedGenericReview: false, field: updated };
  }

  return { usedGenericReview: false, field };
}

function buildReviewDecisionPayload(decision, editedValue) {
  if (decision === "edited") {
    return { decision, edited_value: editedValue };
  }
  return { decision };
}

function applyDecisionToField(field, decision, editedValue, reviewItem) {
  if (decision === "edited") {
    return { ...field, mapped_value: editedValue, confidence: 1 };
  }
  if (decision === "approved") {
    const mappedValue = Object.hasOwn(reviewItem || {}, "proposed_value")
      ? reviewItem.proposed_value
      : field.mapped_value;
    return {
      ...field,
      mapped_value: mappedValue,
      confidence: mappedValue == null ? field.confidence : 1,
    };
  }
  if (decision === "rejected") {
    return {
      ...field,
      mapped_profile_key: null,
      mapped_value: null,
      confidence: null,
    };
  }
  return field;
}

function applyDecisionToReviewItem(reviewItem, decision, editedValue) {
  const status = {
    approved: "APPROVED",
    edited: "EDITED",
    rejected: "REJECTED",
    needs_more_evidence: "NEEDS_MORE_EVIDENCE",
  }[decision];
  return {
    ...reviewItem,
    status: status || reviewItem.status,
    proposed_value: decision === "edited" ? editedValue : reviewItem.proposed_value,
  };
}
