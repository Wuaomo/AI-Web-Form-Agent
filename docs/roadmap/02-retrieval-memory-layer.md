# Phase 2: Retrieval Memory Layer

## Goal

Make the system visibly learn from reviewed corrections.

## Why

General AI Engineer roles care about RAG, embeddings, memory, and adaptive behavior. The app should show why a future mapping improved.

## Scope

Add memory source explanations and retrieval-backed mapping support.

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

### Memory Retrieval

For new fields, retrieve similar reviewed examples.

Minimum implementation:

- Start with the existing retrieval service or simple text similarity.
- Add embeddings later as an optional baseline.

### UI Explanation

On Review Mapping, show:

```text
Source: reviewed memory
Similar previous field: Portfolio URL
Mapped key: github
Confidence: 91%
```

### Memory Controls

User can choose:

- Auto save
- Do not save
- Force save when safe

Sensitive fields must never be saved.

## Acceptance Criteria

- Reviewed corrections can influence future mappings.
- Review Mapping shows the source of each mapping.
- User can tell whether mapping came from rules, LLM, or memory.
- Sensitive values are blocked from memory.
- Tests cover memory save, retrieval, and skip rules.

## Demo Story

Correct a field once, rerun a similar form, and show that memory improves the next mapping.

