"""Benchmark runner API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import BenchmarkRun
from app.schemas import BenchmarkRunRequest, BenchmarkRunResponse
from app.services.benchmark_report_service import build_benchmark_markdown_report
from app.services.benchmark_request_service import normalize_benchmark_request
from app.services.benchmark_runner import run_benchmarks
from app.services.llm_provider_config import (
    get_provider_setup_hint,
    is_provider_configured,
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
    try:
        normalized = normalize_benchmark_request(options)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if normalized.execution_mode == "llm":
        if not normalized.provider:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider is required for LLM benchmarks",
            )
        if not is_provider_configured(normalized.provider):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=get_provider_setup_hint(normalized.provider),
            )
    try:
        run_benchmarks(
            mode=normalized.eval_mode,
            provider=normalized.provider,
            db=db,
            stress_mode=normalized.stress_mode,
            memory_mode=normalized.memory_mode,
            baseline_run_id=normalized.baseline_run_id,
        )
    except ValueError as exc:
        message = str(exc)
        if message == "Baseline benchmark run not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        ) from exc
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


@router.get("/runs/{run_id}/report", response_class=PlainTextResponse)
def get_benchmark_report(
    run_id: int,
    db: Session = Depends(get_db),
) -> str:
    """Return a copyable Markdown report for one benchmark run."""

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
    baseline = db.get(BenchmarkRun, run.baseline_run_id) if run.baseline_run_id else None
    return build_benchmark_markdown_report(run, baseline=baseline)

