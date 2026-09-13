"""Architecture aggregation, comparison, and marginal-return analysis (P8D).

Aggregation groups repeated runs by architecture and (by default) complexity, so
economics can be judged per task-complexity rather than only on global averages.
Comparison keeps every metric as an explicit delta — there is no combined score.
Marginal-return analysis is descriptive and conservative: it reports observed
diminishing returns and a candidate elbow, never statistical certainty.
"""

from __future__ import annotations

from . import metrics
from .models import (
    ArchitectureSummary,
    EconomicsComparison,
    EconomicsRun,
    MarginalReturnAnalysis,
    MarginalReturnPoint,
)

# Comparable aggregate metrics for architecture-vs-architecture deltas.
_COMPARISON_FIELDS = (
    "avg_quality",
    "success_rate",
    "avg_total_tokens",
    "avg_latency_seconds",
    "avg_web_searches",
    "avg_model_calls",
    "avg_tool_calls",
    "avg_subagent_calls",
    "avg_agent_cost",
    "avg_effective_task_cost",
    "avg_expected_net_value",
)

# Agentic-work metrics supported by marginal-return analysis.
_WORK_METRIC_ACCESSORS = {
    "web_searches": lambda run: _as_float(run.web_searches),
    "model_calls": lambda run: _as_float(run.model_calls),
    "tool_calls": lambda run: _as_float(run.tool_calls),
    "subagent_calls": lambda run: _as_float(run.subagent_calls),
    "total_tokens": lambda run: _as_float(run.resolved_total_tokens()),
    "latency_seconds": lambda run: _as_float(run.latency_seconds),
}


def _as_float(value) -> float | None:
    return None if value is None else float(value)


def _resolve_architecture(
    runs: list[EconomicsRun], architecture: str | None
) -> str:
    if architecture is not None:
        return architecture
    labels = {run.architecture for run in runs}
    if len(labels) != 1:
        raise ValueError(
            "summarize_architecture requires a single architecture; found "
            f"{sorted(labels)!r}. Pass architecture=... or pre-filter the runs."
        )
    return next(iter(labels))


def summarize_architecture(
    runs: list[EconomicsRun],
    *,
    architecture: str | None = None,
    complexity: str | None = None,
) -> ArchitectureSummary:
    """Aggregate runs for one architecture (optionally one complexity).

    Averages are taken only over runs that reported a given metric, so an
    unavailable metric stays ``None`` instead of being dragged toward zero.
    ``complexity=None`` aggregates across complexities.
    """
    selected = [
        run
        for run in runs
        if (architecture is None or run.architecture == architecture)
        and (complexity is None or run.complexity == complexity)
    ]
    label = _resolve_architecture(selected, architecture) if selected else (
        architecture or "unknown"
    )

    # Outcome aggregates.
    success_flags = [run.task_success for run in selected if run.task_success is not None]
    num_success_known = len(success_flags)
    num_success = sum(1 for flag in success_flags if flag) if success_flags else None
    rate = metrics.success_rate(num_success, num_success_known)

    def avg(attr: str) -> float | None:
        return metrics.average(getattr(run, attr) for run in selected)

    avg_total = metrics.average(run.resolved_total_tokens() for run in selected)
    avg_human = metrics.average(metrics.run_human_cost(run) for run in selected)
    avg_effective = metrics.average(
        metrics.run_effective_task_cost(run) for run in selected
    )
    avg_net = metrics.average(
        metrics.run_expected_net_value(run) for run in selected
    )

    # Per-successful-task ratios use totals over available runs / known successes.
    total_agent_cost = _sum_optional(run.agent_cost for run in selected)
    total_tokens_sum = _sum_optional(
        run.resolved_total_tokens() for run in selected
    )
    total_searches = _sum_optional(run.web_searches for run in selected)
    total_effective = _sum_optional(
        metrics.run_effective_task_cost(run) for run in selected
    )

    return ArchitectureSummary(
        architecture=label,
        complexity=complexity,
        num_runs=len(selected),
        num_success_known=num_success_known,
        num_success=num_success,
        success_rate=rate,
        avg_quality=avg("quality_score"),
        avg_input_tokens=avg("input_tokens"),
        avg_output_tokens=avg("output_tokens"),
        avg_total_tokens=avg_total,
        avg_model_calls=avg("model_calls"),
        avg_web_searches=avg("web_searches"),
        avg_tool_calls=avg("tool_calls"),
        avg_subagent_calls=avg("subagent_calls"),
        avg_memory_reads=avg("memory_reads"),
        avg_skill_loads=avg("skill_loads"),
        avg_summarization_calls=avg("summarization_calls"),
        avg_latency_seconds=avg("latency_seconds"),
        avg_agent_cost=avg("agent_cost"),
        avg_human_cost=avg_human,
        avg_effective_task_cost=avg_effective,
        avg_expected_net_value=avg_net,
        cost_per_successful_task=metrics.cost_per_successful_task(
            total_agent_cost, num_success
        ),
        tokens_per_successful_task=metrics.per_successful_task(
            total_tokens_sum, num_success
        ),
        searches_per_successful_task=metrics.per_successful_task(
            total_searches, num_success
        ),
        effective_cost_per_successful_task=metrics.per_successful_task(
            total_effective, num_success
        ),
    )


