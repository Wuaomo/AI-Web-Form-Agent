# Phase 7: Retrieval Quality and Memory Governance

## Goal

Make reviewed memory trustworthy enough to support AI-assisted workflows without
turning the project into a broad RAG platform.

## Why

Retrieval is only useful if users can see where suggestions came from, when they
are stale, and why unsafe data is not reused.

## Scope

Improve memory quality, source evidence, and safety rules around reuse.

## Current Status

Partially complete:

- Confirmed form-field mapping memory exists.
- Sensitive and one-time field skip rules exist.
- Retrieval is intentionally local and simple.
- Reviewed memory retrieval now returns source type, source id, reviewed
  timestamp, last-used timestamp, stale status, and governance status.
- Stale reviewed memory is still visible as evidence, but is not used for
  automatic retrieval fallback mapping.

Not complete yet:

- source document evidence;
- user-facing stale memory warnings;
- manual delete or disable flow;
- unsupported-answer refusal for questionnaire answers;
- reviewed-only governance for policy-document-derived answers.

## Features

### Source-Backed Suggestions

Every memory-backed suggestion should show:

- source type
- source task or document
- matched field or policy snippet
- reviewed timestamp
- confidence or match reason

### Memory Governance

Add rules for:

- reviewed-only reuse;
- stale memory warnings;
- sensitive memory rejection;
- unsupported-answer refusal;
- one-time value rejection;
- manual delete or disable.

### Retrieval Baselines

Keep the first implementation boring:

- SQLite text search or simple similarity first;
- optional embeddings only after the baseline works;
- no vector database unless local retrieval quality clearly needs it.

## Acceptance Criteria

- Users can tell why a suggestion was made.
- Sensitive and one-time values are never stored or reused.
- Unsupported answers are marked as needs review instead of guessed.
- Tests cover source evidence, stale memory, refusal, and sensitive skip rules.
