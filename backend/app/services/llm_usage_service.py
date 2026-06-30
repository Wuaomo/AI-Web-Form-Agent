"""Helpers for storing and summarizing internal LLM API usage."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import LlmApiUsageLog


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

    log = LlmApiUsageLog(
        task_id=task_id,
        provider=str(usage["provider"]),
        model=str(usage["model"]),
        prompt_tokens=int(usage["prompt_tokens"]),
        completion_tokens=int(usage["completion_tokens"]),
        total_tokens=int(usage["total_tokens"]),
        cache_hit_tokens=int(usage["cache_hit_tokens"]),
        cache_miss_tokens=int(usage["cache_miss_tokens"]),
        cache_hit=bool(usage["cache_hit"]),
        cache_hit_rate=float(usage["cache_hit_rate"]),
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


def summarize_llm_usage(
    db: Session,
    task_id: int | None = None,
) -> dict[str, int | float | None]:
    """Aggregate token and cache usage across matching records."""

    logs = list_llm_usage_logs(db, task_id=task_id)
    prompt_tokens = sum(log.prompt_tokens for log in logs)
    cache_hit_tokens = sum(log.cache_hit_tokens for log in logs)

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
    }
