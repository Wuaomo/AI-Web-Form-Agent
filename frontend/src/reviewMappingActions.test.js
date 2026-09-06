import assert from "node:assert/strict";
import test from "node:test";

import {
  applyReviewItemDecision,
  applyFieldReviewDecision,
  applyFieldValueEdit,
  getReviewMappingRunId,
  loadReviewItemsForReviewMapping,
} from "./reviewMappingActions.js";

function fakeApi() {
  const calls = [];
  return {
    calls,
    reviewTaskItem: async (taskId, itemId, decision) => {
      calls.push({ name: "reviewTaskItem", taskId, itemId, decision });
      return { id: `decision-${itemId}`, ...decision };
    },
    listTaskReviewItems: async (taskId) => {
      calls.push({ name: "listTaskReviewItems", taskId });
      return [{ id: "task-review" }];
    },
    listAgentRunReviewItems: async (runId) => {
      calls.push({ name: "listAgentRunReviewItems", runId });
      return [{ id: "run-review" }];
    },
    reviewAgentRunItem: async (runId, itemId, decision) => {
      calls.push({ name: "reviewAgentRunItem", runId, itemId, decision });
      return { id: `decision-${itemId}`, ...decision };
    },
    updateTaskField: async (taskId, fieldId, changes) => {
      calls.push({ name: "updateTaskField", taskId, fieldId, changes });
      return { id: fieldId, ...changes };
    },
  };
}

test("review mapping resolves AgentRun review items before task fallback", async () => {
  const apiClient = fakeApi();

  const items = await loadReviewItemsForReviewMapping({
    apiClient,
    taskId: 7,
    task: { agent_run_id: "run-7" },
  });

  assert.deepEqual(items, [{ id: "run-review" }]);
  assert.deepEqual(apiClient.calls, [
    { name: "listAgentRunReviewItems", runId: "run-7" },
  ]);
});

test("review mapping falls back to task review items without a run id", async () => {
  const apiClient = fakeApi();

  assert.equal(
    getReviewMappingRunId({ agent_runtime: { run_id: "runtime-run-7" } }),
    "runtime-run-7",
  );

  await loadReviewItemsForReviewMapping({
    apiClient,
    taskId: 7,
    task: {},
  });

  assert.deepEqual(apiClient.calls, [{ name: "listTaskReviewItems", taskId: 7 }]);
});

test("review mapping falls back to task review items when AgentRun review fails", async () => {
  const apiClient = {
    ...fakeApi(),
    listAgentRunReviewItems: async (runId) => {
      apiClient.calls.push({ name: "listAgentRunReviewItems", runId });
      throw new Error("missing run");
    },
  };

  const items = await loadReviewItemsForReviewMapping({
    apiClient,
    taskId: 7,
    task: { agent_run_id: "run-7" },
  });

  assert.deepEqual(items, [{ id: "task-review" }]);
  assert.deepEqual(apiClient.calls, [
    { name: "listAgentRunReviewItems", runId: "run-7" },
    { name: "listTaskReviewItems", taskId: 7 },
  ]);
});

test("review item decisions prefer AgentRun review boundary with task fallback", async () => {
  const apiClient = fakeApi();
  const reviewItem = { id: "proposal-7", status: "PENDING" };

  await applyReviewItemDecision({
    apiClient,
    taskId: 7,
    runId: "run-7",
    reviewItem,
    decision: "approved",
  });

  assert.deepEqual(apiClient.calls, [
    {
      name: "reviewAgentRunItem",
      runId: "run-7",
      itemId: "proposal-7",
      decision: { decision: "approved" },
    },
  ]);
});

test("review item decisions fall back to task review when AgentRun review fails", async () => {
  const apiClient = {
    ...fakeApi(),
    reviewAgentRunItem: async (runId, itemId, decision) => {
      apiClient.calls.push({
        name: "reviewAgentRunItem",
        runId,
        itemId,
        decision,
      });
      throw new Error("missing run");
    },
  };
  const reviewItem = { id: "proposal-7", status: "PENDING" };

  await applyReviewItemDecision({
    apiClient,
    taskId: 7,
    runId: "run-7",
    reviewItem,
    decision: "approved",
  });

  assert.deepEqual(apiClient.calls, [
    {
      name: "reviewAgentRunItem",
      runId: "run-7",
      itemId: "proposal-7",
      decision: { decision: "approved" },
    },
    {
      name: "reviewTaskItem",
      taskId: 7,
      itemId: "proposal-7",
      decision: { decision: "approved" },
    },
  ]);
});

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

test("field edits prefer AgentRun review boundary when a run id exists", async () => {
  const apiClient = fakeApi();
  const field = { id: 4, mapped_value: "old@example.com" };
  const reviewItemsByFieldId = new Map([
    [4, { id: "run-7-field-4", target_type: "form_field" }],
  ]);

  await applyFieldValueEdit({
    apiClient,
    taskId: 7,
    runId: "run-7",
    field,
    mappedValue: "ada@example.com",
    reviewItemsByFieldId,
  });

  assert.deepEqual(apiClient.calls, [
    {
      name: "reviewAgentRunItem",
      runId: "run-7",
      itemId: "run-7-field-4",
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

test("non-field proposal decisions use generic review item API", async () => {
  const apiClient = fakeApi();
  const reviewItem = {
    id: "task-7-field-4-memory-mapping",
    target_type: "workflow_memory",
    proposed_value: "email",
    status: "PENDING",
  };

  const approved = await applyReviewItemDecision({
    apiClient,
    taskId: 7,
    reviewItem,
    decision: "approved",
  });
  const edited = await applyReviewItemDecision({
    apiClient,
    taskId: 7,
    reviewItem,
    decision: "edited",
    editedValue: "support_email",
  });
  const rejected = await applyReviewItemDecision({
    apiClient,
    taskId: 7,
    reviewItem,
    decision: "rejected",
  });

  assert.deepEqual(
    apiClient.calls.map((call) => call.decision),
    [
      { decision: "approved" },
      { decision: "edited", edited_value: "support_email" },
      { decision: "rejected" },
    ],
  );
  assert.equal(approved.reviewItem.status, "APPROVED");
  assert.equal(edited.reviewItem.proposed_value, "support_email");
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
