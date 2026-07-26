import assert from "node:assert/strict";
import test from "node:test";

import {
  confidenceLabel,
  riskLabel,
  workflowLabel,
} from "./pageIntakePresentation.js";

test("workflowLabel returns human-readable names for known workflows", () => {
  assert.equal(workflowLabel("security_questionnaire"), "Security Questionnaire");
  assert.equal(workflowLabel("vendor_onboarding"), "Vendor Onboarding");
  assert.equal(workflowLabel("job_research_summary"), "Job Research Summary");
  assert.equal(workflowLabel("form_fill"), "Form Fill");
  assert.equal(workflowLabel("web_data_extract"), "Web Data Extract");
});

test("workflowLabel falls back to raw value for unknown types", () => {
  assert.equal(workflowLabel("unknown_type"), "unknown_type");
});

test("riskLabel returns human-readable names for known risk flags", () => {
  assert.equal(riskLabel("login_required"), "Login required");
  assert.equal(riskLabel("captcha"), "CAPTCHA blocked");
  assert.equal(riskLabel("otp"), "One-time code blocked");
  assert.equal(riskLabel("payment"), "Payment blocked");
  assert.equal(riskLabel("destructive_action"), "Destructive action review");
});

test("riskLabel falls back to raw value for unknown flags", () => {
  assert.equal(riskLabel("unknown_flag"), "unknown_flag");
});

test("confidenceLabel maps numeric confidence to qualitative labels", () => {
  assert.equal(confidenceLabel(0.95), "High confidence");
  assert.equal(confidenceLabel(0.8), "High confidence");
  assert.equal(confidenceLabel(0.75), "Medium confidence");
  assert.equal(confidenceLabel(0.6), "Medium confidence");
  assert.equal(confidenceLabel(0.55), "Needs review");
  assert.equal(confidenceLabel(0.4), "Needs review");
  assert.equal(confidenceLabel(0), "Needs review");
});
