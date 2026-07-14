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
});

