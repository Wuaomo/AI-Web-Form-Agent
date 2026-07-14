import test from "node:test";
import assert from "node:assert/strict";

import {
  buildReviewGroups,
  computeAttentionSummary,
  formatConfidence,
  formatMappingSummary,
  formatSourceSuggestion,
  getFieldChoiceOptions,
  getSourceSuggestionsByFieldId,
  hasFieldChoiceOptions,
  isLowConfidence,
  isRequiredMissing,
  isReviewableField,
  isUnmapped,
  needsMappingReview,
  shouldShowAdvancedFieldDetails,
  shouldShowMappingSource,
  shouldShowProfileMemoryControl,
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

test("source suggestion helpers expose checkpoint evidence by field id", () => {
  const checkpoints = [
    {
      stage: "MAPPING",
      output: {
        source_suggestions: [
          {
            field_id: 10,
            source: "mock-security-policy.md",
            matched_section: "Encryption At Rest",
            status: "needs_review",
          },
        ],
      },
    },
  ];

  const suggestions = getSourceSuggestionsByFieldId(checkpoints);

  assert.equal(
    formatSourceSuggestion(suggestions.get(10)),
    "Source: mock-security-policy.md / Encryption At Rest (needs review)",
  );
  assert.equal(formatSourceSuggestion(null), "");
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

test("isRequiredMissing identifies required fields with empty mapped_value", () => {
  assert.equal(
    isRequiredMissing({
      field_type: "text",
      required: true,
      mapped_value: "",
    }),
    true,
  );
  assert.equal(
    isRequiredMissing({
      field_type: "text",
      required: true,
      mapped_value: "Alice",
    }),
    false,
  );
  assert.equal(
    isRequiredMissing({
      field_type: "text",
      required: false,
      mapped_value: "",
    }),
    false,
  );
  assert.equal(
    isRequiredMissing({
      field_type: "submit",
      required: true,
      mapped_value: "",
    }),
    false,
  );
});

test("isLowConfidence identifies fields with confidence below 0.75", () => {
  assert.equal(isLowConfidence({ confidence: 0.74 }), true);
  assert.equal(isLowConfidence({ confidence: 0.75 }), false);
  assert.equal(isLowConfidence({ confidence: 0.5 }), true);
  assert.equal(isLowConfidence({ confidence: 1 }), false);
  assert.equal(isLowConfidence({ confidence: null }), false);
  assert.equal(isLowConfidence({ confidence: undefined }), false);
});

test("isLowConfidence ignores non-reviewable fields", () => {
  assert.equal(
    isLowConfidence({
      field_type: "submit",
      confidence: 0.2,
    }),
    false,
  );

  assert.equal(
    isLowConfidence({
      field_type: "file",
      confidence: 0.2,
    }),
    false,
  );

  assert.equal(
    isLowConfidence({
      field_type: "text",
      confidence: 0.2,
    }),
    true,
  );
});

test("computeAttentionSummary does not include non-reviewable low confidence fields", () => {
  const summary = computeAttentionSummary([
    {
      id: 1,
      field_type: "submit",
      required: false,
      mapped_value: "",
      mapped_profile_key: "",
      confidence: 0.1,
    },
    {
      id: 2,
      field_type: "text",
      required: false,
      mapped_value: "",
      mapped_profile_key: "email",
      confidence: 0.6,
    },
  ]);

  assert.deepEqual(summary.lowConfidence.map((field) => field.id), [2]);
});

test("isUnmapped identifies optional fillable fields with no mapping", () => {
  assert.equal(
    isUnmapped({
      field_type: "text",
      required: false,
      mapped_profile_key: "",
      mapped_value: "",
    }),
    true,
  );
  assert.equal(
    isUnmapped({
      field_type: "text",
      required: false,
      mapped_profile_key: "email",
      mapped_value: "",
    }),
    false,
  );
  assert.equal(
    isUnmapped({
      field_type: "text",
      required: false,
      mapped_profile_key: "",
      mapped_value: "manual value",
    }),
    false,
  );
  assert.equal(
    isUnmapped({
      field_type: "text",
      required: true,
      mapped_profile_key: "",
      mapped_value: "",
    }),
    false,
  );
  assert.equal(
    isUnmapped({
      field_type: "submit",
      required: false,
      mapped_profile_key: "",
      mapped_value: "",
    }),
    false,
  );
});

test("computeAttentionSummary categorizes fields with deduplication", () => {
  const fields = [
    {
      id: 1,
      field_type: "text",
      field_label: "Name",
      required: true,
      mapped_value: "",
      confidence: 0.5,
    },
    {
      id: 2,
      field_type: "text",
      field_label: "Email",
      required: false,
      mapped_value: "",
      confidence: 0.7,
      mapped_profile_key: "",
    },
    {
      id: 3,
      field_type: "text",
      field_label: "Phone",
      required: false,
      mapped_value: "",
      confidence: null,
      mapped_profile_key: "",
    },
    {
      id: 4,
      field_type: "text",
      field_label: "Address",
      required: false,
      mapped_value: "123 Street",
      confidence: 0.8,
      mapped_profile_key: "",
    },
    {
      id: 5,
      field_type: "submit",
      field_label: "Submit",
      required: false,
      mapped_value: "",
      mapped_profile_key: "",
    },
  ];

  const summary = computeAttentionSummary(fields);

  assert.equal(summary.requiredMissing.length, 1);
  assert.equal(summary.requiredMissing[0].id, 1);

  assert.equal(summary.lowConfidence.length, 1);
  assert.equal(summary.lowConfidence[0].id, 2);

  assert.equal(summary.unmapped.length, 1);
  assert.equal(summary.unmapped[0].id, 3);
});

test("computeAttentionSummary handles empty fields list", () => {
  const summary = computeAttentionSummary([]);
  assert.equal(summary.requiredMissing.length, 0);
  assert.equal(summary.lowConfidence.length, 0);
  assert.equal(summary.unmapped.length, 0);
});

test("computeAttentionSummary handles fields with null confidence for unmapped", () => {
  const fields = [
    {
      id: 1,
      field_type: "text",
      field_label: "Optional Field",
      required: false,
      mapped_value: "",
      confidence: null,
      mapped_profile_key: "",
    },
  ];

  const summary = computeAttentionSummary(fields);
  assert.equal(summary.unmapped.length, 1);
  assert.equal(summary.unmapped[0].id, 1);
});

test("advanced review controls stay hidden in the simplified user view", () => {
  assert.equal(shouldShowMappingSource(), false);
  assert.equal(shouldShowAdvancedFieldDetails(), false);
  assert.equal(shouldShowProfileMemoryControl(), false);
});
