import assert from "node:assert/strict";
import test from "node:test";

import {
  buildRunCockpitSummary,
  getRunCockpitPlanSteps,
  getRunCockpitToolCalls,
  getRunCockpitVerificationDetails,
  shouldShowRunCockpit,
} from "./runCockpitPresentation.js";

test("shouldShowRunCockpit recognizes generic governed runtime responses", () => {
  assert.equal(shouldShowRunCockpit(null), false);
  assert.equal(shouldShowRunCockpit({ status: "PAUSED" }), false);
  assert.equal(
    shouldShowRunCockpit({
      status: "PAUSED",
      planner_mode: "deterministic",
      plan: { steps: [] },
    }),
    true,
  );
});

test("getRunCockpitPlanSteps preserves generic plan step order", () => {
  const steps = getRunCockpitPlanSteps({
    plan: {
      steps: [
        { step_id: "inspect_page", tool_name: "extract_page_structure" },
        { step_id: "fill_values", tool: "fill_browser_fields" },
      ],
    },
  });

  assert.deepEqual(
    steps.map((step) => [step.id, step.toolName]),
    [
      ["inspect_page", "extract_page_structure"],
      ["fill_values", "fill_browser_fields"],
    ],
  );
});

test("buildRunCockpitSummary maps governed runtime fields into compact labels", () => {
  const summary = buildRunCockpitSummary({
    status: "PAUSED",
    planner_mode: "template_guided",
    current_tool_call: {
      tool_call_id: "call-1",
      tool_name: "fill_browser_fields",
      args: { field_id: 7 },
    },
    governance_decision: {
      decision: "REVIEW_REQUIRED",
      reason: "Browser writes require review.",
    },
    tool_result_count: 2,
    verification_result: { verified: true, mismatches: [] },
    error: null,
  });

  assert.deepEqual(summary, {
    status: "Paused",
    plannerMode: "Template guided",
    currentTool: "fill_browser_fields",
    governanceDecision: "Review required",
    governanceReason: "Browser writes require review.",
    toolResultCount: 2,
    verificationSummary: "Verified",
    error: null,
  });
});

test("buildRunCockpitSummary reads persisted generic verification status", () => {
  const summary = buildRunCockpitSummary({
    status: "COMPLETED",
    planner_mode: "deterministic",
    verification_result: {
      status: "VERIFIED",
      total: 2,
      verified: 2,
      failed: 0,
      skipped: 0,
      mismatches: [],
    },
  });

  assert.equal(summary.verificationSummary, "Verified");
});

test("buildRunCockpitSummary summarizes verification mismatches and errors", () => {
  const summary = buildRunCockpitSummary({
    status: "FAILED",
    planner_mode: "llm_structured",
    tool_result_count: 0,
    verification_result: { verified: false, mismatches: ["#email"] },
    error: "Planner output failed validation.",
  });

  assert.equal(summary.status, "Failed");
  assert.equal(summary.plannerMode, "Llm structured");
  assert.equal(summary.currentTool, "None");
  assert.equal(summary.governanceDecision, "Not evaluated");
  assert.equal(summary.toolResultCount, 0);
  assert.equal(summary.verificationSummary, "1 mismatch");
  assert.equal(summary.error, "Planner output failed validation.");
});

test("getRunCockpitToolCalls returns compact recent tool history", () => {
  const calls = getRunCockpitToolCalls({
    tool_calls: [
      {
        tool_call_id: "task-1:extract",
        plan_step_id: "extract",
        tool_name: "extract_form",
        status: "SUCCEEDED",
        governance_decision: "ALLOW",
      },
      {
        tool_call_id: "task-1:map",
        plan_step_id: "map",
        tool_name: "map_fields",
        status: "FAILED",
        governance_decision: "ALLOW",
        error: "Mapping failed.",
      },
    ],
  });

  assert.deepEqual(calls, [
    {
      id: "task-1:extract",
      stepId: "extract",
      toolName: "extract_form",
      status: "Succeeded",
      governanceDecision: "Allow",
      error: null,
      evidenceCount: 0,
      proposalCount: 0,
      verificationCandidateCount: 0,
    },
    {
      id: "task-1:map",
      stepId: "map",
      toolName: "map_fields",
      status: "Failed",
      governanceDecision: "Allow",
      error: "Mapping failed.",
      evidenceCount: 0,
      proposalCount: 0,
      verificationCandidateCount: 0,
    },
  ]);
});

test("getRunCockpitVerificationDetails summarizes verified runs", () => {
  const details = getRunCockpitVerificationDetails({
    verification_result: { verified: true, mismatches: [] },
  });

  assert.deepEqual(details, {
    statusLabel: "Verified",
    mismatchCount: 0,
    mismatches: [],
    evidenceItems: [],
  });
});

test("getRunCockpitVerificationDetails reads persisted generic verification status", () => {
  const details = getRunCockpitVerificationDetails({
    verification_result: {
      status: "PARTIAL",
      total: 2,
      verified: 1,
      failed: 0,
      skipped: 1,
      mismatches: [],
    },
  });

  assert.equal(details.statusLabel, "Partial");
  assert.equal(details.mismatchCount, 0);
});

test("getRunCockpitVerificationDetails returns compact mismatches", () => {
  const details = getRunCockpitVerificationDetails({
    verification_result: {
      verified: false,
      mismatches: [
        { target_ref: "#email", expected: "me@example.com", actual: "" },
        "#phone",
        { selector: "#name", reason: "selector_not_found" },
        "#hidden-debug-field",
      ],
    },
  });

  assert.equal(details.statusLabel, "4 mismatches");
  assert.equal(details.mismatchCount, 4);
  assert.deepEqual(details.mismatches, [
    "#email: expected me@example.com, got empty",
    "#phone",
    "#name: selector_not_found",
  ]);
});

test("getRunCockpitVerificationDetails returns compact evidence items", () => {
  const details = getRunCockpitVerificationDetails({
    verification_result: {
      verified: true,
      evidence_items: [
        {
          source_title: "Post-fill DOM check",
          section_title: "Email field",
          quote_or_summary: "The email input matched the approved value.",
          output_json: { raw: "do not expose" },
        },
        {
          source_type: "verification",
          quote_or_summary: "Screenshot captured after fill.",
        },
        {
          source_title: "Extra evidence",
          quote_or_summary: "Hidden in the UI slice.",
        },
        {
          source_title: "Debug evidence",
          quote_or_summary: "Also hidden.",
        },
      ],
      output_json: { raw: "do not expose" },
    },
  });

  assert.deepEqual(details.evidenceItems, [
    "Post-fill DOM check / Email field: The email input matched the approved value.",
    "verification: Screenshot captured after fill.",
    "Extra evidence: Hidden in the UI slice.",
  ]);
  assert.equal(JSON.stringify(details).includes("output_json"), false);
  assert.equal(JSON.stringify(details).includes("do not expose"), false);
});

test("getRunCockpitVerificationDetails handles missing verification", () => {
  const details = getRunCockpitVerificationDetails({});

  assert.deepEqual(details, {
    statusLabel: "Not verified",
    mismatchCount: 0,
    mismatches: [],
    evidenceItems: [],
  });
});
