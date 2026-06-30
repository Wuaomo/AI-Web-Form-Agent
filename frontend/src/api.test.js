import assert from "node:assert/strict";
import test from "node:test";

import { api, clearApiCache } from "./api.js";

function jsonResponse(body) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

test("deduplicates and caches concurrent GET requests", async () => {
  clearApiCache();
  const originalFetch = globalThis.fetch;
  let requestCount = 0;
  globalThis.fetch = async () => {
    requestCount += 1;
    return jsonResponse([{ id: 1, status: "CREATED" }]);
  };

  try {
    const [firstResult, secondResult] = await Promise.all([
      api.listTasks(),
      api.listTasks(),
    ]);
    const cachedResult = await api.listTasks();

    assert.equal(requestCount, 1);
    assert.deepEqual(firstResult, [{ id: 1, status: "CREATED" }]);
    assert.deepEqual(secondResult, firstResult);
    assert.deepEqual(cachedResult, firstResult);
  } finally {
    clearApiCache();
    globalThis.fetch = originalFetch;
  }
});

test("clears cached GET responses after a successful mutation", async () => {
  clearApiCache();
  const originalFetch = globalThis.fetch;
  const urls = [];
  globalThis.fetch = async (url, options = {}) => {
    urls.push({ url, method: options.method || "GET" });
    return jsonResponse({ ok: true });
  };

  try {
    await api.listTasks();
    await api.createTask({
      url: "https://example.com/form",
      profile_id: 1,
    });
    await api.listTasks();

    assert.deepEqual(
      urls.map((entry) => entry.method),
      ["GET", "POST", "GET"],
    );
  } finally {
    clearApiCache();
    globalThis.fetch = originalFetch;
  }
});
