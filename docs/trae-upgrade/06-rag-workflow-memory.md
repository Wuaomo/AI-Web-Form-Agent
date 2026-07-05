# Phase 06 - RAG Workflow Memory

## Goal

Add retrieval-backed workflow memory so historical user corrections and successful mappings improve future field mapping.

The first version should be simple, local, and SQLite-backed. It should not require a vector database to run.

## Why This Matters

This is the clearest way to upgrade the project from "LLM API wrapper" to "AI engineering system":

- it learns from user review
- it retrieves prior examples
- it improves prompts with context
- it supports measurable memory on/off evaluations

## Current Code To Read

- `backend/app/services/mapping_cache.py`
- `backend/app/services/field_mapper.py`
- `backend/app/models.py`
- `backend/app/routers/tasks.py`
- `backend/app/services/benchmark_runner.py`
- `backend/tests/test_field_mapper.py`
- `backend/tests/test_task_mapping_endpoint.py`

## Scope

Add:

- workflow memory table
- save confirmed mappings as memory
- retrieval service for similar fields
- optional prompt augmentation for LLM mapping
- benchmark flag to compare memory on/off

## Out Of Scope

- Do not add Pinecone, Weaviate, Chroma, or FAISS yet.
- Do not require embeddings API.
- Do not store sensitive values.
- Do not store password/OTP/payment/consent fields.
- Do not replace existing mapping cache.

## Memory Model

Add `WorkflowMemoryItem` in `backend/app/models.py`:

```python
class WorkflowMemoryItem(Base):
    __tablename__ = "workflow_memory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(50), default="form_fill", nullable=False)
    source_domain: Mapped[Optional[str]] = mapped_column(String(300))
    field_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    field_text: Mapped[str] = mapped_column(Text, nullable=False)
    mapped_profile_key: Mapped[str] = mapped_column(String(100), nullable=False)
    value_kind: Mapped[str] = mapped_column(String(50), default="profile_value", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
```

`field_text` should contain normalized non-sensitive field context:

```text
label: GitHub
name: github_url
placeholder: https://github.com/...
type: url
options: []
```

Do not store `mapped_value` by default. Store only `mapped_profile_key`.

## Memory Types

Add constants:

```python
MEMORY_TYPE_CONFIRMED_MAPPING = "confirmed_mapping"
MEMORY_TYPE_BENCHMARK_EXPECTED = "benchmark_expected"
MEMORY_TYPE_SUCCESSFUL_RUN = "successful_run"
```

## Field Text Builder

Create `backend/app/services/workflow_memory.py`.

Required functions:

```python
def build_field_memory_text(field: FormField) -> str:
    ...

def should_save_mapping_memory(field: FormField) -> bool:
    ...

def save_confirmed_mapping_memory(db: Session, *, task: Task, field: FormField) -> WorkflowMemoryItem | None:
    ...

def save_confirmed_mappings_for_task(db: Session, *, task: Task, fields: list[FormField]) -> list[WorkflowMemoryItem]:
    ...
```

Rules:

- skip empty mapped_profile_key
- skip non-fillable fields
- skip one-time/sensitive fields
- skip `mapped_value`; do not persist raw user value
- if same `field_signature` and `mapped_profile_key` exists, increment `success_count`

Use existing `save_user_mapping_override()` behavior as inspiration, but do not delete it.

## Retrieval Service

Create `backend/app/services/retrieval_service.py`.

Use simple lexical similarity first.

Required functions:

```python
def tokenize(text: str) -> set[str]:
    ...

def jaccard_similarity(a: str, b: str) -> float:
    ...

def search_similar_field_mappings(
    db: Session,
    *,
    field_text: str,
    workflow_type: str = "form_fill",
    source_domain: str | None = None,
    limit: int = 5,
) -> list[dict[str, object]]:
    ...
```

Scoring:

- base score: Jaccard similarity between query and memory field text
- add `0.1` if source_domain matches
- add `min(0.1, success_count * 0.01)`
- sort descending
- return only scores `>= 0.15`

Returned item:

```python
{
    "mapped_profile_key": "github",
    "field_text": "...",
    "score": 0.42,
    "source_domain": "example.com",
    "success_count": 3
}
```

## LLM Prompt Augmentation

Modify `backend/app/services/field_mapper.py`.

In `_build_llm_prompt()` or the nearest safe call site:

- accept optional `retrieved_examples`.
- include a compact section:

```text
Historical mapping examples:
- Field: "label: GitHub; placeholder: profile link" -> profile key: github
- Field: "label: Portfolio URL" -> profile key: custom:portfolio
```

Rules:

- include at most 5 examples.
- never include raw mapped values.
- if no examples, omit section.

## Mapping Flow Integration

When mapping fields with LLM:

1. Build field memory text for each field.
2. Retrieve similar mappings.
3. Pass examples to prompt.
4. If LLM fails or returns missing mapping, optionally use top retrieved mapping when score >= `0.65`.

Keep fallback conservative. Do not overwrite high-confidence existing rules mapping unless LLM mode explicitly does so already.

## Confirmation Integration

In `confirm_task_mapping()`:

- after successful profile update/skip handling, call `save_confirmed_mappings_for_task()`.
- only save memory for confirmed safe fields.

## Benchmark Support

Extend benchmark runner options:

```python
memory_mode: Literal["off", "on"] = "off"
```

For the first pass:

- `off`: no retrieval examples.
- `on`: use retrieval examples.

Add this to benchmark metadata and report.

## API Contract

No public memory API is required in this phase.

Optional debug endpoint may be added later:

```text
GET /workflow-memory/search?q=github
```

Skip it unless needed for tests.

## Tests Required

### Backend

Create `backend/tests/test_workflow_memory.py`:

- field memory text includes label/name/placeholder/type.
- sensitive fields are not saved.
- confirmed mapping saves profile key but not mapped value.
- duplicate memory increments success_count.

Create `backend/tests/test_retrieval_service.py`:

- tokenization lowercases.
- Jaccard score works.
- matching domain boosts score.
- search returns best mapping first.
- low similarity is filtered.

Update `backend/tests/test_field_mapper.py`:

- prompt includes historical examples when provided.
- prompt omits examples when empty.
- prompt never includes mapped raw values from memory.

Update benchmark tests if memory mode is added.

## Acceptance Criteria

- Confirmed safe mappings create memory items.
- Similar field mappings can be retrieved.
- LLM prompts can include retrieved examples.
- Memory does not store sensitive mapped values.
- Benchmark/report can distinguish memory on/off.
- No vector DB or embedding API is required.

## Implementation Order

1. Add `WorkflowMemoryItem` model and migration helper.
2. Add constants.
3. Add workflow memory service.
4. Add retrieval service.
5. Integrate memory save into confirm mapping.
6. Add prompt augmentation.
7. Add conservative retrieval fallback if simple.
8. Add benchmark memory mode metadata.
9. Add tests.

## Trae Prompt

Implement Phase 06. Add SQLite-backed workflow memory for confirmed safe field mappings, lexical retrieval for similar fields, prompt augmentation with historical examples, conservative integration into LLM field mapping, and tests. Do not add a vector database or store raw mapped user values.
