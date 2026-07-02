const nonFillableFieldTypes = new Set(["button", "submit", "reset", "image", "file"]);

const WORKFLOW_NODES = [
  { id: "created", label: "Created" },
  { id: "analyze", label: "Analyze" },
  { id: "map", label: "Map fields" },
  { id: "review", label: "Review mapping" },
  { id: "confirm", label: "Confirm mapping" },
  { id: "fill", label: "Fill form" },
  { id: "approve", label: "Waiting approval" },
  { id: "submit", label: "Submit" },
  { id: "completed", label: "Completed" },
];

function getWorkflowTimeline(task) {
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

  function setUpTo(nodeId, state) {
    const idx = nodes.findIndex((n) => n.id === nodeId);
    for (let i = 0; i <= idx; i++) {
      if (nodes[i].state === "pending") {
        nodes[i].state = state;
      }
    }
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
      setState("map", "success");
      setState("review", "active");
      break;

    case "READY_TO_FILL":
      setState("created", "success");
      setState("analyze", "success");
      setState("map", "success");
      setState("review", "success");
      setState("confirm", "success");
      setState("fill", "pending");
      break;

    case "FILLING":
      setState("created", "success");
      setState("analyze", "success");
      setState("map", "success");
      setState("review", "success");
      setState("confirm", "success");
      setState("fill", "active");
      break;

    case "WAITING_APPROVAL":
      setState("created", "success");
      setState("analyze", "success");
      setState("map", "success");
      setState("review", "success");
      setState("confirm", "success");
      setState("fill", "success");
      setState("approve", "active", "Review the filled form screenshot before final submission.");
      break;

    case "COMPLETED":
      setAllTo("success");
      break;

    case "FAILED":
      setAllTo("pending");
      setState("created", "success");

      if (task?.failed_step === "analyze" || status === "LOGIN_REQUIRED" || status === "ANALYZING") {
        setState("analyze", "failed");
      } else if (
        task?.failed_step === "map" ||
        task?.failed_step === "review" ||
        status === "MAPPING_READY"
      ) {
        setState("analyze", "success");
        setState("map", "success");
        setState("review", "failed");
      } else if (status === "READY_TO_FILL" || status === "FILLING") {
        setState("analyze", "success");
        setState("map", "success");
        setState("review", "success");
        setState("confirm", "success");
        setState("fill", "failed");
      } else if (status === "WAITING_APPROVAL") {
        setState("analyze", "success");
        setState("map", "success");
        setState("review", "success");
        setState("confirm", "success");
        setState("fill", "success");
        setState("approve", "failed");
      } else {
        const lastSuccessfulStep =
          task?.form_fields?.length > 0 ? "review" : task?.analyzed ? "analyze" : "created";
        setAllTo("pending");
        setState("created", "success");
        setUpTo(lastSuccessfulStep, "success");
        const nextStepIndex = nodes.findIndex((n) => n.id === lastSuccessfulStep) + 1;
        if (nextStepIndex < nodes.length && nextStepIndex < 8) {
          setState(nodes[nextStepIndex].id, "failed");
        }
      }
      break;

    default:
      setState("created", "success");
      break;
  }

  return nodes;
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

export { fieldDisplayName, getWorkflowTimeline, isFillableField };
