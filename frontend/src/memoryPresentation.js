export function memoryStatusLabel(item = {}) {
  return item.stale ? "Stale" : "Reviewed";
}

export function memorySourceLabel(item = {}) {
  return item.source_domain || "Local memory";
}

export function memoryProfileKeyLabel(item = {}) {
  if (item.value_kind === "questionnaire_answer") {
    return "Reviewed answer";
  }
  return item.mapped_profile_key
    ? `profile.${item.mapped_profile_key}`
    : "Unmapped";
}

export function memoryFieldPreview(item = {}) {
  const text = item.field_text || "";
  const firstLine = text.split("\n").find(Boolean) || "";
  return firstLine.replace(/^(label|question):\s*/i, "") || "Saved field";
}

