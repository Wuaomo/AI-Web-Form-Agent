import assert from "node:assert/strict";
import test from "node:test";

import {
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