def _sum_optional(values) -> float | None:
    """Sum non-``None`` values, or ``None`` when none are present."""
    present = [float(value) for value in values if value is not None]
    return sum(present) if present else None


def summarize_architectures(
    runs: list[EconomicsRun],
    *,
    by_complexity: bool = True,
) -> list[ArchitectureSummary]:
    """Group runs by architecture (and complexity) and summarize each group.

    Returns summaries ordered by architecture then complexity for stable output.
    With ``by_complexity=False`` complexities are pooled per architecture.
    """
    groups: dict[tuple[str, str | None], list[EconomicsRun]] = {}
    for run in runs:
        key = (run.architecture, run.complexity if by_complexity else None)
        groups.setdefault(key, []).append(run)

    summaries: list[ArchitectureSummary] = []
    for (architecture, complexity), group in sorted(
        groups.items(), key=lambda item: (item[0][0], item[0][1] or "")
    ):
        summaries.append(
            summarize_architecture(
                group, architecture=architecture, complexity=complexity
            )
        )
    return summaries


def compare_architectures(
    baseline: ArchitectureSummary,
    candidate: ArchitectureSummary,
) -> EconomicsComparison:
    """Produce explicit ``candidate - baseline`` deltas across key metrics.

    No metric is collapsed into a single score; unavailable sides stay ``None``.
    """
    deltas: dict[str, float | None] = {}
    for field_name in _COMPARISON_FIELDS:
        base_value = getattr(baseline, field_name)
        cand_value = getattr(candidate, field_name)
        key = field_name.removeprefix("avg_")
        if base_value is None or cand_value is None:
            deltas[key] = None
        else:
            deltas[key] = float(cand_value) - float(base_value)

    notes = _comparison_notes(baseline, candidate, deltas)
    complexity = baseline.complexity if baseline.complexity == candidate.complexity else None
    return EconomicsComparison(
        baseline=baseline,
        candidate=candidate,
        complexity=complexity,
        deltas=deltas,
        notes=notes,
    )


def _comparison_notes(
    baseline: ArchitectureSummary,
    candidate: ArchitectureSummary,
    deltas: dict[str, float | None],
) -> list[str]:
    notes: list[str] = []
    quality = deltas.get("quality")
    success = deltas.get("success_rate")
    tokens = deltas.get("total_tokens")

    if quality is not None:
        direction = "higher" if quality > 0 else "lower" if quality < 0 else "equal"
        notes.append(f"Quality {direction} by {quality:+.2f}.")
    else:
        notes.append("Quality delta unavailable.")

    if success is not None:
        notes.append(f"Success rate delta {success:+.1%}.")
    if tokens is not None:
        direction = "more" if tokens > 0 else "fewer"
        notes.append(f"{abs(tokens):.0f} {direction} average tokens.")

    effective = deltas.get("effective_task_cost")
    if effective is not None:
        direction = "higher" if effective > 0 else "lower"
        notes.append(f"Effective task cost {direction} by {effective:+.4f}.")

    notes.append(
        f"{candidate.architecture} vs {baseline.architecture}: metrics reported "
        "separately (no combined score)."
    )
    return notes


