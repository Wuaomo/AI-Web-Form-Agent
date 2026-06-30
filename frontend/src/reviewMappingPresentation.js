const actionFieldTypes = new Set(["button", "file", "submit", "reset", "image"]);

export const profileKeys = [
  "first_name",
  "last_name",
  "full_name",
  "email",
  "phone",
  "university",
  "major",
  "linkedin",
  "github",
  "self_intro",
];

export function isReviewableField(field) {
  return !actionFieldTypes.has((field.field_type || "").toLowerCase());
}

export function fieldDisplayName(field) {
  return (
    field.field_label ||
    field.label ||
    field.name ||
    field.hint ||
    field.placeholder ||
    field.selector
  );
}

export function fieldHint(field) {
  const hint = field.hint || field.placeholder;
  if (!hint || hint === fieldDisplayName(field)) {
    return "";
  }
  return hint;
}

export function fieldFormTitle(field) {
  if (!field.form_title || field.form_title === fieldDisplayName(field)) {
    return "";
  }
  return field.form_title;
}

export function fieldSectionTitle(field) {
  if (!field.section_title || field.section_title === fieldDisplayName(field)) {
    return "";
  }
  return field.section_title;
}

export function fieldGroupTitle(field) {
  return fieldSectionTitle(field) || fieldFormTitle(field) || "Form fields";
}

export function buildReviewGroups(fields) {
  const groups = [];
  const groupByTitle = new Map();

  fields.filter(isReviewableField).forEach((field) => {
    const title = fieldGroupTitle(field);
    if (!groupByTitle.has(title)) {
      const group = { title, fields: [] };
      groupByTitle.set(title, group);
      groups.push(group);
    }
    groupByTitle.get(title).fields.push(field);
  });

  return groups;
}

export function needsRequiredInput(field) {
  return field.required && isReviewableField(field) && !field.mapped_value;
}

export function needsMappingReview(field) {
  if (!isReviewableField(field)) {
    return false;
  }
  if (needsRequiredInput(field)) {
    return true;
  }
  if (field.confidence === null || field.confidence === undefined) {
    return true;
  }
  return field.confidence < 0.7;
}

export function formatConfidence(confidence) {
  if (confidence === null || confidence === undefined) {
    return "Not scored";
  }
  return `${Math.round(confidence * 100)}%`;
}

export function formatMappingSummary(field) {
  if (!field.mapped_profile_key && !field.mapped_value) {
    return "Not chosen yet";
  }

  const source = field.mapped_profile_key
    ? `profile.${field.mapped_profile_key}`
    : "Manual value";
  const value = field.mapped_value ? `"${field.mapped_value}"` : "empty";
  return `${source} -> ${value}`;
}

export function valueControlLabel(field) {
  const fieldType = (field.field_type || "").toLowerCase();
  if (fieldType === "checkbox") {
    return "Checked state";
  }
  if (fieldType === "radio" || fieldType === "select") {
    return "Selected option";
  }
  return "Value to enter";
}

export function getFieldChoiceOptions(field) {
  return (field.options || [])
    .map((option) => ({
      label: option.label || option.value || "",
      value: option.value || option.label || "",
    }))
    .filter((option) => option.label || option.value);
}

export function hasFieldChoiceOptions(field) {
  const fieldType = (field.field_type || "").toLowerCase();
  return (
    (fieldType === "radio" || fieldType === "select") &&
    getFieldChoiceOptions(field).length > 0
  );
}
