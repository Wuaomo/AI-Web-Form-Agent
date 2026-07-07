"""Normalization helpers for benchmark/evaluation run requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.schemas import BenchmarkRunRequest
from app.services.llm_provider_config import resolve_llm_provider

ExecutionMode = Literal["rules", "llm"]


@dataclass(frozen=True)
class NormalizedBenchmarkRequest:
    eval_mode: str
    execution_mode: ExecutionMode
    provider: str | None
    stress_mode: str
    memory_mode: str
    mode_detail: str
    baseline_run_id: int | None


def build_mode_detail(*, stress_mode: str, memory_mode: str) -> str:
    return f"stress_mode={stress_mode};memory_mode={memory_mode}"


def normalize_benchmark_request(options: BenchmarkRunRequest) -> NormalizedBenchmarkRequest:
    eval_mode = options.mode
    stress_mode = options.stress_mode
    baseline_run_id = options.baseline_run_id

    if eval_mode in {"rules", "full_workflow"}:
        memory_mode = "off"
        provider = None
        return NormalizedBenchmarkRequest(
            eval_mode=eval_mode,
            execution_mode="rules",
            provider=provider,
            stress_mode=stress_mode,
            memory_mode=memory_mode,
            mode_detail=build_mode_detail(stress_mode=stress_mode, memory_mode=memory_mode),
            baseline_run_id=baseline_run_id,
        )

    provider_raw = options.provider
    if not provider_raw:
        raise ValueError("Provider is required for LLM benchmarks")
    provider = resolve_llm_provider(provider_raw)

    if eval_mode == "rag_llm":
        memory_mode = "on"
    else:
        memory_mode = options.memory_mode

    return NormalizedBenchmarkRequest(
        eval_mode=eval_mode,
        execution_mode="llm",
        provider=provider,
        stress_mode=stress_mode,
        memory_mode=memory_mode,
        mode_detail=build_mode_detail(stress_mode=stress_mode, memory_mode=memory_mode),
        baseline_run_id=baseline_run_id,
    )
