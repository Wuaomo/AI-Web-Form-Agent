import assert from "node:assert/strict";
import test from "node:test";

import {
  getVisibleRunSummaryItems,
  getTaskRunSummary,
  getTaskRunState,
  isFillableField,
} from "./taskRunState.js";

const baseTask = {
  id: 7,
  status: "MAPPING_READY",
  form_fields: [
    {
      id: 1,
      field_type: "email",
      required: true,
      mapped_value: "ada@example.com",
    },
    {
      id: 2,
      field_type: "text",
      required: true,
      mapped_value: "",
    },
    {
      id: 3,
      field_type: "submit",
      required: false,
      mapped_value: null,
    },
  ],
};

test("isFillableField excludes form controls that should not receive values", () => {
  assert.equal(isFillableField({ field_type: "email" }), true);
  assert.equal(isFillableField({ field_type: "file" }), false);
  assert.equal(isFillableField({ field_type: "submit" }), false);
});

test("getTaskRunSummary counts found, mapped, missing, and skipped fields", () => {
  assert.deepEqual(getTaskRunSummary(baseTask), {
    totalFields: 3,
    mappedFields: 1,
    missingRequiredFields: 1,
    skippedFields: 1,
  });
});

test("getVisibleRunSummaryItems hides skipped fields from the user summary", () => {
  assert.deepEqual(getVisibleRunSummaryItems(baseTask), [
    { key: "totalFields", label: "Fields found", value: 3 },
    { key: "mappedFields", label: "Mapped", value: 1 },
    { key: "missingRequiredFields", label: "Need input", value: 1 },
  ]);
});

test("getTaskRunState exposes one primary user action for each task status", () => {
  assert.equal(
    getTaskRunState({ ...baseTask, status: "CREATED" }).primaryAction,
    "prepare",
  );
  assert.equal(
    getTaskRunState({ ...baseTask, status: "LOGIN_REQUIRED" }).primaryAction,
    "login",
  );
  assert.equal(getTaskRunState(baseTask).primaryAction, "review");
  assert.equal(
    getTaskRunState({ ...baseTask, status: "READY_TO_FILL" }).primaryAction,
    "fill",
  );
  assert.equal(
    getTaskRunState({ ...baseTask, status: "WAITING_APPROVAL" }).primaryAction,
    "approve",
  );
  assert.equal(
    getTaskRunState({ ...baseTask, status: "COMPLETED" }).primaryAction,
    null,
  );
});

test("getTaskRunState uses user-facing status labels", () => {
  assert.equal(getTaskRunState(baseTask).statusLabel, "Needs review");
  assert.equal(
    getTaskRunState({ ...baseTask, status: "READY_TO_FILL" }).statusLabel,
    "Ready to fill",
  );
  assert.equal(
    getTaskRunState({ ...baseTask, status: "WAITING_APPROVAL" }).statusLabel,
    "Waiting for approval",
  );
});

test("getTaskRunState shows recovery-aware label for analysis failure", () => {
  const checkpoints = [
    { stage: "ANALYSIS", status: "FAILED" },
  ];
  const state = getTaskRunState({ ...baseTask, status: "FAILED" }, checkpoints);
  assert.equal(state.statusLabel, "Analysis failed");
  assert.equal(state.primaryAction, "prepare");
  assert.equal(state.primaryLabel, "Retry analysis");
});

test("getTaskRunState shows recovery-aware label for mapping failure", () => {
  const checkpoints = [
    { stage: "ANALYSIS", status: "SUCCESS" },
    { stage: "MAPPING", status: "FAILED" },
  ];
  const state = getTaskRunState({ ...baseTask, status: "FAILED" }, checkpoints);
  assert.equal(state.statusLabel, "Mapping failed");
  assert.equal(state.primaryAction, "map");
  assert.equal(state.primaryLabel, "Retry mapping");
});

test("getTaskRunState shows recovery-aware label for fill failure", () => {
  const checkpoints = [
    { stage: "ANALYSIS", status: "SUCCESS" },
    { stage: "MAPPING", status: "SUCCESS" },
    { stage: "FILL", status: "FAILED" },
  ];
  const state = getTaskRunState({ ...baseTask, status: "FAILED" }, checkpoints);
  assert.equal(state.statusLabel, "Fill failed");
  assert.equal(state.primaryAction, "fill");
  assert.equal(state.primaryLabel, "Retry fill");
});

test("getTaskRunState falls back to generic FAILED state when no checkpoint available", () => {
  const state = getTaskRunState({ ...baseTask, status: "FAILED" }, []);
  assert.equal(state.statusLabel, "Failed");
  assert.equal(state.primaryAction, "prepare");
});

test("getTaskRunState ignores checkpoints for non-FAILED status", () => {
  const checkpoints = [
    { stage: "ANALYSIS", status: "FAILED" },
  ];
  const state = getTaskRunState(baseTask, checkpoints);
  assert.equal(state.statusLabel, "Needs review");
  assert.equal(state.primaryAction, "review");
});
