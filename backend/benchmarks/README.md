# Benchmark Form Samples

This directory contains reproducible form-mapping benchmark cases for the AI
Web Form Agent.

Each case has:

- `forms/*.html`: a local web form that Playwright can open and analyze.
- `expected/*.json`: the expected extraction and mapping answers.

The first 16 cases are intentionally small but varied. They cover clear labels,
semantic labels, placeholder-only fields, aria labels, split names, mixed
controls, camelCase identifiers, submit-button safety, login-gate detection, and
required/optional field handling.

Additional cases (11-16) cover more realistic patterns:

- Multi-section applications spanning personal, education, and link blocks.
- Select dropdowns where option labels do not match stored profile values.
- Radio groups with shared names that represent preferences (not profile data).
- Checkbox groups for interests/skills plus a required terms agreement checkbox.
- Address and date fields that are intentionally unsupported by built-in profile keys.
- Security questionnaire answers backed by local policy evidence, plus unsupported
  and sensitive-field refusal cases.
- Full-workflow reliability mode that runs locally without LLM keys and reports
  workflow success, safety pass, verification pass, and failure rate.

Suggested metrics for a future benchmark runner:

- Field extraction recall and precision.
- Profile-key mapping accuracy.
- Required-field completion rate.
- Rule-based mapping accuracy versus LLM-assisted mapping accuracy.
- Non-fillable/action-control rejection rate.
- Login-gate detection rate.
- Source evidence coverage.
- Unsupported-answer refusal rate.
- Sensitive-field skip rate.
- Workflow success rate.
- Safety pass rate.
- Verification pass rate.
- Failure rate.
