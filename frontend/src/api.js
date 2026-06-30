export const API_BASE_URL =
  import.meta.env?.VITE_API_BASE_URL || "http://localhost:8000";

const GET_CACHE_TTL_MS = 5000;
const responseCache = new Map();
const inFlightGetRequests = new Map();
let cacheVersion = 0;

export function clearApiCache() {
  responseCache.clear();
  inFlightGetRequests.clear();
  cacheVersion += 1;
}

function getCachedResponse(cacheKey) {
  const cached = responseCache.get(cacheKey);
  if (!cached) {
    return null;
  }
  if (cached.expiresAt <= Date.now()) {
    responseCache.delete(cacheKey);
    return null;
  }
  return cached.data;
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

async function request(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const canCache = method === "GET" && !options.body;
  const cacheKey = `${method}:${path}`;

  if (canCache) {
    const cached = getCachedResponse(cacheKey);
    if (cached !== null) {
      return cached;
    }

    const inFlight = inFlightGetRequests.get(cacheKey);
    if (inFlight) {
      return inFlight;
    }

    const requestVersion = cacheVersion;
    const promise = performRequest(path, options)
      .then((data) => {
        if (requestVersion === cacheVersion) {
          responseCache.set(cacheKey, {
            data,
            expiresAt: Date.now() + GET_CACHE_TTL_MS,
          });
        }
        return data;
      })
      .finally(() => {
        inFlightGetRequests.delete(cacheKey);
      });
    inFlightGetRequests.set(cacheKey, promise);
    return promise;
  }

  const result = await performRequest(path, {
    ...options,
    method,
  });
  clearApiCache();
  return result;
}

export const api = {
  health: () => request("/health"),
  listLlmProviders: () => request("/llm/providers"),

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
};
