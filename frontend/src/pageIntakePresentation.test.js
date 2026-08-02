import assert from "node:assert/strict";
import test from "node:test";

import {
  buildPageIntakeBrief,
  confidenceLabel,
  getPageIntakeCheckpoint,
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
  assert.equal(riskLabel("password"), "Password blocked");
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

test("getPageIntakeCheckpoint returns the newest PAGE_INTAKE checkpoint", () => {
  const checkpoints = [
    { id: 1, stage: "MAPPING", output: {} },
    { id: 2, stage: "PAGE_INTAKE", output: { page_type: "form" } },
    { id: 3, stage: "PAGE_INTAKE", output: { page_type: "questionnaire" } },
  ];

  assert.equal(getPageIntakeCheckpoint(checkpoints).id, 3);
  assert.equal(getPageIntakeCheckpoint([]), null);
});

test("buildPageIntakeBrief summarizes checkpoint output for Task Detail", () => {
  const brief = buildPageIntakeBrief([
    {
      id: 7,
      stage: "PAGE_INTAKE",
      status: "SUCCESS",
      output: {
        page_type: "questionnaire",
        recommended_workflow: "security_questionnaire",
        confidence: 0.85,
        detected_fields: [{ selector: "#a" }, { selector: "#b" }],
        risk_flags: ["password"],
        evidence: [
          { source: "page_text", text: "matched: security", reason: "security signal" },
        ],
      },
    },
  ]);

  assert.equal(brief.pageType, "questionnaire");
  assert.equal(brief.workflowLabel, "Security Questionnaire");
  assert.equal(brief.confidenceText, "High confidence (0.85)");
  assert.equal(brief.detectedFieldCount, 2);
  assert.deepEqual(brief.riskLabels, ["Password blocked"]);
  assert.equal(brief.evidenceItems[0].text, "matched: security");
});
