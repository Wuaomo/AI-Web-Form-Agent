"""Helpers for recording and reading LLM token usage."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LLMApiUsageLog


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

    @property
    def cache_hit(self) -> bool:
        return self.cache_hit_tokens > 0

    @property
    def cache_hit_rate(self) -> float:
        if self.prompt_tokens <= 0:
            return 0.0
        return self.cache_hit_tokens / self.prompt_tokens


def create_llm_usage_log(
    task_id: int,
    usage: LLMUsageData,
    db: Session,
) -> LLMApiUsageLog:
    """Add one normalized provider usage record to the current transaction."""

    log = LLMApiUsageLog(
        task_id=task_id,
        provider=usage.provider,
        model=usage.model,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        cache_hit_tokens=usage.cache_hit_tokens,
        cache_miss_tokens=usage.cache_miss_tokens,
        cache_hit=usage.cache_hit,
        cache_hit_rate=usage.cache_hit_rate,
    )
    db.add(log)
    return log


def list_llm_usage_logs(task_id: int, db: Session) -> list[LLMApiUsageLog]:
    """Return usage rows for one task in chronological order."""

    statement = (
        select(LLMApiUsageLog)
        .where(LLMApiUsageLog.task_id == task_id)
        .order_by(LLMApiUsageLog.created_at, LLMApiUsageLog.id)
    )
    return list(db.scalars(statement))
