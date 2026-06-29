const nonFillableFieldTypes = new Set(["button", "submit", "reset", "image", "file"]);

function pluralize(count, singular, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function parseCount(message) {
  const match = message?.match(/\d+/);
  return match ? Number(match[0]) : null;
}

function fieldType(field) {
  return (field.field_type || "").toLowerCase();
}

function isFillableField(field) {
  return !nonFillableFieldTypes.has(fieldType(field));
}

function fieldDisplayName(field) {
  return (
    field.field_label ||
    field.label ||
    field.name ||
    field.hint ||
    field.placeholder ||
    field.selector ||
    "Unnamed field"
  );
}

function mappedFields(fields) {
  return fields.filter((field) => isFillableField(field) && field.mapped_value);
}

function skippedFields(fields) {
  return fields.filter((field) => !isFillableField(field));
}

function missingRequiredFields(fields) {
  return fields.filter(
    (field) => field.required && isFillableField(field) && !field.mapped_value,
  );
}

function compactDetails(items) {
  return items.filter((item) => item.value !== null && item.value !== undefined && item.value !== "");
}

function logDetails(log) {
  return compactDetails([
    { label: "Action", value: log.action },
    { label: "Status", value: log.status },
    { label: "Step", value: log.step },
    { label: "Raw message", value: log.message },
  ]);
}

function fieldDetails(field) {
  return compactDetails([
    { label: "Field", value: fieldDisplayName(field) },
    { label: "Type", value: field.field_type },
    { label: "Profile key", value: field.mapped_profile_key },
    { label: "Selector", value: field.selector },
    { label: "Element ref", value: field.element_ref },
  ]);
}

function logTitle(log, fields) {
  const count = parseCount(log.message);

  if (log.status === "FAILED") {
    return log.message ? `Something went wrong: ${log.message}` : "Something went wrong";
  }

  if (log.action === "analyze_form") {
    return log.status === "STARTED"
      ? "Checking the page for forms"
      : "Finished checking the page";
  }

  if (log.action === "extract_fields") {
    const fieldCount = count ?? fields.length;
    return `Found ${pluralize(fieldCount, "form field")}`;
  }

  if (log.action === "login_required") {
    return "Needs your input: log in to continue";
  }

  if (log.action === "manual_login") {
    return log.status === "TIMEOUT"
      ? "Needs your input: login timed out"
      : "Waiting for you to finish login";
  }

  if (log.action === "resume_after_login") {
    return "Resumed after login";
  }

  if (log.action === "fill_form") {
    if (log.status === "STARTED") {
      const fieldCount = count ?? mappedFields(fields).length;
      return `Filling ${pluralize(fieldCount, "mapped field")}`;
    }
    return "Filled mapped fields and paused before submission";
  }

  if (log.action === "confirm_submit") {
    return "You approved final submission";
  }

  if (log.action === "submit_form") {
    return "Submitted the reviewed form";
  }

  return log.message || log.action || "Agent action";
}

function mappedSummaryEntry(fields, log) {
  const mapped = mappedFields(fields);
  if (mapped.length === 0) return null;

  return {
    id: `${log.id}-mapped-summary`,
    status: "SUCCESS",
    createdAt: log.created_at,
    title: `Mapped ${pluralize(mapped.length, "field")} from profile`,
    details: mapped.flatMap(fieldDetails),
  };
}

function missingInputEntries(fields, log) {
  return missingRequiredFields(fields).map((field) => ({
    id: `${log.id}-missing-${field.id || field.element_ref || field.selector}`,
    status: "WAITING",
    createdAt: log.created_at,
    title: `Needs your input: ${fieldDisplayName(field)}`,
    details: fieldDetails(field),
  }));
}

function skippedSummaryEntry(fields, log) {
  const skipped = skippedFields(fields);
  if (skipped.length === 0) return null;

  const types = [...new Set(skipped.map(fieldType).filter(Boolean))];
  const typeLabel =
    types.length === 1
      ? `${types[0]} ${skipped.length === 1 ? "field" : "fields"}`
      : "file/button fields";

  return {
    id: `${log.id}-skipped-summary`,
    status: "SKIPPED",
    createdAt: log.created_at,
    title: `Skipped ${skipped.length} ${typeLabel}`,
    details: skipped.flatMap(fieldDetails),
  };
}

function fieldSummaryEntries(fields, log) {
  if (fields.length === 0 || log.action !== "extract_fields" || log.status !== "SUCCESS") {
    return [];
  }

  return [
    mappedSummaryEntry(fields, log),
    ...missingInputEntries(fields, log),
    skippedSummaryEntry(fields, log),
  ].filter(Boolean);
}

export function buildAgentTimeline(logs, fields = []) {
  return logs.flatMap((log) => [
    {
      id: log.id,
      status: log.status,
      createdAt: log.created_at,
      title: logTitle(log, fields),
      details: logDetails(log),
    },
    ...fieldSummaryEntries(fields, log),
  ]);
}

export { fieldDisplayName, isFillableField };
