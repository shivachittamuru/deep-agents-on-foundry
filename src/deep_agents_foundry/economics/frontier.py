"""Value-frontier / Pareto analysis for architecture summaries (P8D).

Default framing: maximize a quality dimension while minimizing a cost dimension.
An architecture is *dominated* when another has quality that is at-least-as-good
and cost that is at-least-as-low, with at least one strict improvement.

There is no optimization solver here. When the chosen cost dimension is
unavailable the result says so explicitly rather than treating tokens or latency
as dollars — although the caller may *deliberately* choose tokens or latency as a
proxy cost dimension.
"""

from __future__ import annotations

from collections.abc import Callable

from .models import ArchitectureSummary, FrontierEntry, FrontierResult

# Quality dimensions: higher is better.
_QUALITY_DIMENSIONS: dict[str, Callable[[ArchitectureSummary], float | None]] = {
    "avg_quality": lambda summary: summary.avg_quality,
    "success_rate": lambda summary: summary.success_rate,
}

# Cost dimensions: lower is better. Tokens/latency are explicit opt-in proxies.
_COST_DIMENSIONS: dict[str, Callable[[ArchitectureSummary], float | None]] = {
    "avg_agent_cost": lambda summary: summary.avg_agent_cost,
    "avg_effective_task_cost": lambda summary: summary.avg_effective_task_cost,
    "cost_per_successful_task": lambda summary: summary.cost_per_successful_task,
    "effective_cost_per_successful_task": (
        lambda summary: summary.effective_cost_per_successful_task
    ),
    "avg_total_tokens": lambda summary: summary.avg_total_tokens,
    "avg_latency_seconds": lambda summary: summary.avg_latency_seconds,
}


def compute_value_frontier(
    summaries: list[ArchitectureSummary],
    *,
    quality_dimension: str = "avg_quality",
    cost_dimension: str = "avg_agent_cost",
) -> FrontierResult:
    """Compute the Pareto frontier over (quality, cost) for the given summaries.

    Only architectures that report *both* the chosen quality and cost values
    participate in domination. Architectures missing either value are returned as
    entries with ``on_frontier=False`` and a reason, and never fabricate the
    frontier. When no architecture has both values the result is marked
    unavailable.
    """
    quality_of = _QUALITY_DIMENSIONS.get(quality_dimension)
    cost_of = _COST_DIMENSIONS.get(cost_dimension)
    if quality_of is None:
        raise ValueError(
            f"Unsupported quality_dimension {quality_dimension!r}; expected one of "
            f"{sorted(_QUALITY_DIMENSIONS)!r}."
        )
    if cost_of is None:
        raise ValueError(
            f"Unsupported cost_dimension {cost_dimension!r}; expected one of "
            f"{sorted(_COST_DIMENSIONS)!r}."
        )

    complexity = _shared_complexity(summaries)

    comparable: list[tuple[ArchitectureSummary, float, float]] = []
    incomplete: list[FrontierEntry] = []
    for summary in summaries:
        quality = quality_of(summary)
        cost = cost_of(summary)
        if quality is None or cost is None:
            incomplete.append(
                FrontierEntry(
                    architecture=summary.architecture,
                    complexity=summary.complexity,
                    quality_value=quality,
                    cost_value=cost,
                    on_frontier=False,
                    reason=(
                        f"Missing {quality_dimension} and/or {cost_dimension}; "
                        "excluded from frontier."
                    ),
                )
            )
            continue
        comparable.append((summary, float(quality), float(cost)))

    if not comparable:
        return FrontierResult(
            complexity=complexity,
            quality_dimension=quality_dimension,
            cost_dimension=cost_dimension,
            available=False,
            entries=incomplete,
            frontier=[],
            dominated=[],
            reason=(
                f"No architecture reported both {quality_dimension} and "
                f"{cost_dimension}; frontier cannot be calculated."
            ),
        )

    entries: list[FrontierEntry] = []
    frontier: list[str] = []
    dominated: list[str] = []
    for summary, quality, cost in comparable:
        dominators = [
            other.architecture
            for other, other_quality, other_cost in comparable
            if other.architecture != summary.architecture
            and other_quality >= quality
            and other_cost <= cost
            and (other_quality > quality or other_cost < cost)
        ]
        on_frontier = not dominators
        entries.append(
            FrontierEntry(
                architecture=summary.architecture,
                complexity=summary.complexity,
                quality_value=quality,
                cost_value=cost,
                on_frontier=on_frontier,
                dominated_by=dominators,
            )
        )
        if on_frontier:
            frontier.append(summary.architecture)
        else:
            dominated.append(summary.architecture)

    entries.extend(incomplete)
    return FrontierResult(
        complexity=complexity,
        quality_dimension=quality_dimension,
        cost_dimension=cost_dimension,
        available=True,
        entries=entries,
        frontier=frontier,
        dominated=dominated,
        reason=None,
    )


def _shared_complexity(summaries: list[ArchitectureSummary]) -> str | None:
    complexities = {summary.complexity for summary in summaries}
    return next(iter(complexities)) if len(complexities) == 1 else None
