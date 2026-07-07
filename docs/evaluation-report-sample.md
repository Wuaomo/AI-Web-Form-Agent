# Evaluation Report Sample

Sample report generated from local fixtures. These numbers are illustrative for the demo package and are not production usage claims.

## Run Summary

| Metric | Sample Result |
| --- | ---: |
| Benchmark cases | 15 |
| Field extraction recall | 0.93 |
| Field extraction precision | 0.96 |
| Profile-key mapping accuracy | 0.88 |
| Required-field coverage | 0.91 |
| Non-fillable/action rejection | 1.00 |
| Login-gate detection | 1.00 |

## Case-Level Notes

| Case | Focus | Sample Outcome |
| --- | --- | --- |
| `simple_contact` | Clear labels | Passed |
| `placeholder_only` | Placeholder-based fields | Passed |
| `split_name` | First and last name handling | Passed |
| `mixed_controls` | Select, checkbox, radio controls | Review needed |
| `login_gate` | Authentication boundary | Blocked correctly |

## How To Reproduce Real Results

Run the benchmark suite from the backend:

```powershell
cd backend
python -m pytest
```

Or use the Evaluation page in the frontend after starting the app. Persisted benchmark runs show comparisons, regressions, improvements, and failure details.

## What The Evaluation Proves

- Local fixtures make mapping quality repeatable.
- Required-field coverage is tracked separately from general mapping accuracy.
- Submit buttons and other action controls are rejected as non-fillable.
- Login gates are treated as safety boundaries rather than automation targets.

## What It Does Not Prove

- It does not claim production reliability across all websites.
- It does not measure paid LLM provider quality unless a provider is explicitly configured.
- It does not bypass CAPTCHA, authentication, or anti-bot systems.
