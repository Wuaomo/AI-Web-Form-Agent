import assert from "node:assert/strict";
import test from "node:test";

import {
  continueRunCockpitRuntime,
  loadRunCockpitRuntime,
  startRunCockpitRuntime,
  submitRunCockpitRuntime,
} from "./runCockpitActions.js";

function fakeApi(overrides = {}) {
  const calls = [];
  return {
    calls,
    getAgentRun: async (runId) => {
      calls.push({ name: "getAgentRun", runId });
      return { run_id: runId, status: "AGENT_RUN", planner_mode: "deterministic" };
    },
    getGovernedWorkflowState: async (taskId) => {
      calls.push({ name: "getGovernedWorkflowState", taskId });
      return { status: "GOVERNED", planner_mode: "deterministic" };
    },
    startGovernedWorkflow: async (taskId, options) => {
      calls.push({ name: "startGovernedWorkflow", taskId, options });
      return { status: "STARTED", planner_mode: "deterministic" };
    },
    continueAgentRun: async (runId, options) => {
      calls.push({ name: "continueAgentRun", runId, options });
      return { status: "WAITING_APPROVAL" };
    },
    fillTask: async (taskId) => {
      calls.push({ name: "fillTask", taskId });
      return { status: "WAITING_APPROVAL" };
    },
    confirmSubmit: async (taskId) => {
      calls.push({ name: "confirmSubmit", taskId });
      return { status: "COMPLETED" };
    },
    ...overrides,
  };
}

test("run cockpit reads AgentRun compact state before governed workflow fallback", async () => {
  const apiClient = fakeApi();

  const runtime = await loadRunCockpitRuntime({
    apiClient,
    taskId: 7,
    task: {
      agent_run_id: "run-7",
      agent_runtime: { status: "TASK_FACADE", planner_mode: "deterministic" },
    },
  });

  assert.deepEqual(runtime, {
    run_id: "run-7",
    status: "AGENT_RUN",
    planner_mode: "deterministic",
  });
  assert.deepEqual(apiClient.calls, [{ name: "getAgentRun", runId: "run-7" }]);
});

test("run cockpit falls back to governed workflow when AgentRun read fails", async () => {
  const apiClient = fakeApi({
    getAgentRun: async (runId) => {
      apiClient.calls.push({ name: "getAgentRun", runId });
      throw new Error("missing run");
    },
  });

  const runtime = await loadRunCockpitRuntime({
    apiClient,
    taskId: 7,
    task: { agent_runtime: { run_id: "runtime-run-7", status: "TASK_FACADE" } },
  });

  assert.deepEqual(runtime, { status: "GOVERNED", planner_mode: "deterministic" });
  assert.deepEqual(apiClient.calls, [
    { name: "getAgentRun", runId: "runtime-run-7" },
    { name: "getGovernedWorkflowState", taskId: 7 },
  ]);
});

test("run cockpit reads governed workflow when no AgentRun id exists", async () => {
  const apiClient = fakeApi();

  const runtime = await loadRunCockpitRuntime({
    apiClient,
    taskId: 7,
    task: { status: "CREATED" },
  });

  assert.deepEqual(runtime, { status: "GOVERNED", planner_mode: "deterministic" });
  assert.deepEqual(apiClient.calls, [
    { name: "getGovernedWorkflowState", taskId: 7 },
  ]);
});

test("run cockpit falls back to task facade when primary reads fail", async () => {
  const apiClient = fakeApi({
    getAgentRun: async (runId) => {
      apiClient.calls.push({ name: "getAgentRun", runId });
      throw new Error("missing run");
    },
    getGovernedWorkflowState: async (taskId) => {
      apiClient.calls.push({ name: "getGovernedWorkflowState", taskId });
      throw new Error("missing governed state");
    },
  });

  const runtime = await loadRunCockpitRuntime({
    apiClient,
    taskId: 7,
    task: {
      agent_run_id: "run-7",
      agent_runtime: { status: "TASK_FACADE", planner_mode: "deterministic" },
    },
  });

  assert.deepEqual(runtime, {
    run_id: "run-7",
    status: "TASK_FACADE",
    planner_mode: "deterministic",
  });
});

test("started run cockpit state uses refreshed AgentRun runtime for follow-up navigation", async () => {
  const apiClient = fakeApi();

  const runtime = await startRunCockpitRuntime({
    apiClient,
    taskId: 7,
    task: { status: "CREATED" },
    refreshTaskData: async () => ({
      governedRuntime: {
        run_id: "run-7",
        status: "WAITING_REVIEW",
        planner_mode: "deterministic",
      },
    }),
  });

  assert.equal(runtime.status, "WAITING_REVIEW");
  assert.deepEqual(apiClient.calls, [
    {
      name: "startGovernedWorkflow",
      taskId: 7,
      options: { plannerMode: "deterministic" },
    },
  ]);
});

test("continue run cockpit uses AgentRun boundary when run id exists", async () => {
  const apiClient = fakeApi();

  const result = await continueRunCockpitRuntime({
    apiClient,
    taskId: 7,
    task: { agent_runtime: { run_id: "run-7" } },
  });

  assert.deepEqual(result, { status: "WAITING_APPROVAL" });
  assert.deepEqual(apiClient.calls, [
    { name: "continueAgentRun", runId: "run-7", options: undefined },
  ]);
});

test("continue run cockpit falls back to legacy fill without run id", async () => {
  const apiClient = fakeApi();

  const result = await continueRunCockpitRuntime({
    apiClient,
    taskId: 7,
    task: { status: "READY_TO_FILL" },
  });

  assert.deepEqual(result, { status: "WAITING_APPROVAL" });
  assert.deepEqual(apiClient.calls, [{ name: "fillTask", taskId: 7 }]);
});

test("submit run cockpit uses AgentRun continue boundary when run id exists", async () => {
  const apiClient = fakeApi();

  const result = await submitRunCockpitRuntime({
    apiClient,
    taskId: 7,
    task: { agent_runtime: { run_id: "run-7" } },
  });

  assert.deepEqual(result, { status: "WAITING_APPROVAL" });
  assert.deepEqual(apiClient.calls, [
    { name: "continueAgentRun", runId: "run-7", options: { action: "submit_form" } },
  ]);
});

test("submit run cockpit falls back to legacy confirm submit without run id", async () => {
  const apiClient = fakeApi();

  const result = await submitRunCockpitRuntime({
    apiClient,
    taskId: 7,
    task: { status: "WAITING_APPROVAL" },
  });

  assert.deepEqual(result, { status: "COMPLETED" });
  assert.deepEqual(apiClient.calls, [{ name: "confirmSubmit", taskId: 7 }]);
});
