const STORAGE_KEY = "ai-web-form-agent.llmProvider";

export function getSavedLlmProvider(providers = []) {
  const savedProvider = window.localStorage.getItem(STORAGE_KEY) || "";
  return providers.some((provider) => provider.id === savedProvider)
    ? savedProvider
    : "";
}

export function saveLlmProvider(provider) {
  if (provider) {
    window.localStorage.setItem(STORAGE_KEY, provider);
  } else {
    window.localStorage.removeItem(STORAGE_KEY);
  }
}
