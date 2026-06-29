import test from "node:test";
import assert from "node:assert/strict";

import {
  buildReviewGroups,
  formatConfidence,
  formatMappingSummary,
  isReviewableField,
} from "./reviewMappingPresentation.js";

test("review queue includes information controls and excludes action controls", () => {
  assert.equal(isReviewableField({ field_type: "checkbox" }), true);
  assert.equal(isReviewableField({ field_type: "radio" }), true);
  assert.equal(isReviewableField({ field_type: "select" }), true);
  assert.equal(isReviewableField({ field_type: "textarea" }), true);
  assert.equal(isReviewableField({ field_type: "submit" }), false);
  assert.equal(isReviewableField({ field_type: "button" }), false);
});

test("buildReviewGroups groups fields by section before form title", () => {
  const groups = buildReviewGroups([
    {
      id: 1,
      form_title: "Application",
      section_title: "Personal information",
      field_label: "Full name",
      field_type: "text",
    },
    {
      id: 2,
      form_title: "Application",
      section_title: "Preferences",
      field_label: "Remote work",
      field_type: "checkbox",
    },
    {
      id: 3,
      form_title: "Application",
      section_title: "Preferences",
      field_label: "Work authorization",
      field_type: "radio",
    },
    {
      id: 4,
      form_title: "Application",
      field_label: "Submit",
      field_type: "submit",
    },
  ]);

  assert.deepEqual(
    groups.map((group) => ({
      title: group.title,
      fieldIds: group.fields.map((field) => field.id),
    })),
    [
      { title: "Personal information", fieldIds: [1] },
      { title: "Preferences", fieldIds: [2, 3] },
    ],
  );
});

test("formatMappingSummary describes agent source and value in user-facing text", () => {
  assert.equal(
    formatMappingSummary({
      mapped_profile_key: "full_name",
      mapped_value: "Alice Wang",
    }),
    'profile.full_name -> "Alice Wang"',
  );
  assert.equal(
    formatMappingSummary({ mapped_profile_key: null, mapped_value: "" }),
    "Not chosen yet",
  );
});

test("formatConfidence shows percentages and an unknown state", () => {
  assert.equal(formatConfidence(0.94), "94%");
  assert.equal(formatConfidence(1), "100%");
  assert.equal(formatConfidence(null), "Not scored");
});
