import assert from "node:assert/strict";
import test from "node:test";

import {
  getWorkflowPlanSteps,
  workflowPlanApprovalLabel,
} from "./workflowPlanPresentation.js";

test("getWorkflowPlanSteps preserves provided step ordering", () => {
  const plan = {
    steps: [
      { step_id: "open_url", tool: "open_url" },
      { step_id: "review_mapping", tool: "request_human_approval" },
      { step_id: "submit_form", tool: "submit_form" },
    ],
  };

  assert.deepEqual(
    getWorkflowPlanSteps(plan).map((step) => step.step_id),
    ["open_url", "review_mapping", "submit_form"],
  );
});

test("workflowPlanApprovalLabel marks approval-required steps", () => {
  assert.equal(
    workflowPlanApprovalLabel({ requires_approval: true }),
    "Approval required",
  );
  assert.equal(
    workflowPlanApprovalLabel({ requires_approval: false }),
    null,
  );
});
