import assert from "node:assert/strict";
import test from "node:test";

import { buildAgentTimeline, getWorkflowTimeline } from "./agentTimeline.js";

test("builds user-facing timeline entries from logs and fields", () => {
  const logs = [
    {
      id: 1,
      step: 1,
      action: "extract_fields",
      status: "SUCCESS",
      message: "Extracted and saved 4 form fields.",
      created_at: "2026-06-29T12:00:00Z",
    },
    {
      id: 2,
      step: 2,
      action: "fill_form",
      status: "STARTED",
      message: "Filling 2 mapped fields.",
      created_at: "2026-06-29T12:01:00Z",
    },
    {
      id: 3,
      step: 3,
      action: "login_required",
      status: "WAITING",
      message: "The target URL opened a login page.",
      created_at: "2026-06-29T12:02:00Z",
    },
  ];
  const fields = [
    {
      label: "Email",
      field_type: "email",
      required: true,
      mapped_value: "alex@example.com",
      mapped_profile_key: "email",
      selector: "#email",
      element_ref: "field_1",
    },
    {
      label: "Full name",
      field_type: "text",
      required: true,
      mapped_value: "Alex Wu",
      mapped_profile_key: "full_name",
      selector: "#name",
      element_ref: "field_2",
    },
    {
      label: "Graduation date",
      field_type: "date",
      required: true,
      mapped_value: "",
      mapped_profile_key: null,
      selector: "#graduation",
      element_ref: "field_3",
    },
    {
      label: "Upload resume",
      field_type: "file",
      required: false,
      mapped_value: null,
      mapped_profile_key: null,
      selector: "#resume",
      element_ref: "field_4",
    },
  ];

  const entries = buildAgentTimeline(logs, fields);

  assert.deepEqual(
    entries.map((entry) => entry.title),
    [
      "Found 4 form fields",
      "Mapped 2 fields from profile",
      "Needs your input: Graduation date",
      "Skipped 1 file field",
      "Filling 2 mapped fields",
      "Needs your input: log in to continue",
    ],
  );
  assert.equal(entries[0].details[0].label, "Action");
  assert.equal(entries[0].details[0].value, "extract_fields");
  assert.equal(entries[2].details.some((detail) => detail.value === "#graduation"), true);
});

test("getWorkflowTimeline for CREATED status", () => {
  const nodes = getWorkflowTimeline({ status: "CREATED" });
  assert.equal(nodes.find((n) => n.id === "created").state, "success");
  assert.equal(nodes.find((n) => n.id === "analyze").state, "pending");
});

test("getWorkflowTimeline for LOGIN_REQUIRED status", () => {
  const nodes = getWorkflowTimeline({ status: "LOGIN_REQUIRED" });
  assert.equal(nodes.find((n) => n.id === "created").state, "success");
  assert.equal(nodes.find((n) => n.id === "analyze").state, "blocked");
  assert.ok(nodes.find((n) => n.id === "analyze").helpText);
});

test("getWorkflowTimeline for READY_TO_FILL status", () => {
  const nodes = getWorkflowTimeline({ status: "READY_TO_FILL" });
  assert.equal(nodes.find((n) => n.id === "created").state, "success");
  assert.equal(nodes.find((n) => n.id === "analyze").state, "success");
  assert.equal(nodes.find((n) => n.id === "map").state, "success");
  assert.equal(nodes.find((n) => n.id === "review").state, "success");
  assert.equal(nodes.find((n) => n.id === "confirm").state, "success");
  assert.equal(nodes.find((n) => n.id === "fill").state, "pending");
});

test("getWorkflowTimeline for WAITING_APPROVAL status", () => {
  const nodes = getWorkflowTimeline({ status: "WAITING_APPROVAL" });
  assert.equal(nodes.find((n) => n.id === "fill").state, "success");
  assert.equal(nodes.find((n) => n.id === "approve").state, "active");
  assert.ok(nodes.find((n) => n.id === "approve").helpText);
});

test("getWorkflowTimeline for COMPLETED status", () => {
  const nodes = getWorkflowTimeline({ status: "COMPLETED" });
  nodes.forEach((node) => {
    assert.equal(node.state, "success", `${node.id} should be success`);
  });
});

test("getWorkflowTimeline for FAILED status", () => {
  const nodes = getWorkflowTimeline({ status: "FAILED", form_fields: [] });
  assert.equal(nodes.find((n) => n.id === "created").state, "success");
  assert.ok(["failed", "pending"].includes(nodes.find((n) => n.id === "analyze").state));
});

test("getWorkflowTimeline for MAPPING_READY does not claim mapping is complete by status alone", () => {
  const nodes = getWorkflowTimeline({ status: "MAPPING_READY", form_fields: [] });

  assert.equal(nodes.find((n) => n.id === "created").state, "success");
  assert.equal(nodes.find((n) => n.id === "analyze").state, "success");
  assert.equal(nodes.find((n) => n.id === "map").state, "active");
  assert.equal(nodes.find((n) => n.id === "review").state, "pending");
});

test("getWorkflowTimeline for MAPPING_READY without mapped fields", () => {
  const nodes = getWorkflowTimeline({
    status: "MAPPING_READY",
    form_fields: [
      { field_type: "text", mapped_value: "" },
    ],
  });
  assert.equal(nodes.find((n) => n.id === "created").state, "success");
  assert.equal(nodes.find((n) => n.id === "analyze").state, "success");
  assert.equal(nodes.find((n) => n.id === "map").state, "active");
  assert.equal(nodes.find((n) => n.id === "review").state, "pending");
});

