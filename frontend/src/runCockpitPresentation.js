function humanizeLabel(value) {
  if (!value) return "Unknown";
  const label = String(value)
    .replace(/[_-]/g, " ")
    .toLowerCase()
    .trim();
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function compactText(value, fallback = "") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  if (typeof value === "object") {
    return fallback || "provided";
  }
  const text = String(value).trim();
  return text.length > 140 ? `${text.slice(0, 137)}...` : text;
}

function formatMismatch(mismatch) {
  if (!mismatch || typeof mismatch !== "object") {
    return compactText(mismatch, "Verification mismatch");
  }

  const target =
    mismatch.target_ref ||
    mismatch.selector ||
    mismatch.field_label ||
    mismatch.id ||
    "Verification";
  if ("expected" in mismatch || "actual" in mismatch) {
    return `${target}: expected ${compactText(mismatch.expected, "empty")}, got ${compactText(mismatch.actual, "empty")}`;
  }
  if (mismatch.reason) {
    return `${target}: ${compactText(mismatch.reason)}`;
  }
  return compactText(target, "Verification mismatch");
}

function formatEvidenceItem(evidence) {
  if (!evidence || typeof evidence !== "object") {
    return compactText(evidence, "");
  }

  const source =
    evidence.source_title ||
    evidence.source_type ||
    evidence.title ||
    "Evidence";
  const section = evidence.section_title ? ` / ${evidence.section_title}` : "";
  const summary =
    evidence.quote_or_summary ||
    evidence.summary ||
    evidence.snippet ||
    "";
  return summary
    ? `${source}${section}: ${compactText(summary)}`
    : `${source}${section}`;
}

function verificationStatusLabel(verification, mismatchCount) {
  if (verification?.verified === true) return "Verified";
  if (mismatchCount === 1) return "1 mismatch";
  if (mismatchCount > 1) return `${mismatchCount} mismatches`;
  if (verification?.status) return humanizeLabel(verification.status);
  return "Not verified";
}

export function shouldShowRunCockpit(runtime) {
  return Boolean(
    runtime &&
      (runtime.planner_mode ||
        runtime.plan ||
        runtime.current_tool_call ||
        runtime.governance_decision),
  );
}

export function resolveRunCockpitRuntime(task, endpointRuntime = null) {
  if (endpointRuntime) return endpointRuntime;
  if (!task?.agent_runtime) return null;
  return {
    run_id: task.agent_run_id,
    ...task.agent_runtime,
  };
}

export function getRunCockpitPlanSteps(runtime) {
  const steps = runtime?.plan?.steps;
  if (!Array.isArray(steps)) return [];

  return steps.map((step, index) => ({
    id: step.step_id || step.id || `step-${index + 1}`,
    toolName: step.tool_name || step.tool || "Unknown tool",
    reason: step.reason || "",
  }));
}

export function getRunCockpitToolCalls(runtime) {
  const calls = runtime?.tool_calls;
  if (!Array.isArray(calls)) return [];

  return calls.map((call) => ({
    id: call.tool_call_id || call.id || "unknown-call",
    stepId: call.plan_step_id || "Unknown step",
    toolName: call.tool_name || "Unknown tool",
    status: humanizeLabel(call.status),
    governanceDecision: call.governance_decision
      ? humanizeLabel(call.governance_decision)
      : "Not evaluated",
    error: call.error || null,
    evidenceCount: Number(call.evidence_count || 0),
    proposalCount: Number(call.proposal_count || 0),
    verificationCandidateCount: Number(call.verification_candidate_count || 0),
  }));
}

export function getRunCockpitVerificationDetails(runtime) {
  const verification = runtime?.verification_result;
  const mismatches = Array.isArray(verification?.mismatches)
    ? verification.mismatches
    : [];
  const evidence = Array.isArray(verification?.evidence_items)
    ? verification.evidence_items
    : Array.isArray(verification?.evidence)
      ? verification.evidence
      : [];
  const mismatchCount = mismatches.length;

  return {
    statusLabel: verificationStatusLabel(verification, mismatchCount),
    mismatchCount,
    mismatches: mismatches.slice(0, 3).map(formatMismatch),
    evidenceItems: evidence.slice(0, 3).map(formatEvidenceItem).filter(Boolean),
  };
}

export function buildRunCockpitSummary(runtime) {
  const governance = runtime?.governance_decision || null;
  const verification = runtime?.verification_result || {};
  const mismatches = Array.isArray(verification.mismatches)
    ? verification.mismatches.length
    : 0;

  return {
    status: humanizeLabel(runtime?.status),
    plannerMode: humanizeLabel(runtime?.planner_mode),
    currentTool:
      runtime?.current_tool_call?.tool_name ||
      runtime?.current_tool_call?.tool ||
      "None",
    governanceDecision: governance?.decision
      ? humanizeLabel(governance.decision)
      : "Not evaluated",
    governanceReason: governance?.reason || "",
    toolResultCount: Number(runtime?.tool_result_count || 0),
    verificationSummary: verificationStatusLabel(verification, mismatches),
    error: runtime?.error || null,
  };
}
