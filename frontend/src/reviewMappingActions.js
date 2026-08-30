export async function applyFieldValueEdit({
  apiClient,
  taskId,
  field,
  mappedValue,
  reviewItemsByFieldId,
}) {
  return applyFieldReviewDecision({
    apiClient,
    taskId,
    field,
    decision: "edited",
    editedValue: mappedValue,
    reviewItemsByFieldId,
  });
}

export async function applyFieldReviewDecision({
  apiClient,
  taskId,
  field,
  decision,
  editedValue,
  reviewItemsByFieldId,
}) {
  const reviewItem = reviewItemsByFieldId.get(field.id);
  if (reviewItem) {
    await apiClient.reviewTaskItem(
      taskId,
      reviewItem.id,
      buildReviewDecisionPayload(decision, editedValue),
    );
    return {
      usedGenericReview: true,
      field: applyDecisionToField(field, decision, editedValue),
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

function applyDecisionToField(field, decision, editedValue) {
  if (decision === "edited") {
    return { ...field, mapped_value: editedValue, confidence: 1 };
  }
  if (decision === "approved") {
    return {
      ...field,
      confidence: field.mapped_value == null ? field.confidence : 1,
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
