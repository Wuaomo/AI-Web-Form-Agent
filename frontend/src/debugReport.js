import { API_BASE_URL } from "./api";

export function generateDebugReport(task, profiles = [], screenshots = [], llmUsage = null, logs = []) {
  const profile = profiles.find((p) => p.id === task?.profile_id);
  const profileName = profile?.profile_name || task?.profile_id || "—";

  const lines = [];
  lines.push("=== Task Debug Report ===");
  lines.push("");

  if (task?.id) {
    lines.push(`Task ID: ${task.id}`);
  }
  if (task?.url) {
    lines.push(`URL: ${task.url}`);
  }
  if (task?.status) {
    lines.push(`Status: ${task.status}`);
  }
  lines.push(`Profile: ${profileName}`);
  if (task?.description) {
    lines.push(`Description: ${task.description}`);
  }

  const fieldCount = task?.form_fields?.length || 0;
  lines.push(`Field count: ${fieldCount}`);

  const requiredMissing = task?.form_fields?.filter(
    (f) => f.required && f.mapped_value === ""
  ) || [];
  if (requiredMissing.length > 0) {
    lines.push(`Required missing: ${requiredMissing.length}`);
    requiredMissing.forEach((field) => {
      const label = field.field_label || field.label || field.name || field.selector;
      lines.push(`  - ${label}`);
    });
  }

  if (screenshots.length > 0) {
    const latestScreenshot = screenshots[screenshots.length - 1];
    const screenshotUrl = new URL(latestScreenshot.file_path, `${API_BASE_URL}/`).toString();
    lines.push("");
    lines.push("Latest screenshot:");
    lines.push(screenshotUrl);
  }

  if (llmUsage?.summary) {
    lines.push("");
    lines.push("LLM Usage:");
    lines.push(`  Requests: ${llmUsage.summary.request_count}`);
    lines.push(`  Total tokens: ${llmUsage.summary.total_tokens}`);
    lines.push(`  Cache hit rate: ${Math.round(llmUsage.summary.cache_hit_rate * 100)}%`);
    lines.push(`  Cache hit tokens: ${llmUsage.summary.cache_hit_tokens}`);
    lines.push(`  Cache miss tokens: ${llmUsage.summary.cache_miss_tokens}`);
  }

  if (logs.length > 0) {
    lines.push("");
    lines.push("Recent logs:");
    logs.slice(-10).forEach((log) => {
      lines.push(`  [${log.created_at}] ${log.action || "-"} | ${log.status || "-"} | ${log.message || "-"}`);
    });
  } else {
    lines.push("");
    lines.push("Recent logs: Not loaded (TODO: GET /tasks/{task_id}/logs)");
  }

  lines.push("");
  lines.push("=== End Report ===");

  return lines.join("\n");
}