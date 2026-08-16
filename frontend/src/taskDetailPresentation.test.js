import assert from "node:assert/strict";
import test from "node:test";

import { shouldShowApprovalsOnMain } from "./taskDetailPresentation.js";

test("shouldShowApprovalsOnMain hides empty and resolved approval sections", () => {
  assert.equal(shouldShowApprovalsOnMain([]), false);
  assert.equal(shouldShowApprovalsOnMain([{ status: "APPROVED" }]), false);
});

test("shouldShowApprovalsOnMain shows pending approvals", () => {
  assert.equal(shouldShowApprovalsOnMain([{ status: "PENDING" }]), true);
});