test("getWorkflowTimeline for FAILED with analyze_form failure", () => {
  const nodes = getWorkflowTimeline(
    { status: "FAILED", form_fields: [] },
    [{ action: "analyze_form", status: "FAILED" }],
  );
  assert.equal(nodes.find((n) => n.id === "created").state, "success");
  assert.equal(nodes.find((n) => n.id === "analyze").state, "failed");
});

test("getWorkflowTimeline marks fill failed from failed fill_form log", () => {
  const nodes = getWorkflowTimeline(
    { status: "FAILED", form_fields: [{ id: 1, mapped_value: "Alex" }] },
    [{ id: 10, action: "fill_form", status: "FAILED", created_at: "2026-07-02T10:00:00Z" }],
  );

  assert.equal(nodes.find((n) => n.id === "confirm").state, "success");
  assert.equal(nodes.find((n) => n.id === "fill").state, "failed");
  assert.equal(nodes.find((n) => n.id === "approve").state, "pending");
});

test("getWorkflowTimeline marks submit failed from failed submit_form log", () => {
  const nodes = getWorkflowTimeline(
    { status: "FAILED", form_fields: [{ id: 1, mapped_value: "Alex" }] },
    [{ id: 11, action: "submit_form", status: "FAILED", created_at: "2026-07-02T10:01:00Z" }],
  );

  assert.equal(nodes.find((n) => n.id === "fill").state, "success");
  assert.equal(nodes.find((n) => n.id === "approve").state, "success");
  assert.equal(nodes.find((n) => n.id === "submit").state, "failed");
});

test("getWorkflowTimeline marks analyze failed from failed analyze_form log", () => {
  const nodes = getWorkflowTimeline(
    { status: "FAILED", form_fields: [] },
    [{ id: 12, action: "analyze_form", status: "FAILED", created_at: "2026-07-02T10:02:00Z" }],
  );

  assert.equal(nodes.find((n) => n.id === "created").state, "success");
  assert.equal(nodes.find((n) => n.id === "analyze").state, "failed");
  assert.equal(nodes.find((n) => n.id === "map").state, "pending");
});

test("getWorkflowTimeline for FAILED with extract_fields failure", () => {
  const nodes = getWorkflowTimeline(
    { status: "FAILED", form_fields: [] },
    [{ action: "extract_fields", status: "FAILED" }],
  );
  assert.equal(nodes.find((n) => n.id === "created").state, "success");
  assert.equal(nodes.find((n) => n.id === "analyze").state, "failed");
});

test("getWorkflowTimeline for FAILED with fill_form failure", () => {
  const nodes = getWorkflowTimeline(
    { status: "FAILED", form_fields: [{ field_type: "text", mapped_value: "test" }] },
    [
      { action: "analyze_form", status: "SUCCESS" },
      { action: "fill_form", status: "FAILED" },
    ],
  );
  assert.equal(nodes.find((n) => n.id === "created").state, "success");
  assert.equal(nodes.find((n) => n.id === "analyze").state, "success");
  assert.equal(nodes.find((n) => n.id === "map").state, "success");
  assert.equal(nodes.find((n) => n.id === "review").state, "success");
  assert.equal(nodes.find((n) => n.id === "confirm").state, "success");
  assert.equal(nodes.find((n) => n.id === "fill").state, "failed");
});

test("getWorkflowTimeline for FAILED with submit_form failure", () => {
  const nodes = getWorkflowTimeline(
    { status: "FAILED", form_fields: [{ field_type: "text", mapped_value: "test" }] },
    [
      { action: "analyze_form", status: "SUCCESS" },
      { action: "fill_form", status: "SUCCESS" },
      { action: "submit_form", status: "FAILED" },
    ],
  );
  assert.equal(nodes.find((n) => n.id === "created").state, "success");
  assert.equal(nodes.find((n) => n.id === "analyze").state, "success");
  assert.equal(nodes.find((n) => n.id === "map").state, "success");
  assert.equal(nodes.find((n) => n.id === "review").state, "success");
  assert.equal(nodes.find((n) => n.id === "confirm").state, "success");
  assert.equal(nodes.find((n) => n.id === "fill").state, "success");
  assert.equal(nodes.find((n) => n.id === "approve").state, "success");
  assert.equal(nodes.find((n) => n.id === "submit").state, "failed");
});

test("getWorkflowTimeline for FAILED with unknown failure action", () => {
  const nodes = getWorkflowTimeline(
    { status: "FAILED", form_fields: [], analyzed: true },
    [{ action: "unknown_action", status: "FAILED" }],
  );
  assert.equal(nodes.find((n) => n.id === "created").state, "success");
  assert.equal(nodes.find((n) => n.id === "analyze").state, "failed");
});

test("getWorkflowTimeline for FAILED without logs", () => {
  const nodes = getWorkflowTimeline({ status: "FAILED", form_fields: [], analyzed: true });
  assert.equal(nodes.find((n) => n.id === "created").state, "success");
  assert.equal(nodes.find((n) => n.id === "analyze").state, "failed");
});
