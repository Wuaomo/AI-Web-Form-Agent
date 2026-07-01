# Review Mapping Auto Profile Memory (Backend Archiving on Confirm Mapping) — Design

Date: 2026-07-01

## Background & Goals

Today, the Review Mapping page supports per-field “Save to profile” and requires the user to manually enter a Profile key. This is high-friction and prone to inconsistencies (different keys for the same concept) or missed saves.

This change aims to:

- Remove the per-field “Profile key” input and “Save to profile” button in the frontend
- When the user clicks “Confirm mapping”, have the backend automatically persist reusable values into the current `task.profile` inside `confirm_task_mapping`
- The backend is responsible for:
  - Generating and deduplicating `custom_values` keys
  - Skipping one-time fields (terms/privacy/agree/password/payment/login/action, etc.)
  - Synchronizing `field.mapped_profile_key`
  - Synchronizing the user mapping override cache (`UserMappingOverrideCache`)
- Keep existing safety boundaries: do not auto-submit forms, do not automate login/CAPTCHA, do not automate payments
- Do not break the existing `map-fields` and `fill` flow
- Improve transparency/control: Confirm mapping returns a summary of “which profile fields will be updated”, and the UI can display it

## Out of Scope

- No new user/auth/permission system
- No changes to the submission workflow (still requires manual approval after `WAITING_APPROVAL`)
- No new external dependencies or RAG

## Current State & Constraints

- The backend already supports saving one field at a time:
  - `PUT /tasks/{task_id}/fields/{field_id}` supports `save_to_profile` + `profile_custom_key`
  - It writes into `Profile.custom_values`, sets `field.mapped_profile_key` to `custom:<key>`, and writes to the override cache
- The Confirm mapping endpoint currently only performs required-field validation and sets `task.status` to `READY_TO_FILL`
- Reusable mapping behavior relies on two caches:
  - LLM mapping cache (reused across similar forms)
  - User mapping override cache (user-confirmed mapping for a stable field signature)

## Chosen Approach

Choose Approach B: based on Approach A (backend auto-archives on Confirm mapping), the Confirm mapping response includes a summary of “which profile fields will be updated”, and the frontend displays it.

Rationale: users can clearly see what will be written back to the profile, reducing surprises without adding extra steps.

## Data Flow & Core Logic

### Trigger

`POST /tasks/{task_id}/confirm-mapping`:

1. Load the current task and its fields
2. Validate required fields (existing behavior)
3. Auto-archive reusable values into `task.profile` (new)
4. Set `task.status = READY_TO_FILL`
5. Return `MappingConfirmationResponse` (extended to include a summary)

### Candidate Field Filtering (Conservative)

Only consider saving a field when all are true:

- `field.mapped_value` is not empty (not `None` and not an empty string)
- The field type is fillable (same intent as the existing `NON_FILLABLE_FIELD_TYPES`)
- The field does not match one-time/high-risk semantic keywords (case-insensitive; match over a combined text derived from label/name/placeholder/selector):
  - terms / privacy / agree / consent
  - password
  - payment / card / billing / checkout
  - login / sign in / otp / verification
  - action / submit / reset / file / upload / button

### Rules for Writing Back to Profile

For each candidate field, decide the write target:

1) Built-in fields (e.g. `email/phone/full_name/...`)

- If `field.mapped_profile_key` is a built-in key, write:
  - `task.profile.<key> = field.mapped_value` (overwrites are allowed to fix previously incorrect profile data)
  - Sync override cache: `save_user_mapping_override(db, field, <key>)`

2) Existing custom key (`custom:<key>`)

- Write:
  - `task.profile.custom_values[<key>] = field.mapped_value`
  - Sync override cache: `save_user_mapping_override(db, field, "custom:<key>")`

3) Unknown key (`field.mapped_profile_key` is empty or not in the known set)

- Generate a custom key:
  - Use the field display name (label/name/placeholder/selector) to build a candidate key
  - Reuse the backend’s existing normalization rule so the key only contains `[a-z0-9_]`
  - Dedup strategy: if the key already exists and a new key is needed, append `_2/_3/...`
- Write:
  - `task.profile.custom_values[<deduped>] = field.mapped_value`
  - Set `field.mapped_profile_key = "custom:<deduped>"`
  - Sync override cache: `save_user_mapping_override(db, field, "custom:<deduped>")`

### Syncing `field.mapped_profile_key` and Override Cache

For every field that is written back to the profile:

- `field.mapped_profile_key` must match the final write target (built-in key or `custom:<key>`)
- `save_user_mapping_override` must be called to upsert `UserMappingOverrideCache`

## API Changes

### Extend `MappingConfirmationResponse`

Current response includes:

- `task_id`
- `status`

Proposed additions:

- `profile_updates`: list
  - Each item includes:
    - `field_id`
    - `profile_key` (built-in key or `custom:<key>`)
    - `previous_value` (the old value in the profile; can be null)
    - `new_value`
    - `action` (`updated` | `created` | `skipped`, optional)
- `profile_skipped`: list (optional, to explain why something was not saved)
  - `field_id`
  - `reason` (e.g. `one_time_field` / `empty_value` / `non_fillable_type`)

The backend can start by returning only `profile_updates` (actual writes). `profile_skipped` can be added later if the UI needs it.

## Frontend Changes

Review Mapping page:

- Remove per-field Profile key input and “Save to profile” button
- After Confirm mapping:
  - Call the confirm-mapping API
  - Display the returned `profile_updates` summary (e.g. a message area or a card near the top)
- Keep the `map-fields` and `fill` buttons/flows unchanged

## Compatibility & Migration

- Keep the backend `PUT /tasks/{task_id}/fields/{field_id}` `save_to_profile` behavior (even if the UI no longer exposes the button) to avoid breaking tests or any potential API consumers
- Extending the confirm-mapping response schema is not strictly backward compatible for strict clients, but this is a monorepo and frontend/backend can be upgraded together

## Safety Boundaries

- Confirm mapping only updates database state (Profile / FormField / override cache / task.status)
- It must not trigger Playwright automation
- It must not change the existing safety mechanism that pauses before final submission

## Test Plan

Backend (pytest):

- Confirm mapping writes `mapped_value` back to `Profile.email` when `mapped_profile_key=email`
- Confirm mapping generates `custom:<key>` for fields without a key, writes to `Profile.custom_values`, and updates `field.mapped_profile_key`
- Confirm mapping skips terms/privacy/agree/password/payment/login/action fields (does not write to profile)
- Confirm mapping response includes `profile_updates` with correct contents

Frontend (existing test framework):

- Review Mapping no longer renders the per-field “Save to profile” controls
- After Confirm mapping succeeds, the UI displays a profile update summary (at minimum, count and/or list)

## Risks & Mitigations

- Accidentally persisting one-time fields into the profile:
  - Mitigate with keyword filtering + non-fillable type filtering, and show all writes in the response summary
- Overwriting an existing profile value unexpectedly:
  - Overwrites are intentionally allowed to fix incorrect profile data; show `previous_value` and `new_value` in the summary so the change is visible, and allow further edits in the Profiles page
