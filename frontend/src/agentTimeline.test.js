import assert from "node:assert/strict";
import test from "node:test";

import { buildAgentTimeline } from "./agentTimeline.js";

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
