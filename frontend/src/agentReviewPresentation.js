const DECISION_LABELS = {
  PASS: "Passed",
  REVIEW_REQUIRED: "Review required",
  BLOCK: "Blocked",
};

const ROLE_LABELS = {
  MAPPING_CRITIC: "Mapping Critic",
  SAFETY_REVIEW: "Safety Review",
  EXECUTION_VERIFICATION: "Execution Verification",
};

export function decisionLabel(decision) {
  return DECISION_LABELS[decision] || humanizeLabel(decision);
}

export function roleLabel(role) {
  return ROLE_LABELS[role] || humanizeLabel(role);
}

export function getLatestReview(reviews = [], role = null) {
  const filtered = role ? reviews.filter((r) => r.role === role) : reviews;
  if (filtered.length === 0) {
    return null;
  }
  return filtered.reduce((latest, current) => {
    if (!latest.created_at) return current;
    if (!current.created_at) return latest;
    return new Date(current.created_at) > new Date(latest.created_at)
      ? current
      : latest;
  });
}

export function getLatestDecision(reviews = [], role = null) {
  const latest = getLatestReview(reviews, role);
  return latest ? latest.decision : null;
}

export function summarizeReviewItems(review) {
  if (!review || !review.output || !review.output.items) {
    return { total: 0, issues: 0, warnings: 0 };
  }

  const items = review.output.items;
  const summary = {
    total: items.length,
    issues: items.filter((item) => item.issue && item.issue.includes("FAILED")).length,
    warnings: items.filter((item) => !item.issue || !item.issue.includes("FAILED")).length,
  };

  return summary;
}

export function groupReviewsByRole(reviews = []) {
  const groups = {};
  for (const review of reviews) {
    const role = review.role;
    if (!groups[role]) {
      groups[role] = [];
    }
    groups[role].push(review);
  }
  return groups;
}

export function getReviewSummary(reviews = []) {
  const summary = {
    total: reviews.length,
    passed: 0,
    reviewRequired: 0,
    blocked: 0,
    roles: {},
  };

  for (const review of reviews) {
    summary.roles[review.role] = summary.roles[review.role] || {
      count: 0,
      latestDecision: null,
    };
    summary.roles[review.role].count++;
    summary.roles[review.role].latestDecision = review.decision;

    switch (review.decision) {
      case "PASS":
        summary.passed++;
        break;
      case "REVIEW_REQUIRED":
        summary.reviewRequired++;
        break;
      case "BLOCK":
        summary.blocked++;
        break;
      default:
        break;
    }
  }

  return summary;
}

function humanizeLabel(str) {
  if (!str) {
    return "Unknown";
  }

  return str
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/(?:^|\s)\w/g, (char) => char.toUpperCase())
    .trim();
}