def analyze_marginal_returns(
    runs: list[EconomicsRun],
    *,
    work_metric: str = "web_searches",
    quality_metric: str = "quality_score",
    complexity: str | None = None,
    min_quality_gain: float = 0.05,
) -> MarginalReturnAnalysis:
    """Describe how mean quality changes as an agentic-work metric increases.

    Runs are bucketed by their ``work_metric`` value; mean quality per bucket is
    compared across increasing work. A bucket is flagged ``diminishing`` when the
    observed quality gain over the previous bucket falls below ``min_quality_gain``
    despite more work. Language stays deliberately tentative.
    """
    if work_metric not in _WORK_METRIC_ACCESSORS:
        raise ValueError(
            f"Unsupported work_metric {work_metric!r}; expected one of "
            f"{sorted(_WORK_METRIC_ACCESSORS)!r}."
        )
    accessor = _WORK_METRIC_ACCESSORS[work_metric]

    selected = [
        run
        for run in runs
        if complexity is None or run.complexity == complexity
    ]

    # Bucket (work_value -> list of quality scores), keeping only complete pairs.
    buckets: dict[float, list[float]] = {}
    for run in selected:
        work_value = accessor(run)
        quality_value = getattr(run, quality_metric, None)
        if work_value is None or quality_value is None:
            continue
        buckets.setdefault(float(work_value), []).append(float(quality_value))

    if len(buckets) < 2:
        return MarginalReturnAnalysis(
            work_metric=work_metric,
            quality_metric=quality_metric,
            complexity=complexity,
            available=False,
            points=[],
            observations=[
                "Insufficient evidence: fewer than two distinct "
                f"{work_metric} levels with quality data."
            ],
            candidate_elbow=None,
            reason="Need at least two work levels with paired quality scores.",
        )

    points: list[MarginalReturnPoint] = []
    previous_work: float | None = None
    previous_quality: float | None = None
    for work_value in sorted(buckets):
        qualities = buckets[work_value]
        mean_quality = sum(qualities) / len(qualities)
        work_delta = None if previous_work is None else work_value - previous_work
        quality_delta = (
            None if previous_quality is None else mean_quality - previous_quality
        )
        diminishing = (
            quality_delta is not None
            and work_delta is not None
            and work_delta > 0
            and quality_delta < min_quality_gain
        )
        points.append(
            MarginalReturnPoint(
                work_value=work_value,
                quality_value=mean_quality,
                num_runs=len(qualities),
                work_delta=work_delta,
                quality_delta=quality_delta,
                diminishing=diminishing,
            )
        )
        previous_work = work_value
        previous_quality = mean_quality

    elbow, observations = _describe_marginal(points, work_metric, min_quality_gain)
    return MarginalReturnAnalysis(
        work_metric=work_metric,
        quality_metric=quality_metric,
        complexity=complexity,
        available=True,
        points=points,
        observations=observations,
        candidate_elbow=elbow,
    )


def _describe_marginal(
    points: list[MarginalReturnPoint],
    work_metric: str,
    min_quality_gain: float,
) -> tuple[float | None, list[str]]:
    """Find a candidate elbow: the work level after which gains stay small."""
    elbow: float | None = None
    for index in range(1, len(points)):
        if all(
            point.quality_delta is not None and point.quality_delta < min_quality_gain
            for point in points[index:]
        ):
            elbow = points[index - 1].work_value
            break

    observations: list[str] = []
    if elbow is not None:
        observations.append(
            f"Additional {work_metric} beyond ~{elbow:g} show little observed "
            "quality gain (suggests diminishing returns; not statistically certain)."
        )
    else:
        observations.append(
            f"No clear diminishing-return point observed for {work_metric} "
            "across the available levels."
        )
    return elbow, observations
