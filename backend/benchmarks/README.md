# Benchmark Form Samples

This directory contains reproducible form-mapping benchmark cases for the AI
Web Form Agent.

Each case has:

- `forms/*.html`: a local web form that Playwright can open and analyze.
- `expected/*.json`: the expected extraction and mapping answers.

The first 10 cases are intentionally small but varied. They cover clear labels,
semantic labels, placeholder-only fields, aria labels, split names, mixed
controls, camelCase identifiers, submit-button safety, login-gate detection, and
required/optional field handling.

Suggested metrics for a future benchmark runner:

- Field extraction recall and precision.
- Profile-key mapping accuracy.
- Required-field completion rate.
- Rule-based mapping accuracy versus LLM-assisted mapping accuracy.
- Non-fillable/action-control rejection rate.
- Login-gate detection rate.

