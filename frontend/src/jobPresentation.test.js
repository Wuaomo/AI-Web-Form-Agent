import test from "node:test";
import assert from "node:assert/strict";

import {
  jobStatusLabel,
  jobTypeLabel,
  jobStatusClass,
  summarizeJob,
  getNewestJob,
  newestJobStatusLine,
  isTerminalJob,
  isJobInProgress,
} from "./jobPresentation.js";

test("jobStatusLabel returns Queued for PENDING", () => {
  assert.equal(jobStatusLabel("PENDING"), "Queued");
});

test("jobStatusLabel returns Running for RUNNING", () => {
  assert.equal(jobStatusLabel("RUNNING"), "Running");
});

test("jobStatusLabel returns clear label for RETRY_SCHEDULED", () => {
  assert.equal(jobStatusLabel("RETRY_SCHEDULED"), "Retry scheduled");
});

test("jobStatusLabel returns Succeeded for SUCCEEDED", () => {
  assert.equal(jobStatusLabel("SUCCEEDED"), "Succeeded");
});

test("jobStatusLabel returns Failed for FAILED", () => {
  assert.equal(jobStatusLabel("FAILED"), "Failed");
});

test("jobStatusLabel returns Cancelled for CANCELLED", () => {
  assert.equal(jobStatusLabel("CANCELLED"), "Cancelled");
});

test("jobStatusLabel passes through unknown status", () => {
  assert.equal(jobStatusLabel("UNKNOWN"), "UNKNOWN");
});

test("jobTypeLabel returns readable label for known types", () => {
  assert.equal(jobTypeLabel("ANALYZE_FORM"), "Analyze form");
  assert.equal(jobTypeLabel("MAP_FIELDS"), "Map fields");
  assert.equal(jobTypeLabel("FILL_FORM"), "Fill form");
});

test("jobStatusClass returns kebab-case class", () => {
  assert.equal(jobStatusClass("RETRY_SCHEDULED"), "retry-scheduled");
  assert.equal(jobStatusClass("PENDING"), "pending");
});

test("summarizeJob includes attempt count for failed job", () => {
  const job = {
    id: 1,
    job_type: "ANALYZE_FORM",
    status: "FAILED",
    attempts: 2,
    max_attempts: 3,
    error_message: "Connection timed out",
  };

  const summary = summarizeJob(job);
  assert.equal(summary.attempts, 2);
  assert.equal(summary.maxAttempts, 3);
  assert.equal(summary.statusLabel, "Failed");
  assert.equal(summary.error, "Connection timed out");
});

test("summarizeJob does not include error for succeeded job", () => {
  const job = {
    id: 2,
    job_type: "MAP_FIELDS",
    status: "SUCCEEDED",
    attempts: 1,
    max_attempts: 3,
    error_message: null,
  };

  const summary = summarizeJob(job);
  assert.equal(summary.statusLabel, "Succeeded");
  assert.equal(summary.error, "");
});

test("summarizeJob includes error for retry-scheduled job", () => {
  const job = {
    id: 3,
    job_type: "FILL_FORM",
    status: "RETRY_SCHEDULED",
    attempts: 1,
    max_attempts: 3,
    error_message: "Browser timeout",
  };

  const summary = summarizeJob(job);
  assert.equal(summary.statusLabel, "Retry scheduled");
  assert.equal(summary.error, "Browser timeout");
});

test("summarizeJob strips stack traces from error messages", () => {
  const job = {
    id: 4,
    job_type: "ANALYZE_FORM",
    status: "FAILED",
    attempts: 3,
    max_attempts: 3,
    error_message: "Form analysis failed\n  File \"app/services/form_extractor.py\", line 42\n    raise ValueError(...)",
  };

  const summary = summarizeJob(job);
  assert.equal(summary.error, "Form analysis failed");
});

test("summarizeJob strips file path prefixes from error messages", () => {
  const job = {
    id: 5,
    job_type: "MAP_FIELDS",
    status: "FAILED",
    attempts: 2,
    max_attempts: 3,
    error_message: "C:\\app\\services\\field_mapper.py:123: LLM request failed",
  };

  const summary = summarizeJob(job);
  assert.equal(summary.error, "LLM request failed");
});

test("summarizeJob returns null for null input", () => {
  assert.equal(summarizeJob(null), null);
});

test("getNewestJob returns first job from list", () => {
  const jobs = [
    { id: 2, job_type: "MAP_FIELDS", status: "PENDING" },
    { id: 1, job_type: "ANALYZE_FORM", status: "SUCCEEDED" },
  ];

  const newest = getNewestJob(jobs);
  assert.equal(newest.id, 2);
});

test("getNewestJob returns null for empty list", () => {
  assert.equal(getNewestJob([]), null);
  assert.equal(getNewestJob(null), null);
});

test("newestJobStatusLine includes attempt count for failed job", () => {
  const jobs = [
    {
      id: 1,
      job_type: "ANALYZE_FORM",
      status: "FAILED",
      attempts: 2,
      max_attempts: 3,
      error_message: "Timeout",
    },
  ];

  const line = newestJobStatusLine(jobs);
  assert.equal(line, "Analyze form: Failed (attempt 2/3) — Timeout");
});

test("newestJobStatusLine returns empty string for no jobs", () => {
  assert.equal(newestJobStatusLine([]), "");
  assert.equal(newestJobStatusLine(null), "");
});

test("isTerminalJob returns true for terminal statuses", () => {
  assert.equal(isTerminalJob({ status: "SUCCEEDED" }), true);
  assert.equal(isTerminalJob({ status: "FAILED" }), true);
  assert.equal(isTerminalJob({ status: "CANCELLED" }), true);
});

test("isTerminalJob returns false for non-terminal statuses", () => {
  assert.equal(isTerminalJob({ status: "PENDING" }), false);
  assert.equal(isTerminalJob({ status: "RUNNING" }), false);
  assert.equal(isTerminalJob({ status: "RETRY_SCHEDULED" }), false);
});

test("isJobInProgress returns true for queued or running jobs", () => {
  assert.equal(isJobInProgress({ status: "PENDING" }), true);
  assert.equal(isJobInProgress({ status: "RUNNING" }), true);
  assert.equal(isJobInProgress({ status: "RETRY_SCHEDULED" }), true);
});

test("isJobInProgress returns false for terminal jobs", () => {
  assert.equal(isJobInProgress({ status: "SUCCEEDED" }), false);
  assert.equal(isJobInProgress({ status: "FAILED" }), false);
});
