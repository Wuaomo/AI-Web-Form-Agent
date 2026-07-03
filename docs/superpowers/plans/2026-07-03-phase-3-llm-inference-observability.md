# Phase 3 LLM Inference Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LLM-assisted field mapping measurable by tracking latency, token usage, prompt cache hit rate, app-level cache reuse, fallback behavior, provider failures, and estimated cost.

**Architecture:** Extend existing `LlmApiUsageLog` and mapping cache services. Record metrics at the provider-call boundary and at app-cache decision points. Expose summaries through API endpoints and frontend dashboards.

**Tech Stack:** Python, FastAPI, SQLAlchemy, SQLite, pytest, React, Vite, Node test runner.

## Global Constraints

- Do not log API keys or raw provider credentials.
- Do not log full prompt text in database.
- Do not expose sensitive mapped values in LLM usage dashboards.
- All UI text and code comments must be English.
- Cost estimates must be clearly labeled as estimates.

---

## File Structure

- Modify: `backend/app/models.py` to extend `LlmApiUsageLog` or add companion metric fields.
- Modify: `backend/app/services/llm_usage_service.py`
- Modify: `backend/app/services/field_mapper.py`
- Modify: `backend/app/services/mapping_cache.py`
- Modify: `backend/app/routers/llm_usage.py`
- Modify: `backend/app/schemas.py`
- Modify: `frontend/src/pages/TaskDetail.jsx`
- Create: `frontend/src/llmUsagePresentation.js`
- Create tests for backend service, endpoint, and frontend helpers.

---

