"""Helpers for storing and summarizing internal LLM API usage."""

import statistics

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import LlmApiUsageLog
from app.services.llm_cost_service import estimate_llm_cost

CacheSource = Literal[
    "provider_prompt_cache",
    "app_mapping_cache",
    "user_override_cache",
    "no_cache",
]


@dataclass(frozen=True)
class LLMUsageData:
    """Normalized token usage fields across LLM providers."""

    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    latency_ms: int = 0
    error_type: str | None = None
    fallback_used: bool = False
    cache_source: CacheSource = "no_cache"
    estimated_cost: float = 0.0

    @property
    def cache_hit(self) -> bool:
        return self.cache_hit_tokens > 0

    @property
    def cache_hit_rate(self) -> float:
        if self.prompt_tokens <= 0:
            return 0.0
        return self.cache_hit_tokens / self.prompt_tokens


def record_llm_api_usage(
    task_id: int,
    usage: dict[str, object],
    db: Session | None = None,
) -> LlmApiUsageLog | None:
    """Persist one usage payload and return the saved record."""

    if usage.get("usage_available") is False:
        return None

    required_keys = (
        "provider",
        "model",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cache_hit_tokens",
        "cache_miss_tokens",
        "cache_hit",
        "cache_hit_rate",
    )
    if any(key not in usage for key in required_keys):
        return None

    prompt_tokens = int(usage["prompt_tokens"])
    completion_tokens = int(usage["completion_tokens"])

    estimated_cost = usage.get("estimated_cost")
    if estimated_cost is None:
        estimated_cost = estimate_llm_cost(
            provider=str(usage["provider"]),
            model=str(usage["model"]),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    log = LlmApiUsageLog(
        task_id=task_id,
        provider=str(usage["provider"]),
        model=str(usage["model"]),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=int(usage["total_tokens"]),
        cache_hit_tokens=int(usage["cache_hit_tokens"]),
        cache_miss_tokens=int(usage["cache_miss_tokens"]),
        cache_hit=bool(usage["cache_hit"]),
        cache_hit_rate=float(usage["cache_hit_rate"]),
        latency_ms=int(usage.get("latency_ms", 0)),
        error_type=str(usage["error_type"]) if usage.get("error_type") else None,
        fallback_used=bool(usage.get("fallback_used", False)),
        cache_source=str(usage.get("cache_source", "no_cache")),
        estimated_cost=float(estimated_cost),
    )

    if db is not None:
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    with SessionLocal() as session:
        session.add(log)
        session.commit()
        session.refresh(log)
        session.expunge(log)
        return log


def create_llm_usage_log(
    task_id: int,
    usage: LLMUsageData,
    db: Session,
) -> LlmApiUsageLog | None:
    """Compatibility wrapper for callers with normalized usage dataclasses."""

    return record_llm_api_usage(
        task_id=task_id,
        usage={
            "provider": usage.provider,
            "model": usage.model,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "cache_hit_tokens": usage.cache_hit_tokens,
            "cache_miss_tokens": usage.cache_miss_tokens,
            "cache_hit": usage.cache_hit,
            "cache_hit_rate": usage.cache_hit_rate,
            "latency_ms": usage.latency_ms,
            "error_type": usage.error_type,
            "fallback_used": usage.fallback_used,
            "cache_source": usage.cache_source,
            "estimated_cost": usage.estimated_cost,
        },
        db=db,
    )


def list_llm_usage_logs(
    db: Session,
    task_id: int | None = None,
) -> list[LlmApiUsageLog]:
    """Return usage records ordered oldest first."""

    statement = select(LlmApiUsageLog)
    if task_id is not None:
        statement = statement.where(LlmApiUsageLog.task_id == task_id)
    statement = statement.order_by(
        LlmApiUsageLog.created_at,
        LlmApiUsageLog.id,
    )
    return list(db.scalars(statement))


def get_latest_llm_usage_log(
    db: Session,
    task_id: int,
) -> LlmApiUsageLog | None:
    """Return the newest LLM usage record for one task."""

    statement = (
        select(LlmApiUsageLog)
        .where(LlmApiUsageLog.task_id == task_id)
        .order_by(LlmApiUsageLog.created_at.desc(), LlmApiUsageLog.id.desc())
    )
    return db.scalar(statement)


def summarize_llm_usage(
    db: Session,
    task_id: int | None = None,
) -> dict[str, int | float | None]:
    """Aggregate token and cache usage across matching records."""

    logs = list_llm_usage_logs(db, task_id=task_id)
    return _calculate_summary(logs, task_id=task_id)


def _calculate_summary(
    logs: list[LlmApiUsageLog],
    task_id: int | None = None,
) -> dict[str, int | float | None]:
    """Calculate summary metrics from a list of usage logs."""

    prompt_tokens = sum(log.prompt_tokens for log in logs)
    cache_hit_tokens = sum(log.cache_hit_tokens for log in logs)
    latency_values = [log.latency_ms for log in logs]

    return {
        "task_id": task_id,
        "request_count": len(logs),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": sum(log.completion_tokens for log in logs),
        "total_tokens": sum(log.total_tokens for log in logs),
        "cache_hit_tokens": cache_hit_tokens,
        "cache_miss_tokens": sum(log.cache_miss_tokens for log in logs),
        "cache_hit_rate": (
            cache_hit_tokens / prompt_tokens if prompt_tokens else 0
        ),
        "average_latency_ms": (
            int(statistics.mean(latency_values)) if latency_values else 0
        ),
        "p95_latency_ms": (
            int(statistics.quantiles(latency_values, n=100)[94])
            if len(latency_values) >= 20
            else (max(latency_values) if latency_values else 0)
        ),
        "fallback_count": sum(1 for log in logs if log.fallback_used),
        "estimated_cost": sum(log.estimated_cost for log in logs),
    }


def summarize_llm_usage_by_provider(
    db: Session,
) -> list[dict[str, str | int | float]]:
    """Return aggregated LLM usage grouped by provider and model."""

    logs = list_llm_usage_logs(db)

    groups: dict[tuple[str, str], list[LlmApiUsageLog]] = {}
    for log in logs:
        key = (log.provider, log.model)
        if key not in groups:
            groups[key] = []
        groups[key].append(log)

    results = []
    for (provider, model), group_logs in groups.items():
        prompt_tokens = sum(log.prompt_tokens for log in group_logs)
        cache_hit_tokens = sum(log.cache_hit_tokens for log in group_logs)
        latency_values = [log.latency_ms for log in group_logs]

        results.append({
            "provider": provider,
            "model": model,
            "request_count": len(group_logs),
            "average_latency_ms": (
                int(statistics.mean(latency_values)) if latency_values else 0
            ),
            "p95_latency_ms": (
                int(statistics.quantiles(latency_values, n=100)[94])
                if len(latency_values) >= 20
                else (max(latency_values) if latency_values else 0)
            ),
            "cache_hit_rate": (
                cache_hit_tokens / prompt_tokens if prompt_tokens else 0
            ),
            "fallback_count": sum(1 for log in group_logs if log.fallback_used),
            "estimated_cost": sum(log.estimated_cost for log in group_logs),
        })

    return sorted(results, key=lambda x: x["provider"])
