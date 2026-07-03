import assert from "node:assert/strict";
import test from "node:test";

import { generateDebugReport } from "./debugReport.js";

const baseTask = {
  id: 7,
  url: "https://example.com/form",
  status: "MAPPING_READY",
  profile_id: 1,
  description: "Test task",
  form_fields: [
    { id: 1, field_type: "email", required: true, mapped_value: "ada@example.com" },
    { id: 2, field_type: "text", required: true, mapped_value: "" },
  ],
};

const profiles = [{ id: 1, profile_name: "Ada" }];

test("generateDebugReport includes checkpoints when provided", () => {
  const checkpoints = [
    { stage: "ANALYSIS", status: "SUCCESS", output: { field_count: 2 } },
    { stage: "MAPPING", status: "SUCCESS", output: { mapped_count: 1 } },
  ];

  const report = generateDebugReport(baseTask, profiles, [], null, [], checkpoints);

  assert.ok(report.includes("Checkpoints:"));
  assert.ok(report.includes("Stage: ANALYSIS | Status: SUCCESS"));
  assert.ok(report.includes('Output: {"field_count":2}'));
  assert.ok(report.includes("Stage: MAPPING | Status: SUCCESS"));
});

test("generateDebugReport shows failure evidence for failed checkpoints", () => {
  const checkpoints = [
    { stage: "ANALYSIS", status: "SUCCESS" },
    { stage: "MAPPING", status: "FAILED", failure_reason: "LLM_MAPPING_FAILED", error_message: "API timeout" },
  ];

  const report = generateDebugReport(baseTask, profiles, [], null, [], checkpoints);

  assert.ok(report.includes("Failure evidence:"));
  assert.ok(report.includes("[MAPPING] LLM_MAPPING_FAILED"));
  assert.ok(report.includes("API timeout"));
});

test("generateDebugReport handles checkpoints without output", () => {
  const checkpoints = [
    { stage: "ANALYSIS", status: "SUCCESS" },
  ];

  const report = generateDebugReport(baseTask, profiles, [], null, [], checkpoints);

  assert.ok(report.includes("Stage: ANALYSIS | Status: SUCCESS"));
});

test("generateDebugReport handles empty checkpoints list", () => {
  const report = generateDebugReport(baseTask, profiles, [], null, [], []);

  assert.ok(report.includes("=== Task Debug Report ==="));
  assert.ok(!report.includes("Checkpoints:"));
  assert.ok(!report.includes("Failure evidence:"));
});

test("generateDebugReport limits checkpoints to 10 entries", () => {
  const checkpoints = [];
  for (let i = 0; i < 15; i++) {
    checkpoints.push({ stage: `STAGE_${i}`, status: "SUCCESS" });
  }

  const report = generateDebugReport(baseTask, profiles, [], null, [], checkpoints);

  const stageCount = (report.match(/Stage: STAGE_/g) || []).length;
  assert.equal(stageCount, 10);
});