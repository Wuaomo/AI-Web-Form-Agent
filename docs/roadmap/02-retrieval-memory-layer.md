# Phase 2: Retrieval Memory Layer

## Goal

Make the system visibly learn from reviewed corrections and source-backed
knowledge.

## Why

AI application roles care about retrieval and memory, but the project does not
need a large RAG platform. The app should prove that reviewed knowledge can
improve future browser workflows safely.

## Scope

Add reviewed memory, source explanations, and retrieval-backed answer
suggestions.

## Current Status

Completed:

- `workflow_memory_items` persists confirmed safe field mappings.
- Review Mapping supports memory save policy controls.
- Sensitive, one-time, non-fillable, consent, auth, and payment-like fields are
  blocked from memory.
- Field mapping can use retrieved memory as conservative fallback when rules and
  LLM mapping miss.
- Benchmark requests support memory mode.

Not complete yet:

- questionnaire-style answer memory;
- source document snippets for answer suggestions;
- stale memory warnings;
- manual memory delete/disable UI;
- source-backed suggestion display outside mapping memory.

## Features

### Reviewed Memory

When the user corrects a field mapping, save:

- field label
- field name
- placeholder
- selector
- selected profile key
- reviewed value type
- timestamp
- source task id
- safe to reuse flag

For questionnaire-style answers, also save:

- question text
- reviewed answer
- source document or source field
- review status

### Memory Retrieval

For new fields or questions, retrieve similar reviewed examples.

Minimum implementation:

- Start with SQLite text search or simple text similarity.
- Add embeddings later only as an optional benchmark baseline.

### UI Explanation

On Review Mapping, show:

```text
Source: reviewed memory
Similar previous field: Portfolio URL
Mapped key: github
Confidence: 91%
```

For questionnaire answers:

```text
Source: mock-security-policy.md
Matched section: Data retention
Suggested answer: 90 days
Status: needs review
```

### Memory Controls

User can choose:

- Auto save
- Do not save
- Force save when safe

Sensitive fields must never be saved.
Unsupported answers must never be guessed.

## Acceptance Criteria

- Reviewed corrections can influence future mappings.
- Review Mapping shows the source of each mapping.
- User can tell whether mapping came from rules, LLM, or memory.
- Questionnaire answers can show source evidence.
- Unsupported answers are marked as needs review.
- Sensitive values are blocked from memory.
- Tests cover memory save, retrieval, and skip rules.

## Demo Story

Correct a field once, rerun a similar form or questionnaire, and show that
reviewed memory improves the next suggestion with source evidence.

