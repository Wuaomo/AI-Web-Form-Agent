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
