import test from "node:test";
import assert from "node:assert/strict";

import {
  buildReviewGroups,
  formatConfidence,
  formatMappingSummary,
  getFieldChoiceOptions,
  hasFieldChoiceOptions,
  isReviewableField,
  needsMappingReview,
  suggestProfileCustomKey,
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
  assert.equal(
    formatMappingSummary({
      mapped_profile_key: "custom:preferred_location",
      mapped_value: "Shanghai",
    }),
    'profile.custom.preferred_location -> "Shanghai"',
  );
});

test("suggestProfileCustomKey derives compact keys from field labels", () => {
  assert.equal(
    suggestProfileCustomKey({
      field_label: "Preferred work location",
    }),
    "preferred_work_location",
  );
  assert.equal(suggestProfileCustomKey({ selector: "#field" }), "field");
});

test("formatConfidence shows percentages and an unknown state", () => {
  assert.equal(formatConfidence(0.94), "94%");
  assert.equal(formatConfidence(1), "100%");
  assert.equal(formatConfidence(null), "Not scored");
});

test("field choice helpers expose structured select and radio options", () => {
  const field = {
    field_type: "radio",
    options: [
      { label: "Remote", value: "remote", selector: "#remote" },
      { label: "Office", value: "office", selector: "#office" },
    ],
  };

  assert.equal(hasFieldChoiceOptions(field), true);
  assert.deepEqual(getFieldChoiceOptions(field), [
    { label: "Remote", value: "remote" },
    { label: "Office", value: "office" },
  ]);
  assert.equal(hasFieldChoiceOptions({ field_type: "text", options: [] }), false);
});

test("needsMappingReview only highlights fields that need attention", () => {
  assert.equal(
    needsMappingReview({
      field_type: "text",
      required: true,
      mapped_value: "",
      confidence: 1,
    }),
    true,
  );
  assert.equal(
    needsMappingReview({
      field_type: "text",
      required: false,
      mapped_value: "Alice",
      confidence: 0.69,
    }),
    true,
  );
  assert.equal(
    needsMappingReview({
      field_type: "text",
      required: false,
      mapped_value: "Alice",
      confidence: 0.7,
    }),
    false,
  );
  assert.equal(
    needsMappingReview({
      field_type: "text",
      required: false,
      mapped_value: "Alice",
      confidence: 0.95,
    }),
    false,
  );
});
