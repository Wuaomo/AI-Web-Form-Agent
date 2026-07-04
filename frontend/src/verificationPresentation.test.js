import assert from "node:assert/strict";
import test from "node:test";

import {
  summarizeVerificationResults,
  verificationStatusLabel,
  verificationReasonLabel,
} from "./verificationPresentation.js";

test("summarizeVerificationResults counts verified, failed, skipped, and partial results", () => {
  const results = [
    { status: "VERIFIED" },
    { status: "VERIFIED" },
    { status: "FAILED" },
    { status: "SKIPPED" },
    { status: "PARTIAL" },
    { status: "SKIPPED" },
  ];

  const summary = summarizeVerificationResults(results);

  assert.deepEqual(summary, {
    verified: 2,
    failed: 1,
    skipped: 2,
    partial: 1,
    total: 6,
  });
});

test("summarizeVerificationResults returns zeros for empty results", () => {
  const summary = summarizeVerificationResults([]);

  assert.deepEqual(summary, {
    verified: 0,
    failed: 0,
    skipped: 0,
    partial: 0,
    total: 0,
  });
});

test("summarizeVerificationResults handles undefined input", () => {
  const summary = summarizeVerificationResults();

  assert.deepEqual(summary, {
    verified: 0,
    failed: 0,
    skipped: 0,
    partial: 0,
    total: 0,
  });
});

test("summarizeVerificationResults ignores unknown statuses", () => {
  const results = [
    { status: "VERIFIED" },
    { status: "UNKNOWN_STATUS" },
    { status: "FAILED" },
  ];

  const summary = summarizeVerificationResults(results);

  assert.deepEqual(summary, {
    verified: 1,
    failed: 1,
    skipped: 0,
    partial: 0,
    total: 3,
  });
});

test("verificationStatusLabel returns human-readable label for VERIFIED", () => {
  assert.equal(verificationStatusLabel("VERIFIED"), "Verified");
});

test("verificationStatusLabel returns human-readable label for FAILED", () => {
  assert.equal(verificationStatusLabel("FAILED"), "Failed");
});

test("verificationStatusLabel returns human-readable label for SKIPPED", () => {
  assert.equal(verificationStatusLabel("SKIPPED"), "Skipped");
});

test("verificationStatusLabel returns human-readable label for PARTIAL", () => {
  assert.equal(verificationStatusLabel("PARTIAL"), "Partial");
});

test("verificationStatusLabel humanizes unknown status", () => {
  assert.equal(verificationStatusLabel("UNKNOWN_STATUS"), "Unknown Status");
});

test("verificationStatusLabel handles null", () => {
  assert.equal(verificationStatusLabel(null), "Unknown");
});

test("verificationStatusLabel handles undefined", () => {
  assert.equal(verificationStatusLabel(undefined), "Unknown");
});

test("verificationReasonLabel returns human-readable label for SELECTOR_NOT_FOUND", () => {
  assert.equal(verificationReasonLabel("SELECTOR_NOT_FOUND"), "Selector not found");
});

test("verificationReasonLabel returns human-readable label for VALUE_MISMATCH", () => {
  assert.equal(verificationReasonLabel("VALUE_MISMATCH"), "Value mismatch");
});

test("verificationReasonLabel returns human-readable label for OPTION_NOT_SELECTED", () => {
  assert.equal(verificationReasonLabel("OPTION_NOT_SELECTED"), "Option not selected");
});

test("verificationReasonLabel returns human-readable label for FIELD_DISABLED", () => {
  assert.equal(verificationReasonLabel("FIELD_DISABLED"), "Field disabled");
});

test("verificationReasonLabel returns human-readable label for SENSITIVE_FIELD_SKIPPED", () => {
  assert.equal(verificationReasonLabel("SENSITIVE_FIELD_SKIPPED"), "Sensitive field skipped");
});

test("verificationReasonLabel returns human-readable label for PAGE_NAVIGATED_UNEXPECTEDLY", () => {
  assert.equal(verificationReasonLabel("PAGE_NAVIGATED_UNEXPECTEDLY"), "Page navigated unexpectedly");
});

test("verificationReasonLabel humanizes unknown reason", () => {
  assert.equal(verificationReasonLabel("UNKNOWN_REASON"), "Unknown Reason");
});

test("verificationReasonLabel returns null for null", () => {
  assert.equal(verificationReasonLabel(null), null);
});

test("verificationReasonLabel returns null for undefined", () => {
  assert.equal(verificationReasonLabel(undefined), null);
});

test("verificationReasonLabel returns null for empty string", () => {
  assert.equal(verificationReasonLabel(""), null);
});