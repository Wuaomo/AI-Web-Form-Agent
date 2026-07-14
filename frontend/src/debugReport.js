import { API_BASE_URL } from "./api.js";

function sourceSuggestionsFromCheckpoints(checkpoints = []) {
  return checkpoints.flatMap((checkpoint) => {
    const suggestions = checkpoint?.output?.source_suggestions;
    return Array.isArray(suggestions) ? suggestions : [];
  });
}

function safeCheckpointOutput(output) {
  if (!output || typeof output !== "object" || !Array.isArray(output.source_suggestions)) {
    return output;
  }
  return {
    ...output,
    source_suggestions: output.source_suggestions.map((suggestion) => {
      const { suggested_value, ...safeSuggestion } = suggestion;
      return safeSuggestion;
    }),
  };
}

export function generateDebugReport(task, profiles = [], screenshots = [], llmUsage = null, logs = [], checkpoints = [], verificationResults = []) {
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

  if (checkpoints.length > 0) {
    lines.push("");
    lines.push("Checkpoints:");
    checkpoints.slice(-10).forEach((cp) => {
      lines.push(`  Stage: ${cp.stage} | Status: ${cp.status}`);
      if (cp.failure_reason) {
        lines.push(`    Failure reason: ${cp.failure_reason}`);
      }
      if (cp.error_message) {
        lines.push(`    Error: ${cp.error_message}`);
      }
      if (cp.output && typeof cp.output === "object") {
        lines.push(`    Output: ${JSON.stringify(safeCheckpointOutput(cp.output))}`);
      }
    });
  }

  const sourceSuggestions = sourceSuggestionsFromCheckpoints(checkpoints);
  if (sourceSuggestions.length > 0) {
    lines.push("");
    lines.push("Suggestion evidence:");
    sourceSuggestions.forEach((suggestion) => {
      lines.push(`  Field: ${suggestion.field_label || suggestion.field_id || "Unknown field"}`);
      lines.push(`    Source: ${suggestion.source || "Unknown source"}`);
      if (suggestion.matched_section) {
        lines.push(`    Section: ${suggestion.matched_section}`);
      }
      if (suggestion.status) {
        lines.push(`    Status: ${suggestion.status}`);
      }
    });
  }

  const failedCheckpoints = checkpoints.filter((cp) => cp.status === "FAILED");
  if (failedCheckpoints.length > 0) {
    lines.push("");
    lines.push("Failure evidence:");
    failedCheckpoints.forEach((cp) => {
      lines.push(`  [${cp.stage}] ${cp.failure_reason || "Unknown failure"}`);
      if (cp.error_message) {
        lines.push(`    ${cp.error_message}`);
      }
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
    lines.push("Recent logs: None");
  }

  if (verificationResults.length > 0) {
    const verified = verificationResults.filter((r) => r.status === "VERIFIED").length;
    const failed = verificationResults.filter((r) => r.status === "FAILED").length;
    const skipped = verificationResults.filter((r) => r.status === "SKIPPED").length;

    lines.push("");
    lines.push("Verification results:");
    lines.push(`  Verified: ${verified}`);
    lines.push(`  Failed: ${failed}`);
    lines.push(`  Skipped: ${skipped}`);

    if (failed > 0) {
      lines.push("");
      lines.push("Verification failures:");
      verificationResults
        .filter((r) => r.status === "FAILED")
        .forEach((r) => {
          lines.push(`  Selector: ${r.selector}`);
          lines.push(`    Reason: ${r.reason || "Unknown"}`);
          if (r.message) {
            lines.push(`    Message: ${r.message}`);
          }
        });
    }
  }

  lines.push("");
  lines.push("=== End Report ===");

  return lines.join("\n");
}
