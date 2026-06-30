import assert from "node:assert/strict";
import test from "node:test";

import { formatChinaTime } from "./dateTime.js";

test("formatChinaTime treats naive backend timestamps as UTC", () => {
  assert.equal(formatChinaTime("2026-06-30 05:54:22.644147"), "2026/06/30 13:54");
});

test("formatChinaTime formats explicit UTC timestamps in China time", () => {
  assert.equal(formatChinaTime("2026-06-29T12:00:00Z"), "2026/06/29 20:00");
});
