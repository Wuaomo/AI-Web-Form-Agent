import assert from "node:assert/strict";
import test from "node:test";

import {
  buildWorkflowTemplateCreatePath,
  dockerDemoFormUrl,
  isTemplateEnabled,
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

test("resolveWorkflowTypeSelection falls back to form_fill for disabled requests", () => {
  const result = resolveWorkflowTypeSelection(
    [
      { id: "form_fill", enabled: true },
      { id: "job_apply", enabled: false },
    ],
    "job_apply",
  );

  assert.deepEqual(result, {
    selectedWorkflowType: "form_fill",
    notice: "Requested workflow template is unavailable. Using form_fill instead.",
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
