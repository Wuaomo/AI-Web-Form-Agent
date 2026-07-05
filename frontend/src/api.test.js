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
    await api.createTask({
      url: "https://example.com/form",
      profile_id: 1,
    });

    assert.deepEqual(
      urls.map((entry) => entry.method),
      ["GET", "GET", "POST"],
    );
  } finally {
    clearApiCache();
    globalThis.fetch = originalFetch;
  }
});
