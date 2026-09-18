import assert from "node:assert/strict";
import test from "node:test";

import {
  resolveTaskExtractionResult,
  resolveTaskResearchSummary,
  shouldShowApprovalsOnMain,
} from "./taskDetailPresentation.js";

test("shouldShowApprovalsOnMain hides empty and resolved approval sections", () => {
  assert.equal(shouldShowApprovalsOnMain([]), false);
  assert.equal(shouldShowApprovalsOnMain([{ status: "APPROVED" }]), false);
});

test("shouldShowApprovalsOnMain shows pending approvals", () => {
  assert.equal(shouldShowApprovalsOnMain([{ status: "PENDING" }]), true);
});

test("Task Detail prefers complete governed extraction over checkpoint history", () => {
  const extraction = {
    title: "Governed page",
    main_text_blocks: ["Complete extracted text."],
    links: [{ text: "Docs", href: "https://example.com/docs" }],
  };

  assert.equal(
    resolveTaskExtractionResult(
      { workflow_result: { extraction } },
      { title: "Old checkpoint" },
    ),
    extraction,
  );
  assert.deepEqual(
    resolveTaskExtractionResult(null, { title: "Historical checkpoint" }),
    { title: "Historical checkpoint" },
  );
});

test("Task Detail prefers governed research summary over checkpoint history", () => {
  const researchSummary = {
    summary: "Governed summary",
    key_requirements: ["Python"],
    action_checklist: ["Prepare examples"],
    risks: ["Missing salary range"],
  };

  assert.equal(
    resolveTaskResearchSummary(
      { workflow_result: { research_summary: researchSummary } },
      { summary: "Old checkpoint" },
    ),
    researchSummary,
  );
  assert.deepEqual(
    resolveTaskResearchSummary(null, { summary: "Historical checkpoint" }),
    { summary: "Historical checkpoint" },
  );
});
