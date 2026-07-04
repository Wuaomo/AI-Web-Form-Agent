const JOB_STATUS_LABELS = {
  PENDING: "Queued",
  RUNNING: "Running",
  RETRY_SCHEDULED: "Retry scheduled",
  SUCCEEDED: "Succeeded",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
};

const JOB_TYPE_LABELS = {
  ANALYZE_FORM: "Analyze form",
  MAP_FIELDS: "Map fields",
  FILL_FORM: "Fill form",
  RUN_BENCHMARK: "Run benchmark",
};

/**
 * Return a human-readable label for a job status.
 *
 * @param {string} status - Raw job status from the API.
 * @returns {string} Display label.
 */
export function jobStatusLabel(status) {
  return JOB_STATUS_LABELS[status] || status;
}

/**
 * Return a human-readable label for a job type.
 *
 * @param {string} jobType - Raw job type from the API.
 * @returns {string} Display label.
 */
export function jobTypeLabel(jobType) {
  return JOB_TYPE_LABELS[jobType] || jobType;
}

/**
 * Return a CSS-friendly status class for styling job badges.
 *
 * @param {string} status - Raw job status from the API.
 * @returns {string} Lowercase kebab-case status.
 */
export function jobStatusClass(status) {
  return (status || "pending").toLowerCase().replace(/_/g, "-");
}

/**
 * Build a user-facing summary for a single job.
 *
 * Shows attempt count and a sanitized error message (no stack traces)
 * when the job has failed or is scheduled for retry.
 *
 * @param {object} job - Job object from the API.
 * @returns {object} Summary with label, statusLabel, attempts, and error fields.
 */
export function summarizeJob(job) {
  if (!job) {
    return null;
  }

  const summary = {
    id: job.id,
    type: job.job_type,
    typeLabel: jobTypeLabel(job.job_type),
    status: job.status,
    statusLabel: jobStatusLabel(job.status),
    statusClass: jobStatusClass(job.status),
    attempts: job.attempts ?? 0,
    maxAttempts: job.max_attempts ?? 3,
    error: "",
  };

  if (job.status === "FAILED" || job.status === "RETRY_SCHEDULED") {
    summary.error = sanitizeErrorMessage(job.error_message);
  }

  return summary;
}

/**
 * Return the newest job from a list (sorted by created_at descending by API).
 *
 * @param {Array} jobs - List of job objects from the API.
 * @returns {object|null} The newest job or null if empty.
 */
export function getNewestJob(jobs) {
  if (!jobs || jobs.length === 0) {
    return null;
  }
  return jobs[0];
}

/**
 * Build a short status line for the newest job.
 *
 * @param {Array} jobs - List of job objects from the API.
 * @returns {string} Status line text, or empty string when no jobs exist.
 */
export function newestJobStatusLine(jobs) {
  const newest = getNewestJob(jobs);
  if (!newest) {
    return "";
  }

  const summary = summarizeJob(newest);
  let line = `${summary.typeLabel}: ${summary.statusLabel}`;

  if (summary.attempts > 0) {
    line += ` (attempt ${summary.attempts}/${summary.maxAttempts})`;
  }

  if (summary.error) {
    line += ` — ${summary.error}`;
  }

  return line;
}

/**
 * Convert a raw error message into a safe user-facing string.
 *
 * Strips stack traces and file paths so internal details are not exposed.
 *
 * @param {string} message - Raw error message.
 * @returns {string} Sanitized message.
 */
function sanitizeErrorMessage(message) {
  if (!message) {
    return "";
  }

  // Take only the first line to avoid stack traces.
  const firstLine = String(message).split("\n")[0].trim();

  // Strip common file path prefixes (e.g. "C:\...\module.py:123: Error: ...").
  const cleaned = firstLine.replace(
    /^[A-Za-z]:[/\\].*?:\d+:\s*/g,
    "",
  );

  // Truncate overly long messages.
  return cleaned.length > 200 ? cleaned.slice(0, 200) + "…" : cleaned;
}

/**
 * Determine whether a job is in a terminal state.
 *
 * @param {object} job - Job object from the API.
 * @returns {boolean} True if the job has reached a final status.
 */
export function isTerminalJob(job) {
  if (!job) {
    return false;
  }
  return ["SUCCEEDED", "FAILED", "CANCELLED"].includes(job.status);
}

/**
 * Determine whether a job is currently in progress.
 *
 * @param {object} job - Job object from the API.
 * @returns {boolean} True if the job is queued or running.
 */
export function isJobInProgress(job) {
  if (!job) {
    return false;
  }
  return ["PENDING", "RUNNING", "RETRY_SCHEDULED"].includes(job.status);
}
