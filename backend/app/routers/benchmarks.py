"""Benchmark runner API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import BenchmarkRun
from app.schemas import BenchmarkRunRequest, BenchmarkRunResponse
from app.services.benchmark_runner import run_benchmarks
from app.services.llm_provider_config import (
    get_provider_setup_hint,
    is_provider_configured,
    resolve_llm_provider,
)

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


def _load_latest_benchmark_run(db: Session) -> BenchmarkRun:
    run = db.scalar(
        select(BenchmarkRun)
        .options(selectinload(BenchmarkRun.case_results))
        .order_by(BenchmarkRun.id.desc())
        .limit(1)
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Benchmark run could not be loaded",
        )
    return run


@router.post(
    "/run",
    response_model=BenchmarkRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_benchmark_suite(
    request: BenchmarkRunRequest | None = None,
    db: Session = Depends(get_db),
) -> BenchmarkRun:
    """Run the local benchmark suite and persist metrics."""

    options = request or BenchmarkRunRequest()
    if options.mode == "rules":
        run_benchmarks(mode="rules", provider=None, db=db)
        return _load_latest_benchmark_run(db)

    if not options.provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider is required for LLM benchmarks",
        )

    try:
        selected_provider = resolve_llm_provider(options.provider)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not is_provider_configured(selected_provider):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=get_provider_setup_hint(selected_provider),
        )

    run_benchmarks(mode="llm", provider=selected_provider, db=db)
    return _load_latest_benchmark_run(db)


@router.get("/runs", response_model=list[BenchmarkRunResponse])
def list_benchmark_runs(db: Session = Depends(get_db)) -> list[BenchmarkRun]:
    """Return benchmark runs, newest first."""

    return list(
        db.scalars(
            select(BenchmarkRun)
            .options(selectinload(BenchmarkRun.case_results))
            .order_by(BenchmarkRun.created_at.desc(), BenchmarkRun.id.desc())
        )
    )


@router.get("/runs/{run_id}", response_model=BenchmarkRunResponse)
def get_benchmark_run(
    run_id: int,
    db: Session = Depends(get_db),
) -> BenchmarkRun:
    """Return one benchmark run with case-level details."""

    run = db.scalar(
        select(BenchmarkRun)
        .options(selectinload(BenchmarkRun.case_results))
        .where(BenchmarkRun.id == run_id)
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Benchmark run not found",
        )
    return run

