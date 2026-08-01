import assert from "node:assert/strict";
import test from "node:test";

import {
  presentAgentStep,
  hasFailedSteps,
  hasPendingApproval,
  isStepCompleted,
  isStepFailed,
  isStepPending,
} from "./agentStepPresentation.js";

test("presentAgentStep converts tool names to user-readable labels", () => {
  const step = {
    step_id: "open_url",
    tool: "open_url",
    goal: "Open the target URL",
    status: "SUCCESS",
  };

  const presented = presentAgentStep(step);

  assert.equal(presented.toolLabel, "Open URL");
  assert.equal(presented.statusLabel, "Completed");
});

test("presentAgentStep labels page intake steps", () => {
  const presented = presentAgentStep({
    step_id: "page_intake",
    tool: "page_intake",
    status: "SUCCESS",
  });

  assert.equal(presented.toolLabel, "Page intake");
});

test("presentAgentStep handles all status types", () => {
  assert.equal(presentAgentStep({ status: "PENDING" }).statusLabel, "Pending");
  assert.equal(presentAgentStep({ status: "STARTED" }).statusLabel, "In progress");
  assert.equal(presentAgentStep({ status: "SUCCESS" }).statusLabel, "Completed");
  assert.equal(presentAgentStep({ status: "FAILED" }).statusLabel, "Failed");
});

test("presentAgentStep converts evidence types to user-readable labels", () => {
  const step = {
    step_id: "fill_form",
    tool: "fill_form",
    status: "SUCCESS",
    evidence: ["screenshot", "verification_results"],
  };

  const presented = presentAgentStep(step);

  assert.deepEqual(presented.evidenceLabels, ["Screenshot", "Verification"]);
});

test("presentAgentStep handles missing evidence gracefully", () => {
  const step = {
    step_id: "open_url",
    tool: "open_url",
    status: "SUCCESS",
  };

  const presented = presentAgentStep(step);

  assert.deepEqual(presented.evidenceLabels, []);
});

test("hasFailedSteps returns true when any step failed", () => {
  const steps = [
    { step_id: "open_url", status: "SUCCESS" },
    { step_id: "fill_form", status: "FAILED" },
    { step_id: "verify_fields", status: "PENDING" },
  ];

  assert.equal(hasFailedSteps(steps), true);
});

test("hasFailedSteps returns false when no steps failed", () => {
  const steps = [
    { step_id: "open_url", status: "SUCCESS" },
    { step_id: "fill_form", status: "SUCCESS" },
  ];

  assert.equal(hasFailedSteps(steps), false);
});

test("hasPendingApproval returns true when step awaits approval", () => {
  const steps = [
    { step_id: "open_url", status: "SUCCESS" },
    { step_id: "submit_form", status: "APPROVAL_PENDING" },
  ];

  assert.equal(hasPendingApproval(steps), true);
});

test("hasPendingApproval returns false when no approval pending", () => {
  const steps = [
    { step_id: "open_url", status: "SUCCESS" },
    { step_id: "submit_form", status: "SUCCESS" },
  ];

  assert.equal(hasPendingApproval(steps), false);
});

test("isStepCompleted returns true for SUCCESS status", () => {
  assert.equal(isStepCompleted({ status: "SUCCESS" }), true);
  assert.equal(isStepCompleted({ status: "FAILED" }), false);
});

test("isStepFailed returns true for FAILED status", () => {
  assert.equal(isStepFailed({ status: "FAILED" }), true);
  assert.equal(isStepFailed({ status: "SUCCESS" }), false);
});

test("isStepPending returns true for PENDING status", () => {
  assert.equal(isStepPending({ status: "PENDING" }), true);
  assert.equal(isStepPending({ status: "SUCCESS" }), false);
});

test("presentAgentStep formats timestamps correctly", () => {
  const step = {
    step_id: "open_url",
    tool: "open_url",
    status: "SUCCESS",
    started_at: "2026-07-25T10:30:00Z",
  };

  const presented = presentAgentStep(step);

  assert.ok(presented.startedAtFormatted);
  assert.ok(presented.startedAtFormatted.includes("7"));
});

test("presentAgentStep handles missing timestamps", () => {
  const step = {
    step_id: "open_url",
    tool: "open_url",
    status: "PENDING",
  };

  const presented = presentAgentStep(step);

  assert.equal(presented.startedAtFormatted, null);
});
