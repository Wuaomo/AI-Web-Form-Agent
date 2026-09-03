import assert from "node:assert/strict";
import test from "node:test";

import {
  applyFieldReviewDecision,
  applyFieldValueEdit,
} from "./reviewMappingActions.js";

function fakeApi() {
  const calls = [];
  return {
    calls,
    reviewTaskItem: async (taskId, itemId, decision) => {
      calls.push({ name: "reviewTaskItem", taskId, itemId, decision });
      return { id: `decision-${itemId}`, ...decision };
    },
    updateTaskField: async (taskId, fieldId, changes) => {
      calls.push({ name: "updateTaskField", taskId, fieldId, changes });
      return { id: fieldId, ...changes };
    },
  };
}

test("field edits use generic review item decisions when a proposal exists", async () => {
  const apiClient = fakeApi();
  const field = { id: 4, mapped_value: "old@example.com" };
  const reviewItemsByFieldId = new Map([
    [4, { id: "task-7-field-4", target_type: "form_field" }],
  ]);

  const result = await applyFieldValueEdit({
    apiClient,
    taskId: 7,
    field,
    mappedValue: "ada@example.com",
    reviewItemsByFieldId,
  });

  assert.equal(result.usedGenericReview, true);
  assert.deepEqual(apiClient.calls, [
    {
      name: "reviewTaskItem",
      taskId: 7,
      itemId: "task-7-field-4",
      decision: { decision: "edited", edited_value: "ada@example.com" },
    },
  ]);
});

test("generic field edits preserve blank strings as edited values", async () => {
  const apiClient = fakeApi();
  const field = { id: 4, mapped_value: "old@example.com" };
  const reviewItemsByFieldId = new Map([
    [4, { id: "task-7-field-4", target_type: "form_field" }],
  ]);

  await applyFieldValueEdit({
    apiClient,
    taskId: 7,
    field,
    mappedValue: "",
    reviewItemsByFieldId,
  });

  assert.deepEqual(apiClient.calls[0].decision, {
    decision: "edited",
    edited_value: "",
  });
});

test("field approve and reject use generic review item decisions when a proposal exists", async () => {
  const apiClient = fakeApi();
  const field = { id: 4, mapped_value: "ada@example.com" };
  const reviewItemsByFieldId = new Map([
    [4, { id: "task-7-field-4", target_type: "form_field" }],
  ]);

  await applyFieldReviewDecision({
    apiClient,
    taskId: 7,
    field,
    decision: "approved",
    reviewItemsByFieldId,
  });
  await applyFieldReviewDecision({
    apiClient,
    taskId: 7,
    field,
    decision: "rejected",
    reviewItemsByFieldId,
  });

  assert.deepEqual(
    apiClient.calls.map((call) => call.decision),
    [{ decision: "approved" }, { decision: "rejected" }],
  );
});

test("generic review decisions return updated review item state for proposal-backed rows", async () => {
  const apiClient = fakeApi();
  const field = { id: 4, mapped_value: "old@example.com" };
  const reviewItemsByFieldId = new Map([
    [
      4,
      {
        id: "task-7-field-4",
        target_type: "form_field",
        proposed_value: "proposal@example.com",
        status: "PENDING",
      },
    ],
  ]);

  const approved = await applyFieldReviewDecision({
    apiClient,
    taskId: 7,
    field,
    decision: "approved",
    reviewItemsByFieldId,
  });
  const edited = await applyFieldReviewDecision({
    apiClient,
    taskId: 7,
    field,
    decision: "edited",
    editedValue: "edited@example.com",
    reviewItemsByFieldId,
  });
  const rejected = await applyFieldReviewDecision({
    apiClient,
    taskId: 7,
    field,
    decision: "rejected",
    reviewItemsByFieldId,
  });

  assert.equal(approved.reviewItem.status, "APPROVED");
  assert.equal(approved.reviewItem.proposed_value, "proposal@example.com");
  assert.equal(edited.reviewItem.status, "EDITED");
  assert.equal(edited.reviewItem.proposed_value, "edited@example.com");
  assert.equal(rejected.reviewItem.status, "REJECTED");
});

test("field edits and rejects keep the legacy field update fallback", async () => {
  const apiClient = fakeApi();
  const field = { id: 4, mapped_value: "old@example.com" };

  await applyFieldValueEdit({
    apiClient,
    taskId: 7,
    field,
    mappedValue: "ada@example.com",
    reviewItemsByFieldId: new Map(),
  });
  await applyFieldReviewDecision({
    apiClient,
    taskId: 7,
    field,
    decision: "rejected",
    reviewItemsByFieldId: new Map(),
  });

  assert.deepEqual(apiClient.calls, [
    {
      name: "updateTaskField",
      taskId: 7,
      fieldId: 4,
      changes: { mapped_value: "ada@example.com" },
    },
    {
      name: "updateTaskField",
      taskId: 7,
      fieldId: 4,
      changes: { mapped_profile_key: null, mapped_value: null },
    },
  ]);
}
);
