# Phase 7: Retrieval Quality and Memory Governance

## Goal

Make reviewed workflow memory visible and removable so stale or incorrect
memory does not silently shape future mappings.

## Current Status

Implemented in this branch:

- Admin endpoint to list workflow memory with source, profile key, reviewed time,
  and stale status.
- Admin endpoint to delete one workflow memory item.
- React Memory page for reviewing and deleting saved mapping memory.

Still not included:

- Disable-without-delete state.
- Per-profile memory filters.
- Rich source lineage beyond the stored source domain and field text.

