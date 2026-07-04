import assert from "node:assert/strict";
import test from "node:test";

import {
  decisionLabel,
  roleLabel,
  getLatestReview,
  getLatestDecision,
  summarizeReviewItems,
  groupReviewsByRole,
  getReviewSummary,
} from "./agentReviewPresentation.js";

test("decisionLabel returns stable labels for known decisions", () => {
  assert.equal(decisionLabel("PASS"), "Passed");
  assert.equal(decisionLabel("REVIEW_REQUIRED"), "Review required");
  assert.equal(decisionLabel("BLOCK"), "Blocked");
});

test("decisionLabel humanizes unknown decisions", () => {
  assert.equal(decisionLabel("UNKNOWN_DECISION"), "Unknown Decision");
  assert.equal(decisionLabel("SOME_OTHER_STATUS"), "Some Other Status");
});

test("decisionLabel returns 'Unknown' for empty input", () => {
  assert.equal(decisionLabel(null), "Unknown");
  assert.equal(decisionLabel(undefined), "Unknown");
  assert.equal(decisionLabel(""), "Unknown");
});

test("roleLabel returns stable labels for known roles", () => {
  assert.equal(roleLabel("MAPPING_CRITIC"), "Mapping Critic");
  assert.equal(roleLabel("SAFETY_REVIEW"), "Safety Review");
  assert.equal(roleLabel("EXECUTION_VERIFICATION"), "Execution Verification");
});

test("roleLabel humanizes unknown roles", () => {
  assert.equal(roleLabel("UNKNOWN_ROLE"), "Unknown Role");
  assert.equal(roleLabel("CUSTOM_AGENT"), "Custom Agent");
});

test("roleLabel returns 'Unknown' for empty input", () => {
  assert.equal(roleLabel(null), "Unknown");
  assert.equal(roleLabel(undefined), "Unknown");
  assert.equal(roleLabel(""), "Unknown");
});

test("getLatestReview returns null for empty reviews", () => {
  assert.equal(getLatestReview([]), null);
  assert.equal(getLatestReview(), null);
});

test("getLatestReview returns the latest review based on created_at", () => {
  const reviews = [
    { role: "MAPPING_CRITIC", decision: "PASS", created_at: "2026-07-01T10:00:00" },
    { role: "MAPPING_CRITIC", decision: "REVIEW_REQUIRED", created_at: "2026-07-02T11:00:00" },
    { role: "SAFETY_REVIEW", decision: "PASS", created_at: "2026-07-03T12:00:00" },
  ];

  const latest = getLatestReview(reviews);
  assert.equal(latest.decision, "PASS");
  assert.equal(latest.role, "SAFETY_REVIEW");
});

test("getLatestReview filters by role when specified", () => {
  const reviews = [
    { role: "MAPPING_CRITIC", decision: "PASS", created_at: "2026-07-01T10:00:00" },
    { role: "MAPPING_CRITIC", decision: "REVIEW_REQUIRED", created_at: "2026-07-02T11:00:00" },
    { role: "SAFETY_REVIEW", decision: "PASS", created_at: "2026-07-03T12:00:00" },
  ];

  const latest = getLatestReview(reviews, "MAPPING_CRITIC");
  assert.equal(latest.decision, "REVIEW_REQUIRED");
  assert.equal(latest.role, "MAPPING_CRITIC");
});

test("getLatestReview returns null when role not found", () => {
  const reviews = [
    { role: "MAPPING_CRITIC", decision: "PASS", created_at: "2026-07-01T10:00:00" },
  ];

  assert.equal(getLatestReview(reviews, "SAFETY_REVIEW"), null);
});

test("getLatestDecision returns null for empty reviews", () => {
  assert.equal(getLatestDecision([]), null);
  assert.equal(getLatestDecision(), null);
});

test("getLatestDecision returns the latest decision", () => {
  const reviews = [
    { role: "MAPPING_CRITIC", decision: "PASS", created_at: "2026-07-01T10:00:00" },
    { role: "SAFETY_REVIEW", decision: "BLOCK", created_at: "2026-07-02T11:00:00" },
  ];

  assert.equal(getLatestDecision(reviews), "BLOCK");
});

