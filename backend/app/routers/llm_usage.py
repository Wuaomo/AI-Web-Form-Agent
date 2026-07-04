"""Internal LLM usage reporting endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import LlmUsageSummaryResponse, ProviderLlmUsageSummaryResponse
from app.services.llm_usage_service import summarize_llm_usage, summarize_llm_usage_by_provider

router = APIRouter(prefix="/llm-usage", tags=["llm-usage"])


@router.get("/summary", response_model=LlmUsageSummaryResponse)
def get_llm_usage_summary(
    db: Session = Depends(get_db),
) -> dict[str, int | float | None]:
    """Return aggregate LLM usage across all tasks."""

    return summarize_llm_usage(db)


@router.get("/providers", response_model=list[ProviderLlmUsageSummaryResponse])
def get_llm_usage_by_provider(
    db: Session = Depends(get_db),
) -> list[dict[str, str | int | float]]:
    """Return aggregate LLM usage grouped by provider and model."""

    return summarize_llm_usage_by_provider(db)
