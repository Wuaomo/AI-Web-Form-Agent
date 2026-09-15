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
    await api.createKnowledgeSource({
      filename: "security-policy.md",
      content: "# Security Policy",
    });
    await api.disableWorkflowMemory(4);
    await api.deleteKnowledgeSource(3);

    assert.deepEqual(
      urls.map((entry) => entry.method),
      ["GET", "GET", "GET", "GET", "POST", "POST", "POST", "POST", "POST", "POST", "DELETE"],
    );
  } finally {
    clearApiCache();
    globalThis.fetch = originalFetch;
  }
});

test("knowledge source API client uses correct paths", async () => {
  clearApiCache();
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || "GET", body: options.body });
    return jsonResponse({ ok: true });
  };

  try {
    await api.listKnowledgeSources();
    await api.createKnowledgeSource({
      filename: "security-policy.md",
      content: "# Security Policy",
    });
    await api.deleteKnowledgeSource(12);

    assert.equal(calls.length, 3);
    assert.ok(calls[0].url.endsWith("/knowledge-sources"));
    assert.equal(calls[0].method, "GET");
    assert.ok(calls[1].url.endsWith("/knowledge-sources"));
    assert.equal(calls[1].method, "POST");
    assert.equal(JSON.parse(calls[1].body).filename, "security-policy.md");
    assert.ok(calls[2].url.endsWith("/knowledge-sources/12"));
    assert.equal(calls[2].method, "DELETE");
  } finally {
    clearApiCache();
    globalThis.fetch = originalFetch;
  }
});

test("workflow runtime API client exposes governed workflow helpers only", async () => {
  clearApiCache();
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || "GET", body: options.body });
    return jsonResponse({ ok: true });
  };

  try {
    await api.startGovernedWorkflow(1, { plannerMode: "template_guided" });
    await api.getGovernedWorkflowState(1);

    assert.equal(api.startWorkflow, undefined);
    assert.equal(api.getWorkflowState, undefined);
    assert.equal(api.reviewWorkflow, undefined);
    assert.equal(api.extractTaskPage, undefined);
    assert.equal(api.generateJobSummary, undefined);
    assert.equal(calls.length, 2);
    assert.ok(calls[0].url.endsWith("/workflows/1/governed/start?planner_mode=template_guided"));
    assert.equal(calls[0].method, "POST");
    assert.ok(calls[1].url.endsWith("/workflows/1/governed"));
    assert.equal(calls[1].method, "GET");
  } finally {
    clearApiCache();
    globalThis.fetch = originalFetch;
  }
});

test("read-only workflow start uses governed deterministic path first", async () => {
  clearApiCache();
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || "GET" });
    return jsonResponse({ run_id: "task-7", status: "COMPLETED" });
  };

  try {
    await api.startReadOnlyWorkflow(7, "web_data_extract");
    await api.startReadOnlyWorkflow(8, "job_research_summary");

    assert.deepEqual(
      calls.map((call) => call.url.replace(/^.*?:\/\/[^/]+/, "")),
      [
        "/workflows/7/governed/start?planner_mode=deterministic",
        "/workflows/8/governed/start?planner_mode=deterministic",
      ],
    );
    assert.deepEqual(calls.map((call) => call.method), ["POST", "POST"]);
  } finally {
    clearApiCache();
    globalThis.fetch = originalFetch;
  }
});

test("read-only workflow start surfaces governed failure without legacy fallback", async () => {
  clearApiCache();
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || "GET" });
    if (url.endsWith("/workflows/7/governed/start?planner_mode=deterministic")) {
      return new Response(JSON.stringify({ detail: "governed start unavailable" }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      });
    }
    return jsonResponse({ status: "EXTRACTED" });
  };

  try {
    await assert.rejects(
      () => api.startReadOnlyWorkflow(7, "web_data_extract"),
      /governed start unavailable/,
    );

    assert.deepEqual(
      calls.map((call) => call.url.replace(/^.*?:\/\/[^/]+/, "")),
      ["/workflows/7/governed/start?planner_mode=deterministic"],
    );
    assert.deepEqual(calls.map((call) => call.method), ["POST"]);
  } finally {
    clearApiCache();
    globalThis.fetch = originalFetch;
  }
});

test("agent run API client uses primary read boundary", async () => {
  clearApiCache();
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || "GET" });
    return jsonResponse({ run_id: "task-7", status: "COMPLETED" });
  };

  try {
    const result = await api.getAgentRun("task-7");

    assert.deepEqual(result, { run_id: "task-7", status: "COMPLETED" });
    assert.equal(calls.length, 1);
    assert.ok(calls[0].url.endsWith("/agent-runs/task-7"));
    assert.equal(calls[0].method, "GET");
  } finally {
    clearApiCache();
    globalThis.fetch = originalFetch;
  }
});

test("agent run API client uses primary continue boundary", async () => {
  clearApiCache();
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || "GET" });
    return jsonResponse({ status: "WAITING_APPROVAL" });
  };

  try {
    const result = await api.continueAgentRun("task-7");

    assert.deepEqual(result, { status: "WAITING_APPROVAL" });
    assert.equal(calls.length, 1);
    assert.ok(calls[0].url.endsWith("/agent-runs/task-7/continue"));
    assert.equal(calls[0].method, "POST");
  } finally {
    clearApiCache();
    globalThis.fetch = originalFetch;
  }
});

test("agent run API client sends submit continue action payload", async () => {
  clearApiCache();
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || "GET", body: options.body });
    return jsonResponse({ status: "COMPLETED" });
  };

  try {
    const result = await api.continueAgentRun("task-7", { action: "submit_form" });

    assert.deepEqual(result, { status: "COMPLETED" });
    assert.equal(calls.length, 1);
    assert.ok(calls[0].url.endsWith("/agent-runs/task-7/continue"));
    assert.equal(calls[0].method, "POST");
    assert.equal(calls[0].body, JSON.stringify({ action: "submit_form" }));
  } finally {
    clearApiCache();
    globalThis.fetch = originalFetch;
  }
});

test("agent run proposal review API client uses primary review queue boundary", async () => {
  clearApiCache();
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || "GET", body: options.body });
    if (options.method === "POST") {
      return jsonResponse({ id: "decision-run-item" });
    }
    return jsonResponse([{ id: "run-item" }]);
  };

  try {
    const items = await api.listAgentRunReviewItems("task-7");
    const decision = await api.reviewAgentRunItem("task-7", "run-item", {
      decision: "approved",
    });

    assert.deepEqual(items, [{ id: "run-item" }]);
    assert.deepEqual(decision, { id: "decision-run-item" });
    assert.equal(calls.length, 2);
    assert.ok(calls[0].url.endsWith("/agent-runs/task-7/review-items"));
    assert.equal(calls[0].method, "GET");
    assert.ok(
      calls[1].url.endsWith("/agent-runs/task-7/review-items/run-item/decision"),
    );
    assert.equal(calls[1].method, "POST");
    assert.equal(JSON.parse(calls[1].body).decision, "approved");
  } finally {
    clearApiCache();
    globalThis.fetch = originalFetch;
  }
});

test("proposal review API client does not expose legacy task review helpers", () => {
  assert.equal(api.listTaskReviewItems, undefined);
  assert.equal(api.reviewTaskItem, undefined);
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
