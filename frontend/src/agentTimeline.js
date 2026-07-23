import { fieldDisplayName, isReviewableField } from "./reviewMappingPresentation.js";

const WORKFLOW_NODES = [
  { id: "created", label: "Created" },
  { id: "analyze", label: "Analyze page" },
  { id: "extract", label: "Extract questions" },
  { id: "retrieve", label: "Retrieve evidence" },
  { id: "suggest", label: "Suggest answers" },
  { id: "review", label: "Review mappings" },
  { id: "fill", label: "Fill browser" },
  { id: "verify", label: "Verify result" },
  { id: "approve", label: "Await submission approval" },
  { id: "completed", label: "Completed" },
];

function latestFailedAction(logs) {
  return [...logs]
    .filter((log) => log.status === "FAILED")
    .sort((a, b) => {
      const timeDiff = new Date(b.created_at || 0) - new Date(a.created_at || 0);
      return timeDiff || (Number(b.id) || 0) - (Number(a.id) || 0);
    })[0]?.action;
}

function getWorkflowTimeline(task, logs = []) {
  const status = task?.status || "CREATED";

  const nodes = WORKFLOW_NODES.map((node) => ({
    ...node,
    state: "pending",
    helpText: null,
  }));

  function setState(nodeId, state, helpText = null) {
    const node = nodes.find((n) => n.id === nodeId);
    if (node) {
      node.state = state;
      if (helpText) {
        node.helpText = helpText;
      }
    }
  }

  function setAllTo(state) {
    nodes.forEach((node) => {
      node.state = state;
    });
  }

  switch (status) {
    case "CREATED":
      setState("created", "success");
      setState("analyze", "pending");
      break;

    case "ANALYZING":
      setState("created", "success");
      setState("analyze", "active");
      break;

    case "LOGIN_REQUIRED":
      setState("created", "success");
      setState("analyze", "blocked", "Log in in the browser window, then close it to continue.");
      break;

    case "LOGIN_IN_PROGRESS":
      setState("created", "success");
      setState("analyze", "blocked", "Finish login in the browser window, then close it.");
      break;

    case "MAPPING_READY":
      setState("created", "success");
      setState("analyze", "success");
      setState("extract", "success");
      setState("retrieve", "success");
      setState("suggest", "success");
      setState("review", "active", "Review suggested values before browser execution.");
      break;

    case "READY_TO_FILL":
      setState("created", "success");
      setState("analyze", "success");
      setState("extract", "success");
      setState("retrieve", "success");
      setState("suggest", "success");
      setState("review", "success");
      setState("fill", "pending");
      break;

    case "FILLING":
      setState("created", "success");
      setState("analyze", "success");
      setState("extract", "success");
      setState("retrieve", "success");
      setState("suggest", "success");
      setState("review", "success");
      setState("fill", "active");
      setState("verify", "pending");
      break;

    case "WAITING_APPROVAL":
      setState("created", "success");
      setState("analyze", "success");
      setState("extract", "success");
      setState("retrieve", "success");
      setState("suggest", "success");
      setState("review", "success");
      setState("fill", "success");
      setState("verify", "success");
      setState("approve", "active", "Review the screenshot before final submission.");
      break;

    case "COMPLETED":
      setAllTo("success");
      break;

    case "FAILED": {
      setAllTo("pending");
      setState("created", "success");

      const failedAction = latestFailedAction(logs);
      if (failedAction === "analyze_form" || failedAction === "manual_login" || failedAction === "resume_after_login") {
        setState("analyze", "failed");
      } else if (failedAction === "map_fields" || failedAction === "llm_map_fields") {
        setState("analyze", "success");
        setState("extract", "success");
        setState("retrieve", "success");
        setState("suggest", "failed");
      } else if (failedAction === "fill_form") {
        setState("analyze", "success");
        setState("extract", "success");
        setState("retrieve", "success");
        setState("suggest", "success");
        setState("review", "success");
        setState("fill", "failed");
      } else if (failedAction === "submit_form" || failedAction === "confirm_submit") {
        setState("analyze", "success");
        setState("extract", "success");
        setState("retrieve", "success");
        setState("suggest", "success");
        setState("review", "success");
        setState("fill", "success");
        setState("verify", "success");
        setState("approve", "failed");
      } else {
        const hasFields = (task?.form_fields || []).length > 0;
        setState("analyze", hasFields ? "success" : "failed");
        if (hasFields) {
          setState("extract", "success");
          setState("retrieve", "success");
          setState("suggest", "failed");
        }
      }
      break;
    }

    default:
      setState("created", "success");
      break;
  }

  return nodes;
}

function shouldShowWorkflowTimeline() {
  return false;
}

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

const isFillableField = isReviewableField;

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
      ? "Analyzing the page"
      : "Finished analyzing the page";
  }

  if (log.action === "extract_fields") {
    const fieldCount = count ?? fields.length;
    return `Extracted ${pluralize(fieldCount, "field")} from the page`;
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
      return `Applying ${pluralize(fieldCount, "mapped value")}`;
    }
    return "Applied values in the browser and paused before submission";
  }

  if (log.action === "confirm_submit") {
    return "You approved final submission";
  }

  if (log.action === "submit_form") {
    return "Submitted after your approval";
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

export {
  fieldDisplayName,
  getWorkflowTimeline,
  isFillableField,
  shouldShowWorkflowTimeline,
};
