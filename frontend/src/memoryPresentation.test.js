import test from "node:test";
import assert from "node:assert/strict";

import {
  memoryFieldPreview,
  memoryProfileKeyLabel,
  memorySourceLabel,
  memoryStatusLabel,
} from "./memoryPresentation.js";

test("memory presentation helpers format reviewed memory rows", () => {
  const item = {
    source_domain: "example.com",
    mapped_profile_key: "github",
    field_text: "label: Portfolio URL\nname: portfolio",
    stale: true,
  };

  assert.equal(memorySourceLabel(item), "example.com");
  assert.equal(memoryProfileKeyLabel(item), "profile.github");
  assert.equal(memoryFieldPreview(item), "Portfolio URL");
  assert.equal(memoryStatusLabel(item), "Stale");
  assert.equal(memoryStatusLabel({ stale: false }), "Reviewed");
  assert.equal(memoryStatusLabel({ disabled_at: "2026-08-26T00:00:00Z" }), "Disabled");
});

test("memory presentation helpers format questionnaire answer memory rows", () => {
  const item = {
    value_kind: "questionnaire_answer",
    mapped_profile_key: "reviewed_answer",
    field_text: "question: Do you enforce MFA?\nanswer: Yes",
  };

  assert.equal(memoryProfileKeyLabel(item), "Reviewed answer");
  assert.equal(memoryFieldPreview(item), "Do you enforce MFA?");
});