test("getLatestDecision returns decision filtered by role", () => {
  const reviews = [
    { role: "MAPPING_CRITIC", decision: "PASS", created_at: "2026-07-01T10:00:00" },
    { role: "MAPPING_CRITIC", decision: "REVIEW_REQUIRED", created_at: "2026-07-02T11:00:00" },
    { role: "SAFETY_REVIEW", decision: "PASS", created_at: "2026-07-03T12:00:00" },
  ];

  assert.equal(getLatestDecision(reviews, "MAPPING_CRITIC"), "REVIEW_REQUIRED");
});

test("summarizeReviewItems returns zero counts for null input", () => {
  assert.deepEqual(summarizeReviewItems(null), { total: 0, issues: 0, warnings: 0 });
  assert.deepEqual(summarizeReviewItems(), { total: 0, issues: 0, warnings: 0 });
});

test("summarizeReviewItems returns zero counts for missing output", () => {
  const review = { decision: "PASS" };
  assert.deepEqual(summarizeReviewItems(review), { total: 0, issues: 0, warnings: 0 });
});

test("summarizeReviewItems summarizes review items correctly", () => {
  const review = {
    decision: "REVIEW_REQUIRED",
    output: {
      items: [
        { issue: "REQUIRED_FIELD_FAILED", message: "Email failed" },
        { issue: "OPTIONAL_FIELD_FAILED", message: "Phone failed" },
        { issue: "LOW_CONFIDENCE", message: "Low confidence" },
      ],
    },
  };

  const summary = summarizeReviewItems(review);
  assert.equal(summary.total, 3);
  assert.equal(summary.issues, 2);
  assert.equal(summary.warnings, 1);
});

test("summarizeReviewItems handles all warnings", () => {
  const review = {
    decision: "REVIEW_REQUIRED",
    output: {
      items: [
        { issue: "LOW_CONFIDENCE", message: "Low confidence" },
        { issue: "SENSITIVE_FIELD_SKIPPED", message: "Skipped" },
      ],
    },
  };

  const summary = summarizeReviewItems(review);
  assert.equal(summary.total, 2);
  assert.equal(summary.issues, 0);
  assert.equal(summary.warnings, 2);
});

test("groupReviewsByRole returns empty object for empty input", () => {
  assert.deepEqual(groupReviewsByRole([]), {});
  assert.deepEqual(groupReviewsByRole(), {});
});

test("groupReviewsByRole groups reviews by role", () => {
  const reviews = [
    { role: "MAPPING_CRITIC", decision: "PASS" },
    { role: "SAFETY_REVIEW", decision: "REVIEW_REQUIRED" },
    { role: "MAPPING_CRITIC", decision: "REVIEW_REQUIRED" },
  ];

  const groups = groupReviewsByRole(reviews);
  assert.deepEqual(Object.keys(groups), ["MAPPING_CRITIC", "SAFETY_REVIEW"]);
  assert.equal(groups["MAPPING_CRITIC"].length, 2);
  assert.equal(groups["SAFETY_REVIEW"].length, 1);
});

test("getReviewSummary returns zero counts for empty input", () => {
  const summary = getReviewSummary([]);
  assert.equal(summary.total, 0);
  assert.equal(summary.passed, 0);
  assert.equal(summary.reviewRequired, 0);
  assert.equal(summary.blocked, 0);
  assert.deepEqual(summary.roles, {});
});

test("getReviewSummary summarizes reviews correctly", () => {
  const reviews = [
    { role: "MAPPING_CRITIC", decision: "PASS" },
    { role: "SAFETY_REVIEW", decision: "REVIEW_REQUIRED" },
    { role: "EXECUTION_VERIFICATION", decision: "BLOCK" },
    { role: "MAPPING_CRITIC", decision: "REVIEW_REQUIRED" },
  ];

  const summary = getReviewSummary(reviews);
  assert.equal(summary.total, 4);
  assert.equal(summary.passed, 1);
  assert.equal(summary.reviewRequired, 2);
  assert.equal(summary.blocked, 1);
  assert.deepEqual(Object.keys(summary.roles), [
    "MAPPING_CRITIC",
    "SAFETY_REVIEW",
    "EXECUTION_VERIFICATION",
  ]);
  assert.equal(summary.roles["MAPPING_CRITIC"].count, 2);
  assert.equal(summary.roles["MAPPING_CRITIC"].latestDecision, "REVIEW_REQUIRED");
});