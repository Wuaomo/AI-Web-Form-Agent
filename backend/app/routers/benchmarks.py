"""Benchmark runner API endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import BenchmarkCaseResult, BenchmarkRun
from app.schemas import BenchmarkRunRequest, BenchmarkRunResponse
from app.services.benchmark_runner import BenchmarkRunSummary, run_benchmarks

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


def _persist_benchmark_summary(
    db: Session,
    summary: BenchmarkRunSummary,
) -> BenchmarkRun:
    """Persist a benchmark summary and its case results."""

    run = BenchmarkRun(
        mode=summary.mode,
        provider=summary.provider,
        total_cases=summary.total_cases,
        average_score=summary.average_score,
        summary_metrics_json=json.dumps(summary.summary_metrics),
    )
    db.add(run)
    db.flush()
    for result in summary.case_results:
        db.add(
            BenchmarkCaseResult(
                run_id=run.id,
                case_id=result["case_id"],
                title=result["title"],
                metrics_json=json.dumps(result["metrics"]),
                failures_json=json.dumps(result["failures"]),
            )
        )
    db.commit()
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
    summary = run_benchmarks(mode=options.mode, provider=options.provider)
    run = _persist_benchmark_summary(db, summary)
    statement = (
        select(BenchmarkRun)
        .options(selectinload(BenchmarkRun.case_results))
        .where(BenchmarkRun.id == run.id)
    )
    return db.scalar(statement)


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

