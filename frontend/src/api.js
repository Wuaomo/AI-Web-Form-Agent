export const API_BASE_URL =
  import.meta.env?.VITE_API_BASE_URL || "http://localhost:8000";

export function clearApiCache() {
  // Kept for tests and older callers; requests are intentionally uncached.
}

async function performRequest(path, options = {}) {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    let detail = null;
    try {
      const body = await response.json();
      detail = body.detail;
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (body.detail && typeof body.detail === "object") {
        message = body.detail.message || message;
      }
    } catch {
      // Keep the status-based message when the response has no JSON body.
    }
    const error = new Error(message);
    error.detail = detail;
    error.status = response.status;
    throw error;
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

async function performTextRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // Keep the status-based message when the response has no JSON body.
    }
    throw new Error(message);
  }

  return response.text();
}

async function request(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  return performRequest(path, {
    ...options,
    method,
  });
}

export const api = {
  health: () => request("/health"),
  listLlmProviders: () => request("/llm/providers"),
  listWorkflowTemplates: () => request("/workflows/templates"),
  startWorkflow: (taskId) =>
    request(`/workflows/${taskId}/start`, { method: "POST" }),
  getWorkflowState: (taskId) => request(`/workflows/${taskId}`),
  reviewWorkflow: (taskId, reviewData = {}) =>
    request(`/workflows/${taskId}/review`, {
      method: "POST",
      body: JSON.stringify(reviewData),
    }),
  runBenchmarks: (options = {}) =>
    request("/benchmarks/run", {
      method: "POST",
      body: JSON.stringify(options),
    }),
  listBenchmarkRuns: () => request("/benchmarks/runs"),
  getBenchmarkRun: (runId) => request(`/benchmarks/runs/${runId}`),
  getBenchmarkReport: (runId) => performTextRequest(`/benchmarks/runs/${runId}/report`),
  listWorkflowMemory: () => request("/admin/workflow-memory"),
  deleteWorkflowMemory: (memoryId) =>
    request(`/admin/workflow-memory/${memoryId}`, { method: "DELETE" }),

  listProfiles: () => request("/profiles"),
  createProfile: (profile) =>
    request("/profiles", {
      method: "POST",
      body: JSON.stringify(profile),
    }),
  updateProfile: (profileId, profile) =>
    request(`/profiles/${profileId}`, {
      method: "PUT",
      body: JSON.stringify(profile),
    }),
  deleteProfile: (profileId) =>
    request(`/profiles/${profileId}`, { method: "DELETE" }),

  createTask: (task) =>
    request("/tasks", {
      method: "POST",
      body: JSON.stringify(task),
    }),
  listTasks: () => request("/tasks"),
  getTask: (taskId) => request(`/tasks/${taskId}`),
  getTaskPlan: (taskId) => request(`/tasks/${taskId}/plan`),
  createTaskPlan: (taskId, goal) =>
    request(`/tasks/${taskId}/plan`, {
      method: "POST",
      body: JSON.stringify({ goal }),
    }),
  listTaskLogs: (taskId) => request(`/tasks/${taskId}/logs`),
  getTaskTrace: (taskId) => request(`/tasks/${taskId}/trace`),
  listTaskScreenshots: (taskId) => request(`/tasks/${taskId}/screenshots`),
  listApprovals: (options = {}) => {
    const params = new URLSearchParams();
    if (options.taskId) {
      params.set("task_id", options.taskId);
    }
    if (options.status) {
      params.set("status", options.status);
    }
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request(`/approvals${suffix}`);
  },
  approveApproval: (approvalId) =>
    request(`/approvals/${approvalId}/approve`, { method: "POST" }),
  rejectApproval: (approvalId) =>
    request(`/approvals/${approvalId}/reject`, { method: "POST" }),
  analyzeTask: (taskId) =>
      request(`/tasks/${taskId}/analyze`, { method: "POST" }),
    extractTaskPage: (taskId) =>
      request(`/tasks/${taskId}/extract-page`, { method: "POST" }),
    generateJobSummary: (taskId) =>
      request(`/tasks/${taskId}/job-summary`, { method: "POST" }),
    loginAndAnalyzeTask: (taskId) =>
      request(`/tasks/${taskId}/login-and-analyze`, { method: "POST" }),
  mapTaskFields: (taskId, options = {}) => {
    const params = new URLSearchParams();
    if (typeof options === "string") {
      params.set("mode", options);
    } else {
      if (options.mode) {
        params.set("mode", options.mode);
      }
      if (options.provider) {
        params.set("provider", options.provider);
      }
    }
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request(`/tasks/${taskId}/map-fields${suffix}`, { method: "POST" });
  },
  listTaskFields: (taskId) => request(`/tasks/${taskId}/fields`),
  updateTaskField: (taskId, fieldId, mapping) =>
    request(`/tasks/${taskId}/fields/${fieldId}`, {
      method: "PUT",
      body: JSON.stringify(mapping),
    }),
  confirmMapping: (taskId) =>
    request(`/tasks/${taskId}/confirm-mapping`, { method: "POST" }),
  fillTask: (taskId) => request(`/tasks/${taskId}/fill`, { method: "POST" }),
  confirmSubmit: (taskId) =>
    request(`/tasks/${taskId}/confirm-submit`, { method: "POST" }),
  getTaskLlmUsage: (taskId) => request(`/tasks/${taskId}/llm-usage`),
  listTaskCheckpoints: (taskId) => request(`/tasks/${taskId}/checkpoints`),
  getTaskVerificationResults: (taskId) => request(`/tasks/${taskId}/verification-results`),
  getTaskAgentReviews: (taskId) => request(`/tasks/${taskId}/agent-reviews`),
  runTaskAgentReviews: (taskId, roles = []) =>
    request(`/tasks/${taskId}/agent-reviews`, {
      method: "POST",
      body: JSON.stringify({ roles }),
    }),

  listJobs: () => request("/jobs"),
  getJob: (jobId) => request(`/jobs/${jobId}`),
  listTaskJobs: (taskId) => request(`/tasks/${taskId}/jobs`),
  cancelJob: (jobId) => request(`/jobs/${jobId}/cancel`, { method: "POST" }),
  listWorkerHeartbeats: () => request("/workers/heartbeats"),
};
