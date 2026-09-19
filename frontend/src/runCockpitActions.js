import {
  getRunCockpitRunId,
  resolveRunCockpitRuntime,
} from "./runCockpitPresentation.js";

export async function loadRunCockpitRuntime({ apiClient, taskId, task }) {
  const runId = getRunCockpitRunId(task);
  if (runId) {
    try {
      const agentRunRuntime = await apiClient.getAgentRun(runId);
      return resolveRunCockpitRuntime(task, null, agentRunRuntime);
    } catch {
      // Migration fallback: legacy task/workflow paths stay alive until parity.
    }
  }

  try {
    const governedRuntime = await apiClient.getGovernedWorkflowState(taskId);
    return resolveRunCockpitRuntime(task, governedRuntime);
  } catch {
    return resolveRunCockpitRuntime(task);
  }
}

export async function startRunCockpitRuntime({
  apiClient,
  taskId,
  task,
  refreshTaskData,
}) {
  const startRuntime = await apiClient.startGovernedWorkflow(taskId, {
    plannerMode: "deterministic",
  });
  const refreshed = refreshTaskData ? await refreshTaskData() : null;
  if (refreshed?.governedRuntime) return refreshed.governedRuntime;
  return resolveRunCockpitRuntime(refreshed?.task || task, startRuntime);
}

export async function continueRunCockpitRuntime({ apiClient, task }) {
  const runId = getRunCockpitRunId(task);
  if (!runId) {
    throw new Error("AgentRun id is required before browser-write actions. Restart the governed runtime and try again.");
  }
  return apiClient.continueAgentRun(runId);
}

export async function submitRunCockpitRuntime({ apiClient, task }) {
  const runId = getRunCockpitRunId(task);
  if (!runId) {
    throw new Error("AgentRun id is required before browser-write actions. Restart the governed runtime and try again.");
  }
  return apiClient.continueAgentRun(runId, { action: "submit_form" });
}
