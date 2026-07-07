# Phase 06 - RAG Workflow Memory (Implementation Plan)

**Goal:** Add SQLite-backed workflow memory for confirmed safe mappings, lexical retrieval for similar fields, prompt augmentation with historical examples, conservative retrieval fallback, and benchmark `memory_mode` on/off.

**Hard boundaries:**
- No vector DB / embeddings API / rerank.
- Do not persist raw `mapped_value`. Persist only `mapped_profile_key` + non-sensitive `field_text`.
- Skip sensitive / one-time / non-fillable fields for both saving and fallback.
- Do not replace `mapping_cache` or user override cache.
- Do not change worker, queue, or browser executor runtime orchestration.
- No debug/public memory API.

## Step 1 - Data Model + SQLite Migration Helper

**Files**
- Modify: `backend/app/models.py`
- Modify: `backend/app/database.py`
- Modify: `backend/app/workflow_constants.py`
- Modify: `backend/tests/test_database_migrations.py`

**Work**
- Add SQLAlchemy model `WorkflowMemoryItem` (`workflow_memory_items`) as per spec.
- Add constants:
  - `MEMORY_TYPE_CONFIRMED_MAPPING`
  - `MEMORY_TYPE_BENCHMARK_EXPECTED`
  - `MEMORY_TYPE_SUCCESSFUL_RUN`
- Extend SQLite migration helper to create `workflow_memory_items` when missing.
- Add migration test coverage for table existence.

## Step 2 - workflow_memory Service (Save Side)

**Files**
- Create: `backend/app/services/workflow_memory.py`
- Create: `backend/tests/test_workflow_memory.py`

**Work**
- Implement:
  - `build_field_memory_text(field)`
  - `should_save_mapping_memory(field)`
  - `save_confirmed_mapping_memory(db, task, field)`
  - `save_confirmed_mappings_for_task(db, task, fields)`
- Ensure:
  - `mapped_profile_key` required
  - skip non-fillable
  - skip one-time
  - skip sensitive categories (password/otp/payment/consent/token/secret)
  - no `mapped_value` persisted
  - duplicates increment `success_count`
- Save is best-effort: failures never break confirm-mapping.

## Step 3 - retrieval_service (Search Side)

**Files**
- Create: `backend/app/services/retrieval_service.py`
- Create: `backend/tests/test_retrieval_service.py`

**Work**
- Implement:
  - `tokenize`
  - `jaccard_similarity`
  - `search_similar_field_mappings`
- Ensure scoring rules and filters match spec (`>=0.15`, domain boost, success_count boost).

## Step 4 - Integrate Memory Save Into confirm-mapping

**Files**
- Modify: `backend/app/routers/tasks.py`
- Update tests if required: `backend/tests/test_task_mapping_endpoint.py`

**Work**
- After confirm-mapping success path, call `save_confirmed_mappings_for_task`.
- Ensure best-effort: errors do not block confirm mapping.

## Step 5 - Prompt Augmentation + Conservative Fallback In LLM Mapping

**Files**
- Modify: `backend/app/services/field_mapper.py`
- Update: `backend/tests/test_field_mapper.py`

**Work**
- Add prompt section “Historical mapping examples” (<=5).
- Ensure prompt never includes raw values.
- Retrieval integration:
  - Only in LLM mapping path
  - Build `field_text` per field
  - Retrieve examples (optionally filtered by source_domain)
- Conservative fallback (required):
  - Only when rules and LLM provide no `mapped_profile_key`
  - Only top1 and score >= 0.65
  - Only for eligible fields
  - Only sets `mapped_profile_key`
  - Never overrides existing mapping/override
- Add tests for:
  - does not override existing mapping
  - low score does not trigger
  - hit triggers profile key only

## Step 6 - Benchmark memory_mode on/off

**Files**
- Modify: `backend/app/services/benchmark_runner.py`
- Modify: `backend/app/routers/benchmarks.py`
- Modify: `backend/app/services/benchmark_report_service.py`
- Update tests that validate benchmark metadata/reporting.

**Work**
- Add `memory_mode: Literal["off","on"]="off"` to benchmark run options.
- Wire it into `run_benchmarks` and the LLM mapping path.
- Ensure `off` disables retrieval/examples/fallback, `on` enables them.
- Include `memory_mode` in run metadata and markdown report output.

## Step 7 - Run Tests

**Backend**
```bash
python -m pytest backend/tests -q
```

**Frontend**
```bash
npm test
```

**Done when**
- New tests pass.
- No sensitive values stored.
- Memory on/off is visible in benchmark metadata/report.
- Existing mapping cache & runtime orchestration remain unchanged.