### Task 1: Extend LLM Usage Data Model

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/tests/test_database_migrations.py`

**Fields To Add:**

```text
latency_ms: int
error_type: str | None
fallback_used: bool
cache_source: str
estimated_cost: float
```

**Allowed `cache_source` Values:**

```text
provider_prompt_cache
app_mapping_cache
user_override_cache
no_cache
```

**Steps:**
- [ ] Write failing database test creating `LlmApiUsageLog` with new fields.
- [ ] Add fields with safe defaults for existing rows.
- [ ] Add fields to `LlmApiUsageLogResponse`.
- [ ] Run: `cd backend; pytest tests/test_database_migrations.py -v`

**Acceptance Criteria:**
- Existing LLM usage endpoint still works.
- New metrics are available to service layer and API responses.

---

### Task 2: Measure Provider Call Latency

**Files:**
- Modify: `backend/app/services/field_mapper.py`
- Modify: `backend/app/services/llm_usage_service.py`
- Modify: `backend/tests/test_field_mapper.py`

**Behavior:**
- [ ] Capture start time immediately before provider API call.
- [ ] Capture end time immediately after provider response or exception.
- [ ] Store `latency_ms`.
- [ ] On provider exception, store `error_type` and `fallback_used` when fallback is used.

**Tests:**
- [ ] Successful provider call records positive `latency_ms`.
- [ ] Provider exception records `error_type`.
- [ ] Fallback path records `fallback_used=True`.
- [ ] Run: `cd backend; pytest tests/test_field_mapper.py -v`

**Acceptance Criteria:**
- Every LLM API call has latency evidence.
- Fallback behavior is visible in usage logs.

---

### Task 3: Track App-Level Cache Sources

**Files:**
- Modify: `backend/app/services/mapping_cache.py`
- Modify: `backend/app/services/field_mapper.py`
- Modify: `backend/tests/test_field_mapper.py`

**Behavior:**
- [ ] If user override cache serves the full mapping, record `cache_source=user_override_cache`.
- [ ] If app mapping cache serves the full mapping, record `cache_source=app_mapping_cache`.
- [ ] If provider is called and provider reports prompt cache tokens, record `cache_source=provider_prompt_cache`.
- [ ] If no cache is used, record `cache_source=no_cache`.
- [ ] Do not create fake provider usage logs for pure app-cache hits unless a separate app-cache metric model is added.

**Tests:**
- [ ] User override hit is detectable in mapping result metadata.
- [ ] App mapping cache hit is detectable in mapping result metadata.
- [ ] Provider prompt cache hit remains recorded from provider usage.
- [ ] Run: `cd backend; pytest tests/test_field_mapper.py -v`

**Acceptance Criteria:**
- Dashboard can distinguish provider prompt cache from app-level cache reuse.
- Repeated-run cache improvements are measurable.

---

### Task 4: Add Cost Estimation

**Files:**
- Create: `backend/app/services/llm_cost_service.py`
- Create: `backend/tests/test_llm_cost_service.py`
- Modify: `backend/app/services/llm_usage_service.py`

**Interfaces:**

```python
def estimate_llm_cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Return estimated request cost in USD."""
```

**Rules:**
- [ ] Store model pricing in a simple dictionary.
- [ ] If provider/model is unknown, return `0.0`.
- [ ] Do not fail request logging because cost is unknown.
- [ ] Label frontend value as estimated.

**Tests:**
- [ ] Known provider/model returns non-zero estimate.
- [ ] Unknown provider/model returns `0.0`.
- [ ] Zero tokens returns `0.0`.
- [ ] Run: `cd backend; pytest tests/test_llm_cost_service.py -v`

**Acceptance Criteria:**
- LLM usage summary can report estimated cost without breaking unknown models.

---

### Task 5: Expand LLM Usage Summary Service

**Files:**
- Modify: `backend/app/services/llm_usage_service.py`
- Modify: `backend/tests/test_llm_usage_endpoint.py`

**Summary Fields:**

```json
{
  "request_count": 11,
  "prompt_tokens": 27678,
  "completion_tokens": 1845,
  "total_tokens": 29523,
  "cache_hit_tokens": 6912,
  "cache_hit_rate": 0.2497,
  "average_latency_ms": 1200,
  "p95_latency_ms": 2200,
  "fallback_count": 2,
  "estimated_cost": 0.15
}
```

**Steps:**
- [ ] Add tests for average latency and p95 latency.
- [ ] Add tests for fallback count.
- [ ] Add tests for estimated cost sum.
- [ ] Preserve existing summary fields.
- [ ] Run: `cd backend; pytest tests/test_llm_usage_endpoint.py -v`

**Acceptance Criteria:**
- Old frontend code remains compatible.
- New metrics are available to new dashboard components.

---

### Task 6: Add Provider-Level Summary Endpoint

**Files:**
- Modify: `backend/app/routers/llm_usage.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/tests/test_llm_usage_endpoint.py`

**Endpoint:**

```text
GET /llm-usage/providers
```

**Response:**

```json
[
  {
    "provider": "deepseek",
    "model": "deepseek-v4-flash",
    "request_count": 11,
    "average_latency_ms": 1200,
    "p95_latency_ms": 2200,
    "cache_hit_rate": 0.85,
    "fallback_count": 0,
    "estimated_cost": 0.15
  }
]
```

**Tests:**
- [ ] Multiple providers are grouped separately.
- [ ] Empty database returns an empty list.
- [ ] Run: `cd backend; pytest tests/test_llm_usage_endpoint.py -v`

**Acceptance Criteria:**
- Provider-level performance can be compared.

---

### Task 7: Add Frontend LLM Usage Presentation Helpers

**Files:**
- Create: `frontend/src/llmUsagePresentation.js`
- Create: `frontend/src/llmUsagePresentation.test.js`

**Interfaces:**

```javascript
export function formatLatency(ms) {}
export function formatEstimatedCost(value) {}
export function formatCacheHitRate(value) {}
export function summarizeLlmUsage(summary) {}
```

**Tests:**
- [ ] `formatLatency(1200)` returns `1.2s`.
- [ ] `formatEstimatedCost(0)` returns `Not estimated`.
- [ ] `formatCacheHitRate(0.8546)` returns `85%`.
- [ ] Missing summary returns safe empty values.
- [ ] Run: `cd frontend; npm test -- llmUsagePresentation.test.js`

**Acceptance Criteria:**
- UI formatting is consistent and tested.

---

### Task 8: Update Task Detail LLM Usage UI

**Files:**
- Modify: `frontend/src/pages/TaskDetail.jsx`
- Modify: `frontend/src/styles.css`

**UI Fields:**
- [ ] Requests
- [ ] Total tokens
- [ ] Prompt cache hit rate
- [ ] Average latency
- [ ] P95 latency
- [ ] Fallback count
- [ ] Estimated cost

**Rules:**
- [ ] Show `No LLM usage yet.` when request count is zero.
- [ ] Do not show raw provider payloads.
- [ ] Use compact cards, not a large table.

**Acceptance Criteria:**
- Task Detail explains LLM cost/performance at a glance.

---

### Task 9: End-To-End Verification

**Commands:**
- [ ] Run: `cd backend; pytest -v`
- [ ] Run: `cd frontend; npm run lint`
- [ ] Run: `cd frontend; npm test`
- [ ] Run: `cd frontend; npm run build`

**Manual Verification:**
- [ ] Run one semantic mapping request.
- [ ] Confirm latency, tokens, cache hit rate, fallback count, and estimated cost appear.
- [ ] Run repeated mapping and confirm cache metrics change.

**Done Criteria:**
- LLM mapping is measurable by latency, cost, token, cache, and fallback behavior.

