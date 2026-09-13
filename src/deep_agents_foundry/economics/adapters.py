"""Thin adapters that turn P8C outputs into P8D ``EconomicsRun`` records (P8D).

Dependency direction is one-way: P8D consumes P8C outputs. These helpers read the
per-run trajectory/usage fields that the improvement runner already collects
(``RunRecord.metrics``, ``latency_seconds``, ``quality``) and never modify P8C.

Cost, human-effort, and business-value fields are *not* present in P8C data, so
they are only populated when the caller supplies them explicitly — nothing is
invented.
"""

from __future__ import annotations

from typing import Any

from ..improvement.models import ComparisonReport, RunRecord, VariantResult
from .models import EconomicsRun


def _success_from_checks(record: RunRecord) -> bool | None:
    """Derive task success from boolean checks, or ``None`` when none exist."""
    checks = [value for value in record.checks.values() if isinstance(value, bool)]
    return all(checks) if checks else None


def economics_run_from_run_record(
    record: RunRecord,
    architecture: str,
    *,
    run_id: str | None = None,
    task_success: bool | None = None,
    success_from_checks: bool = False,
    agent_cost: float | None = None,
    human_review_minutes: float | None = None,
    human_rework_minutes: float | None = None,
    hourly_human_cost: float | None = None,
    failure_cost: float | None = None,
    business_value_if_success: float | None = None,
    extra_metrics: dict[str, Any] | None = None,
) -> EconomicsRun:
    """Convert one P8C ``RunRecord`` into an ``EconomicsRun``.

    Operational metrics come straight from ``record.metrics`` (missing ones stay
    ``None``). ``task_success`` may be passed explicitly; alternatively set
    ``success_from_checks=True`` to derive it from the record's boolean checks.
    Economic inputs (cost, human effort, business value) are only set when
    supplied by the caller.
    """
    metrics = record.metrics or {}
    extra = extra_metrics or {}

    resolved_success = task_success
    if resolved_success is None and success_from_checks:
        resolved_success = _success_from_checks(record)

    return EconomicsRun(
        task_id=record.case_id,
        architecture=architecture,
        complexity=record.complexity,
        run_id=run_id or record.thread_id,
        input_tokens=metrics.get("input_tokens"),
        output_tokens=metrics.get("output_tokens"),
        total_tokens=metrics.get("total_tokens"),
        model_calls=metrics.get("model_calls"),
        web_searches=metrics.get("web_searches"),
        tool_calls=metrics.get("tool_calls"),
        subagent_calls=metrics.get("subagent_calls"),
        memory_reads=extra.get("memory_reads", metrics.get("memory_reads")),
        skill_loads=extra.get("skill_loads", metrics.get("skill_loads")),
        summarization_calls=extra.get(
            "summarization_calls", metrics.get("summarization_calls")
        ),
        latency_seconds=record.latency_seconds,
        quality_score=record.quality,
        task_success=resolved_success,
        agent_cost=agent_cost,
        human_review_minutes=human_review_minutes,
        human_rework_minutes=human_rework_minutes,
        hourly_human_cost=hourly_human_cost,
        failure_cost=failure_cost,
        business_value_if_success=business_value_if_success,
    )


def economics_runs_from_variant_result(
    variant: VariantResult,
    architecture: str | None = None,
    *,
    success_from_checks: bool = False,
) -> list[EconomicsRun]:
    """Convert every ``RunRecord`` in a P8C ``VariantResult`` to economics runs.

    ``architecture`` defaults to the variant's label so a variant maps naturally
    onto one architecture.
    """
    label = architecture or variant.label
    return [
        economics_run_from_run_record(
            record, label, success_from_checks=success_from_checks
        )
        for record in variant.records
    ]


def economics_runs_from_comparison_report(
    report: ComparisonReport,
    *,
    baseline_architecture: str | None = None,
    candidate_architecture: str | None = None,
    success_from_checks: bool = False,
) -> list[EconomicsRun]:
    """Convert both sides of a P8C ``ComparisonReport`` into economics runs.

    Each case contributes a baseline run and a candidate run, labelled with the
    respective architecture (defaulting to the report's variant labels). The two
    architectures can then be aggregated and placed on the value frontier.
    """
    baseline_label = baseline_architecture or report.baseline_label
    candidate_label = candidate_architecture or report.candidate_label

    runs: list[EconomicsRun] = []
    for case in report.case_comparisons:
        runs.append(
            economics_run_from_run_record(
                case.baseline,
                baseline_label,
                success_from_checks=success_from_checks,
            )
        )
        runs.append(
            economics_run_from_run_record(
                case.candidate,
                candidate_label,
                success_from_checks=success_from_checks,
            )
        )
    return runs
