export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
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
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // Keep the status-based message when the response has no JSON body.
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

export const api = {
  health: () => request("/health"),

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
  listTaskLogs: (taskId) => request(`/tasks/${taskId}/logs`),
  listTaskScreenshots: (taskId) => request(`/tasks/${taskId}/screenshots`),
  analyzeTask: (taskId) =>
    request(`/tasks/${taskId}/analyze`, { method: "POST" }),
  mapTaskFields: (taskId, mode) => {
    const suffix = mode ? `?mode=${encodeURIComponent(mode)}` : "";
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
};
