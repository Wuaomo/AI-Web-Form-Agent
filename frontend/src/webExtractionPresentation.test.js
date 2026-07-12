import { describe, it } from "node:test";
import assert from "node:assert";
import { getExtractionCheckpoint, parseExtractionOutput, getExtractionData } from "./webExtractionPresentation.js";

describe("webExtractionPresentation", () => {
  describe("getExtractionCheckpoint", () => {
    it("returns null for empty checkpoints", () => {
      assert.strictEqual(getExtractionCheckpoint([]), null);
    });

    it("returns null for null checkpoints", () => {
      assert.strictEqual(getExtractionCheckpoint(null), null);
    });

    it("returns null for undefined checkpoints", () => {
      assert.strictEqual(getExtractionCheckpoint(undefined), null);
    });

    it("returns null when no EXTRACTION checkpoint exists", () => {
      const checkpoints = [
        { stage: "ANALYSIS", output: {} },
        { stage: "MAPPING", output: {} },
      ];
      assert.strictEqual(getExtractionCheckpoint(checkpoints), null);
    });

    it("returns null when EXTRACTION checkpoint has no output", () => {
      const checkpoints = [
        { stage: "EXTRACTION", output: null },
      ];
      assert.strictEqual(getExtractionCheckpoint(checkpoints), null);
    });

    it("returns the EXTRACTION checkpoint with output", () => {
      const extractionCp = { stage: "EXTRACTION", output: { title: "Test" } };
      const checkpoints = [
        { stage: "ANALYSIS", output: {} },
        extractionCp,
        { stage: "MAPPING", output: {} },
      ];
      assert.strictEqual(getExtractionCheckpoint(checkpoints), extractionCp);
    });
  });

  describe("parseExtractionOutput", () => {
    it("returns null for null checkpoint", () => {
      assert.strictEqual(parseExtractionOutput(null), null);
    });

    it("returns null for checkpoint without output", () => {
      assert.strictEqual(parseExtractionOutput({ stage: "EXTRACTION" }), null);
    });

    it("returns null for checkpoint with null output", () => {
      assert.strictEqual(parseExtractionOutput({ stage: "EXTRACTION", output: null }), null);
    });

    it("parses JSON string output", () => {
      const checkpoint = { stage: "EXTRACTION", output: '{"title":"Test"}' };
      const result = parseExtractionOutput(checkpoint);
      assert.deepStrictEqual(result, { title: "Test" });
    });

    it("returns object output directly", () => {
      const output = { title: "Test", heading_count: 5 };
      const checkpoint = { stage: "EXTRACTION", output };
      assert.strictEqual(parseExtractionOutput(checkpoint), output);
    });
  });

  describe("getExtractionData", () => {
    it("returns null when no checkpoints", () => {
      assert.strictEqual(getExtractionData(null), null);
    });

    it("returns null when no extraction checkpoint", () => {
      const checkpoints = [{ stage: "ANALYSIS", output: {} }];
      assert.strictEqual(getExtractionData(checkpoints), null);
    });

    it("returns parsed extraction data", () => {
      const checkpoints = [
        { stage: "EXTRACTION", output: '{"title":"Test Page","heading_count":3}' },
      ];
      const result = getExtractionData(checkpoints);
      assert.deepStrictEqual(result, { title: "Test Page", heading_count: 3 });
    });
  });
});