# Phase 06 - RAG Workflow Memory (Design)

## Goal

Add retrieval-backed workflow memory so historical user corrections and successful confirmed mappings improve future field mapping quality.

The first version must be simple, local, and SQLite-backed. It must not require embeddings, a vector database, or a re-ranker.

This phase must form a minimal closed loop:

1. confirmed safe mappings → memory
2. memory → lexical retrieval
3. retrieval → mapping improvement (prompt examples + conservative fallback)

## Non-Goals / Hard Constraints

- No vector database (Pinecone / Weaviate / Chroma / FAISS).
- No embeddings API.
- No rerank.
- No debug/public memory API.
- Do not store sensitive values.
- Do not store `mapped_value` by default. Persist only `mapped_profile_key`.
- Do not store password/OTP/payment/consent/token/secret fields.
- Do not replace or delete existing `mapping_cache` or `save_user_mapping_override()` behavior.
- Do not change worker, queue, or browser executor runtime logic.

## Existing Code Surfaces

- Mapping cache and stable signatures: [mapping_cache.py](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/backend/app/services/mapping_cache.py)
- LLM mapping flow + prompt builder: [field_mapper.py](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/backend/app/services/field_mapper.py)
- Confirmation endpoint where mappings become “confirmed”: [tasks.py:confirm_task_mapping](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/backend/app/routers/tasks.py#L1167-L1437)
- Benchmark runner and report: [benchmark_runner.py](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/backend/app/services/benchmark_runner.py), [benchmark_report_service.py](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/backend/app/services/benchmark_report_service.py)
- Existing safety heuristics: [tasks.py:is_one_time_field](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/backend/app/routers/tasks.py#L227-L238), [policy_engine.py](file:///c:/Users/wuaomo/Documents/AI%20Web%20Form%20Agent/backend/app/services/policy_engine.py)

## Data Model

Add `WorkflowMemoryItem` in `backend/app/models.py`:

- `__tablename__ = "workflow_memory_items"`
- `id`: int PK
- `memory_type`: str (see constants)
- `workflow_type`: str default `"form_fill"`
- `source_domain`: optional str (host extracted from task url)
- `field_signature`: str (stable signature compatible with mapping_cache)
- `field_text`: str (normalized non-sensitive field context)
- `mapped_profile_key`: str (profile key only)
- `value_kind`: str default `"profile_value"` (reserved for future use)
- `confidence`: float default `1.0` (reserved)
- `success_count`: int default `1`
- `last_used_at`: datetime nullable
- `created_at`: datetime default now

### Field Text Format

`field_text` must contain normalized non-sensitive context only, e.g.:

```text
label: GitHub
name: github_url
placeholder: https://github.com/...
type: url
options: []
```

### Memory Types (Constants)

Add constants (in `backend/app/workflow_constants.py` or a dedicated memory constants module if preferred):

- `MEMORY_TYPE_CONFIRMED_MAPPING = "confirmed_mapping"`
- `MEMORY_TYPE_BENCHMARK_EXPECTED = "benchmark_expected"`
- `MEMORY_TYPE_SUCCESSFUL_RUN = "successful_run"`

This phase primarily uses `confirmed_mapping`.

## Database Migration Strategy (SQLite)

Use the existing migration-like helper approach in `backend/app/database.py`:

- Ensure table `workflow_memory_items` exists on startup/init.
- Keep it SQLite-friendly (no advanced DDL).

## Workflow Memory Service (Save Side)

Create `backend/app/services/workflow_memory.py` with required functions:

- `build_field_memory_text(field: FormField) -> str`
- `should_save_mapping_memory(field: FormField) -> bool`
- `save_confirmed_mapping_memory(db: Session, *, task: Task, field: FormField) -> WorkflowMemoryItem | None`
- `save_confirmed_mappings_for_task(db: Session, *, task: Task, fields: list[FormField]) -> list[WorkflowMemoryItem]`

### Save Rules (Must Follow)

`should_save_mapping_memory()` returns `False` if any is true:

- `field.mapped_profile_key` missing/empty
- `field` is not fillable
- one-time field detection indicates ephemeral / action-like intent
- policy engine indicates sensitive/blocked for memory write (password/token/secret/otp/payment/consent)

Save behavior:

- Never persist `mapped_value`.
- Compute `field_signature` using the same logic as `mapping_cache.field_signature(...)` (or call it directly).
- Use `task.url` to derive `source_domain`.
- If an item exists with the same `field_signature` and `mapped_profile_key`, increment `success_count`, update `last_used_at`, and keep a single row.

### Failure Isolation

Saving memory must be best-effort:

- Exceptions in memory save must not fail `confirm_task_mapping()`.
- The endpoint must remain successful if memory persistence fails.

## Retrieval Service (Search Side)

Create `backend/app/services/retrieval_service.py` with required functions:

- `tokenize(text: str) -> set[str]`
- `jaccard_similarity(a: str, b: str) -> float`
- `search_similar_field_mappings(db: Session, *, field_text: str, workflow_type: str = "form_fill", source_domain: str | None = None, limit: int = 5) -> list[dict[str, object]]`

### Scoring

- Base score: Jaccard similarity between query and memory `field_text`
- + `0.1` if `source_domain` matches
- + `min(0.1, success_count * 0.01)`
- Filter: return only items with `score >= 0.15`
- Sort descending score, return up to `limit`

Returned item structure:

```python
{
  "mapped_profile_key": "...",
  "field_text": "...",
  "score": 0.42,
  "source_domain": "example.com",
  "success_count": 3
}
```

## LLM Prompt Augmentation

Modify `backend/app/services/field_mapper.py`:

- Extend `_build_llm_prompt()` (or nearest safe call site) to accept optional `retrieved_examples`.
- Add a compact section when examples exist:

```text
Historical mapping examples:
- Field: "label: GitHub; placeholder: profile link" -> profile key: github
- Field: "label: Portfolio URL" -> profile key: custom:portfolio
```

Rules:

- At most 5 examples.
- Never include raw mapped values.
- If no examples, omit the section entirely.

## Mapping Flow Integration (Retrieval + Conservative Fallback)

Integrate retrieval only in the LLM mapping path (not rules-only).

Per field:

1. Build `field_text` using `build_field_memory_text(field)`.
2. Retrieve similar mappings via `search_similar_field_mappings(...)`.
3. Pass retrieved examples into the LLM prompt.

### Conservative Fallback (Required In This Phase)

Fallback is allowed only when all constraints hold:

- The field is eligible (fillable, non-sensitive, non-one-time).
- Both rules and LLM fail to provide `mapped_profile_key` (empty / missing).
- Retrieval returns at least one candidate.
- Use only the top match.
- Top match `score >= 0.65`.
- Do not override any existing mapping (if a key already exists, keep it).
- The fallback sets only `mapped_profile_key` (no `mapped_value`).

This fallback must not change behavior for fields already mapped by rules, user override cache, or LLM.

## Confirmation Integration (Persist Confirmed Mappings)

In `confirm_task_mapping()`:

- After the existing “profile update / skip / approval handling” completes successfully, call `save_confirmed_mappings_for_task(...)`.
- Only pass confirmed safe fields.
- Errors must not fail the endpoint.

## Benchmark Support (memory_mode)

Extend benchmark runner options:

- `memory_mode: Literal["off", "on"] = "off"`

Behavior:

- `off`: no retrieval examples and no fallback.
- `on`: retrieval examples + conservative fallback behavior enabled.

Reporting:

- Include `memory_mode` in benchmark metadata.
- Include `memory_mode` in the generated markdown report.

## Tests

Create:

- `backend/tests/test_workflow_memory.py`
  - field memory text includes label/name/placeholder/type
  - sensitive fields are not saved
  - confirmed mapping saves profile key but not mapped value
  - duplicates increment success_count
- `backend/tests/test_retrieval_service.py`
  - tokenization lowercases
  - Jaccard similarity works
  - domain match boosts score
  - success_count boosts score
  - low similarity filtered
  - best mapping returned first

Update:

- `backend/tests/test_field_mapper.py`
  - prompt includes historical examples when provided
  - prompt omits examples when empty
  - prompt never includes raw values from memory
  - fallback tests:
    - does not override existing mapping
    - low score does not trigger
    - when triggered it sets only `mapped_profile_key`

Benchmark tests:

- Update or add minimal coverage proving `memory_mode` reaches runner metadata/report output (no need to assert score changes).

## Acceptance Criteria

- Confirmed safe mappings create memory items.
- Similar field mappings can be retrieved.
- LLM prompts can include retrieved examples.
- Memory does not store sensitive mapped values.
- Conservative fallback improves mapping only when rules+LLM yield no key and score threshold is met.
- Benchmark/report can distinguish memory on/off.
- No vector DB, embeddings, rerank, or debug API required.

