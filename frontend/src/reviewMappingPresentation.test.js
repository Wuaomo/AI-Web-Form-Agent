import test from "node:test";
import assert from "node:assert/strict";

import {
  buildReviewGroups,
  buildReviewQueueSummary,
  buildReviewQueueCompactItems,
  buildProposalBackedReviewFields,
  computeAttentionSummary,
  formatProposalTypeLabel,
  formatConfidence,
  formatMappingSummary,
  formatSourceSuggestion,
  getProposalReviewItemsByFieldId,
  getFieldSourceEvidence,
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

test("source suggestion helpers expose stale reviewed memory by field id", () => {
  const checkpoints = [
    {
      stage: "MAPPING",
      output: {
        retrieval_suggestions: [
          {
            field_id: 11,
            source_type: "reviewed_memory",
            source_id: 7,
            mapped_profile_key: "email",
            stale: true,
            governance_status: "stale_review_recommended",
          },
        ],
      },
    },
  ];

  const suggestions = getSourceSuggestionsByFieldId(checkpoints);

  assert.equal(
    formatSourceSuggestion(suggestions.get(11)),
    "Reviewed memory #7 -> profile.email (stale; review recommended)",
  );
});

test("proposal review helpers expose generic evidence by field id", () => {
  const items = [
    {
      id: "task-1-field-10",
      proposal_type: "answer",
      target_type: "form_field",
      target_ref: "10",
      proposed_value: "Yes. MFA is required.",
      evidence: [
        {
          source_type: "policy_doc",
          source_title: "mock-security-policy.md",
          section_title: "Access Control",
          quote_or_summary: "MFA is required for administrative access.",
        },
      ],
    },
    {
      id: "task-1-field-11",
      proposal_type: "memory_write",
      target_type: "workflow_memory",
      target_ref: "memory:email",
      proposed_value: "email",
      evidence: [],
    },
  ];

  const byFieldId = getProposalReviewItemsByFieldId(items);

  assert.equal(byFieldId.get(10).proposal_type, "answer");
  assert.equal(byFieldId.get(10).evidence[0].source_type, "policy_doc");
  assert.equal(byFieldId.has(11), false);
});

test("proposal-backed review fields prefer proposal value status and evidence", () => {
  const fields = [
    {
      id: 10,
      field_type: "text",
      mapped_value: "stale@example.com",
      confidence: 0.4,
    },
    {
      id: 11,
      field_type: "text",
      mapped_value: "legacy@example.com",
      confidence: 0.9,
    },
  ];
  const evidence = [{ id: "e-1", quote_or_summary: "Mapped from runtime." }];
  const reviewItemsByFieldId = new Map([
    [
      10,
      {
        id: "proposal-10",
        proposal_type: "field_value",
        status: "PENDING",
        proposed_value: "proposal@example.com",
        confidence: 0.88,
        evidence,
      },
    ],
  ]);

  const rows = buildProposalBackedReviewFields(fields, reviewItemsByFieldId);

  assert.equal(rows[0].mapped_value, "proposal@example.com");
  assert.equal(rows[0].confidence, 0.88);
  assert.equal(rows[0].review_status, "PENDING");
  assert.equal(rows[0].proposal_type, "field_value");
  assert.deepEqual(rows[0].proposal_evidence, evidence);
  assert.equal(rows[1].mapped_value, "legacy@example.com");
  assert.equal(rows[1].review_status, undefined);
});

test("field source evidence prefers compact proposal evidence before checkpoint fallback", () => {
  const proposalEvidence = [
    {
      id: "proposal-evidence",
      source_type: "policy_doc",
      quote_or_summary: "Compact proposal evidence.",
    },
  ];
  const proposalItemsByFieldId = new Map([
    [10, { evidence: proposalEvidence }],
  ]);
  const sourceSuggestionsByFieldId = new Map([
    [10, { source: "checkpoint.md", matched_section: "Fallback" }],
    [11, { source: "checkpoint.md", matched_section: "Fallback" }],
  ]);

  assert.deepEqual(
    getFieldSourceEvidence(
      10,
      proposalItemsByFieldId,
      sourceSuggestionsByFieldId,
    ),
    { type: "proposal", items: proposalEvidence },
  );
  assert.deepEqual(
    getFieldSourceEvidence(
      11,
      proposalItemsByFieldId,
      sourceSuggestionsByFieldId,
    ),
    {
      type: "suggestion",
      suggestion: { source: "checkpoint.md", matched_section: "Fallback" },
    },
  );
});

test("buildReviewQueueSummary counts generic proposal review states and evidence", () => {
  const summary = buildReviewQueueSummary([
    {
      proposal_type: "field_value",
      status: "PENDING",
      evidence: [{ id: "e-1" }],
    },
    {
      proposal_type: "answer",
      status: "APPROVED",
      evidence: [],
    },
    {
      proposal_type: "memory_write",
      status: "REJECTED",
      evidence: [{ id: "e-2" }, { id: "e-3" }],
    },
    {
      proposal_type: "field_value",
      status: "NEEDS_MORE_EVIDENCE",
      evidence: [],
    },
  ]);

  assert.deepEqual(summary, {
    total: 4,
    pending: 1,
    approved: 1,
    edited: 0,
    rejected: 1,
    needsMoreEvidence: 1,
    evidenceBacked: 2,
    byType: [
      { type: "field_value", label: "Field value", count: 2 },
      { type: "answer", label: "Answer", count: 1 },
      { type: "memory_write", label: "Memory write", count: 1 },
    ],
  });
});

test("buildReviewQueueCompactItems includes non-field proposals", () => {
  const items = buildReviewQueueCompactItems([
    {
      id: "task-1-field-10",
      proposal_type: "field_value",
      target_type: "form_field",
      target_ref: "10",
      proposed_value: "Ada",
      status: "PENDING",
    },
    {
      id: "task-1-field-10-memory-mapping",
      proposal_type: "memory_write",
      target_type: "workflow_memory",
      target_ref: "10",
      proposed_value: "email",
      status: "PENDING",
      risk_level: "medium",
      evidence: [{ id: "e-1" }],
    },
  ]);

  assert.deepEqual(items, [
    {
      id: "task-1-field-10-memory-mapping",
      label: "Memory write",
      proposalType: "memory_write",
      target: "workflow_memory:10",
      value: "email",
      status: "PENDING",
      riskLevel: "medium",
      canRequestEvidence: true,
      evidenceCount: 1,
    },
  ]);
});

test("buildReviewQueueCompactItems marks submit proposals as approval-owned", () => {
  const items = buildReviewQueueCompactItems([
    {
      id: "task-1-submit-12",
      proposal_type: "form_submit",
      target_type: "approval_request",
      target_ref: "12",
      proposed_value: {
        action: "submit_form",
        approval_id: 12,
        field_count: 3,
      },
      status: "PENDING",
      risk_level: "high",
    },
  ]);

  assert.deepEqual(items, [
    {
      id: "task-1-submit-12",
      label: "Form submit",
      proposalType: "form_submit",
      target: "approval_request:12",
      value: "submit_form approval #12 (3 fields)",
      status: "PENDING",
      riskLevel: "high",
      reviewMode: "approval",
      evidenceCount: 0,
    },
  ]);
});

test("buildReviewQueueCompactItems shows browser action proposals compactly", () => {
  const items = buildReviewQueueCompactItems([
    {
      id: "task-1-click-save",
      proposal_type: "browser_click",
      target_type: "browser_element",
      target_ref: "#save-draft",
      proposed_value: {
        action: "click",
        selector: "#save-draft",
        label: "Save draft",
        tool_results: [{ raw: "do not show" }],
      },
      status: "PENDING",
      risk_level: "medium",
      evidence: [{ id: "e-1" }, { id: "e-2" }],
    },
    {
      id: "task-1-nav-confirm",
      proposal_type: "browser_navigation",
      target_type: "url",
      target_ref: "https://example.com/confirm",
      proposed_value: {
        action: "navigate",
        url: "https://example.com/confirm",
      },
      status: "APPROVED",
      risk_level: "low",
      evidence: [],
    },
  ]);

  assert.equal(items[0].label, "Browser click");
  assert.equal(items[0].target, "browser_element:#save-draft");
  assert.equal(items[0].action, "click");
  assert.equal(items[0].status, "PENDING");
  assert.equal(items[0].riskLevel, "medium");
  assert.equal(items[0].evidenceCount, 2);
  assert.doesNotMatch(items[0].value, /tool_results|do not show/);
  assert.equal(items[1].label, "Browser navigation");
  assert.equal(items[1].target, "url:https://example.com/confirm");
  assert.equal(items[1].action, "navigate");
});

test("buildReviewQueueCompactItems allows non-field evidence requests", () => {
  const items = buildReviewQueueCompactItems([
    {
      id: "task-1-memory",
      proposal_type: "memory_write",
      target_type: "workflow_memory",
      target_ref: "10",
      proposed_value: "email",
      status: "PENDING",
    },
    {
      id: "task-1-click",
      proposal_type: "browser_click",
      target_type: "browser_element",
      target_ref: "#save",
      proposed_value: { action: "click", selector: "#save" },
      status: "PENDING",
    },
    {
      id: "task-1-custom",
      proposal_type: "custom_followup",
      target_type: "runtime_action",
      target_ref: "next",
      proposed_value: "Collect more page context",
      status: "PENDING",
    },
    {
      id: "task-1-submit",
      proposal_type: "form_submit",
      target_type: "approval_request",
      target_ref: "7",
      proposed_value: { action: "submit_form", approval_id: 7 },
      status: "PENDING",
    },
  ]);

  assert.deepEqual(
    items.map((item) => [item.proposalType, item.canRequestEvidence]),
    [
      ["memory_write", true],
      ["browser_click", true],
      ["custom_followup", true],
      ["form_submit", undefined],
    ],
  );
});

test("buildReviewQueueCompactItems guards external write proposals", () => {
  const items = buildReviewQueueCompactItems([
    {
      id: "task-1-external-write",
      proposal_type: "external_api_write",
      target_type: "external_api",
      target_ref: "vendor_system",
      proposed_value: {
        action: "write_record",
        service: "vendor_system",
        tool_results: [{ raw: "do not show" }],
      },
      status: "PENDING",
      evidence: [{ id: "policy" }],
    },
  ]);

  assert.equal(items[0].label, "External api write");
  assert.equal(items[0].target, "external_api:vendor_system");
  assert.equal(items[0].riskLevel, "high");
  assert.equal(items[0].reviewMode, "blocked");
  assert.equal(items[0].canRequestEvidence, undefined);
  assert.equal(items[0].evidenceCount, 1);
  assert.doesNotMatch(items[0].value, /tool_results|do not show/);
});

test("buildReviewQueueCompactItems falls back for unknown proposals", () => {
  const items = buildReviewQueueCompactItems([
    {
      id: "task-1-unknown",
      proposal_type: "",
      target_type: "",
      target_ref: "",
      proposed_value: "",
    },
  ]);

  assert.equal(items[0].label, "Unknown");
  assert.equal(items[0].proposalType, "unknown");
  assert.equal(items[0].target, "target:");
  assert.equal(items[0].value, "No value");
  assert.equal(items[0].status, "PENDING");
  assert.equal(items[0].riskLevel, "low");
});

test("formatProposalTypeLabel returns stable proposal labels", () => {
  assert.equal(formatProposalTypeLabel("field_value"), "Field value");
  assert.equal(formatProposalTypeLabel("open_ended_answer"), "Open ended answer");
  assert.equal(formatProposalTypeLabel("memory_write"), "Memory write");
  assert.equal(formatProposalTypeLabel("browser_click"), "Browser click");
  assert.equal(formatProposalTypeLabel("custom_type"), "Custom type");
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
