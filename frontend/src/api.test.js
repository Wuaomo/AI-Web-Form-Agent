import assert from "node:assert/strict";
import test from "node:test";

import { api, clearApiCache } from "./api.js";

function jsonResponse(body) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

test("GET requests always fetch fresh data", async () => {
  clearApiCache();
  const originalFetch = globalThis.fetch;
  let requestCount = 0;
  globalThis.fetch = async () => {
    requestCount += 1;
    return jsonResponse([{ id: requestCount, status: "CREATED" }]);
  };

  try {
    const firstResult = await api.listTasks();
    const secondResult = await api.listTasks();

    assert.equal(requestCount, 2);
    assert.deepEqual(firstResult, [{ id: 1, status: "CREATED" }]);
    assert.deepEqual(secondResult, [{ id: 2, status: "CREATED" }]);
  } finally {
    clearApiCache();
    globalThis.fetch = originalFetch;
  }
});

test("mutations use their configured HTTP method", async () => {
  clearApiCache();
  const originalFetch = globalThis.fetch;
  const urls = [];
  globalThis.fetch = async (url, options = {}) => {
    urls.push({ url, method: options.method || "GET" });
    return jsonResponse({ ok: true });
  };

  try {
    await api.listTasks();
    await api.getTaskTrace(7);
    await api.getTaskPlan(7);
    await api.listApprovals({ taskId: 7, status: "PENDING" });
    await api.createTask({
      url: "https://example.com/form",
      profile_id: 1,
    });
    await api.createTaskPlan(7, "Fill this internship application.");
    await api.approveApproval(9);
    await api.rejectApproval(9);

    assert.deepEqual(
      urls.map((entry) => entry.method),
      ["GET", "GET", "GET", "GET", "POST", "POST", "POST", "POST"],
    );
  } finally {
    clearApiCache();
    globalThis.fetch = originalFetch;
  }
});

test("workflow runtime API client uses correct paths", async () => {
  clearApiCache();
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || "GET", body: options.body });
    return jsonResponse({ ok: true });
  };

  try {
    await api.startWorkflow(1);
    await api.getWorkflowState(1);
    await api.reviewWorkflow(1, { decision: "approve_all", approvals: [] });

    assert.equal(calls.length, 3);
    assert.ok(calls[0].url.endsWith("/workflows/1/start"));
    assert.equal(calls[0].method, "POST");
    assert.ok(calls[1].url.endsWith("/workflows/1"));
    assert.equal(calls[1].method, "GET");
    assert.ok(calls[2].url.endsWith("/workflows/1/review"));
    assert.equal(calls[2].method, "POST");
    const reviewBody = JSON.parse(calls[2].body);
    assert.equal(reviewBody.decision, "approve_all");
  } finally {
    clearApiCache();
    globalThis.fetch = originalFetch;
  }
});

test("structured API errors preserve detail payload", async () => {
  clearApiCache();
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    jsonResponse({
      detail: { message: "Final submission requires approval", approval_id: 12 },
    });

  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({
        detail: { message: "Final submission requires approval", approval_id: 12 },
      }),
      {
        status: 409,
        headers: { "Content-Type": "application/json" },
      },
    );

  try {
    await assert.rejects(
      () => api.confirmSubmit(12),
      (error) =>
        error.message === "Final submission requires approval" &&
        error.detail.approval_id === 12 &&
        error.status === 409,
    );
  } finally {
    clearApiCache();
    globalThis.fetch = originalFetch;
  }
});
