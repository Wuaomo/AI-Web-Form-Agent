export function getExtractionCheckpoint(checkpoints) {
  if (!checkpoints || !Array.isArray(checkpoints)) {
    return null;
  }
  const result = checkpoints.find((cp) => cp.stage === "EXTRACTION" && cp.output);
  return result || null;
}

export function parseExtractionOutput(checkpoint) {
  if (!checkpoint || !checkpoint.output) {
    return null;
  }
  const output = typeof checkpoint.output === "string" ? JSON.parse(checkpoint.output) : checkpoint.output;
  return output;
}

export function getExtractionData(checkpoints) {
  const checkpoint = getExtractionCheckpoint(checkpoints);
  if (!checkpoint) {
    return null;
  }
  return parseExtractionOutput(checkpoint);
}

export function getSummaryCheckpoint(checkpoints) {
  if (!checkpoints || !Array.isArray(checkpoints)) {
    return null;
  }
  const result = checkpoints.find((cp) => cp.stage === "SUMMARY" && cp.output);
  return result || null;
}

export function getSummaryData(checkpoints) {
  const checkpoint = getSummaryCheckpoint(checkpoints);
  if (!checkpoint) {
    return null;
  }
  return parseExtractionOutput(checkpoint);
}