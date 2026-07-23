import assert from "node:assert/strict";
import test from "node:test";

import {
  buildWorkflowTemplateCreatePath,
  dockerDemoFormUrl,
  dockerDemoUrlForWorkflow,
  isTemplateEnabled,
  mappingModeForWorkflow,
  requiresLlmProviderForCreate,
  resolveWorkflowTypeSelection,
  sortWorkflowTemplates,
  templateAvailabilityLabel,
} from "./workflowTemplatePresentation.js";

test("template helpers expose status labels and enabled flags", () => {
  assert.equal(isTemplateEnabled({ enabled: true }), true);
  assert.equal(isTemplateEnabled({ enabled: false }), false);
  assert.equal(templateAvailabilityLabel({ enabled: true }), "Available");
  assert.equal(templateAvailabilityLabel({ enabled: false }), "Coming soon");
});

test("sortWorkflowTemplates keeps enabled templates first", () => {
  const templates = [
    { id: "job_apply", name: "Job Apply", enabled: false },
    { id: "form_fill", name: "Form Fill", enabled: true },
    { id: "vendor", name: "Vendor Intake", enabled: true },
  ];

  assert.deepEqual(sortWorkflowTemplates(templates).map((item) => item.id), [
    "form_fill",
    "vendor",
    "job_apply",
  ]);
});

test("sortWorkflowTemplates prioritizes security_questionnaire and vendor_onboarding before form_fill among enabled templates", () => {
  const templates = [
    { id: "form_fill", name: "Form Fill", enabled: true },
    { id: "security_questionnaire", name: "Security Questionnaire", enabled: true },
    { id: "vendor_onboarding", name: "Vendor Onboarding", enabled: true },
    { id: "web_data_extract", name: "Web Data Extraction", enabled: true },
    { id: "job_research_summary", name: "Job Research Summary", enabled: true },
  ];

  assert.deepEqual(sortWorkflowTemplates(templates).map((item) => item.id), [
    "security_questionnaire",
    "vendor_onboarding",
    "form_fill",
    "web_data_extract",
    "job_research_summary",
  ]);
});

test("buildWorkflowTemplateCreatePath encodes the workflow id", () => {
  assert.equal(
    buildWorkflowTemplateCreatePath("form fill"),
    "/tasks/new?workflow_type=form%20fill",
  );
});

test("dockerDemoFormUrl points to the backend container demo fixture", () => {
  assert.equal(
    dockerDemoFormUrl(),
    "file:///app/examples/llm-registration.html",
  );
});

test("dockerDemoUrlForWorkflow uses the questionnaire fixture for security workflow", () => {
  assert.equal(
    dockerDemoUrlForWorkflow("security_questionnaire"),
    "file:///app/examples/security-questionnaire.html",
  );
  assert.equal(dockerDemoUrlForWorkflow("form_fill"), dockerDemoFormUrl());
});

test("dockerDemoUrlForWorkflow uses the vendor onboarding fixture", () => {
  assert.equal(
    dockerDemoUrlForWorkflow("vendor_onboarding"),
    "file:///app/examples/vendor-onboarding.html",
  );
});

test("security questionnaire creation can run without an LLM provider", () => {
  assert.equal(requiresLlmProviderForCreate("security_questionnaire"), false);
  assert.equal(requiresLlmProviderForCreate("vendor_onboarding"), false);
  assert.equal(requiresLlmProviderForCreate("form_fill"), true);
  assert.equal(requiresLlmProviderForCreate("web_data_extract"), false);
});

test("mappingModeForWorkflow uses rules for local no-provider workflows", () => {
  assert.equal(mappingModeForWorkflow("security_questionnaire"), "rules");
  assert.equal(mappingModeForWorkflow("vendor_onboarding"), "rules");
  assert.equal(mappingModeForWorkflow("form_fill"), "llm");
});

test("resolveWorkflowTypeSelection falls back to security_questionnaire when available", () => {
  const result = resolveWorkflowTypeSelection(
    [
      { id: "security_questionnaire", enabled: true },
      { id: "form_fill", enabled: true },
      { id: "job_apply", enabled: false },
    ],
    "job_apply",
  );

  assert.deepEqual(result, {
    selectedWorkflowType: "security_questionnaire",
    notice: "Requested workflow template is unavailable. Using security_questionnaire instead.",
  });
});

test("resolveWorkflowTypeSelection falls back to form_fill when security_questionnaire is unavailable", () => {
  const result = resolveWorkflowTypeSelection(
    [
      { id: "form_fill", enabled: true },
      { id: "job_apply", enabled: false },
    ],
    "job_apply",
  );

  assert.deepEqual(result, {
    selectedWorkflowType: "form_fill",
    notice: "Requested workflow template is unavailable.",
  });
});

test("resolveWorkflowTypeSelection falls back safely for unknown requests", () => {
  const result = resolveWorkflowTypeSelection(
    [{ id: "form_fill", enabled: true }],
    "unknown_template",
  );

  assert.equal(result.selectedWorkflowType, "form_fill");
  assert.match(result.notice, /unavailable/i);
});
