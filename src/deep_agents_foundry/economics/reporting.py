"""Offline orchestration, routing observations, and rendering (P8D).

``analyze_agent_economics`` ties aggregation, the value frontier, and marginal
returns into one :class:`EconomicsReport`. ``render_economics_report`` turns that
into a human-readable report that carefully distinguishes *unavailable* from a
genuine zero and never fabricates a dollar value or a business-value number.
"""

from __future__ import annotations

from .comparison import analyze_marginal_returns, summarize_architectures
from .frontier import compute_value_frontier
from .models import (
    AVOID,
    INVESTIGATE,
    PREFER,
    ArchitectureSummary,
    EconomicsReport,
    FrontierResult,
    RoutingRecommendation,
)

# Preferred display order for the well-known complexity tiers.
_COMPLEXITY_ORDER = ("simple", "medium", "complex")

# Small tolerances for "comparable" quality when choosing among frontier options.
_QUALITY_EPSILON = 0.1  # for a 1-5 quality scale
_SUCCESS_EPSILON = 0.02  # for a 0-1 success-rate scale


def _ordered_complexities(values: set[str]) -> list[str]:
    known = [name for name in _COMPLEXITY_ORDER if name in values]
    extra = sorted(value for value in values if value not in _COMPLEXITY_ORDER)
    return known + extra


def _choose_quality_dimension(summaries: list[ArchitectureSummary]) -> str:
    if any(summary.avg_quality is not None for summary in summaries):
        return "avg_quality"
    return "success_rate"


def _choose_cost_dimension(
    summaries: list[ArchitectureSummary], cost_available: bool
) -> str:
    if cost_available:
        return "avg_agent_cost"
    if any(summary.avg_total_tokens is not None for summary in summaries):
        return "avg_total_tokens"
    return "avg_latency_seconds"


def analyze_agent_economics(
    runs,
    *,
    work_metric: str = "web_searches",
    quality_dimension: str | None = None,
    cost_dimension: str | None = None,
) -> EconomicsReport:
    """Run the full offline economics analysis over a collection of runs.

    Architectures are analyzed separately per complexity. The cost dimension
    defaults to direct agent cost when available, otherwise an explicit token
    proxy (never silently treated as dollars — the chosen dimension is recorded
    on every frontier result).
    """
    runs = list(runs)
    summaries = summarize_architectures(runs, by_complexity=True)

    architectures = sorted({run.architecture for run in runs})
    complexities = _ordered_complexities({run.complexity for run in runs})

    cost_available = any(run.agent_cost is not None for run in runs)
    human_available = any(
        run.hourly_human_cost is not None
        and (run.human_review_minutes is not None or run.human_rework_minutes is not None)
        for run in runs
    )
    business_available = any(
        run.business_value_if_success is not None or run.failure_cost is not None
        for run in runs
    )

    resolved_quality_dim = quality_dimension or _choose_quality_dimension(summaries)
    resolved_cost_dim = cost_dimension or _choose_cost_dimension(
        summaries, cost_available
    )

    frontier_by_complexity: dict[str, FrontierResult] = {}
    routing: list[RoutingRecommendation] = []
    marginal_returns = []

    for complexity in complexities:
        comp_summaries = [
            summary for summary in summaries if summary.complexity == complexity
        ]
        frontier = compute_value_frontier(
            comp_summaries,
            quality_dimension=resolved_quality_dim,
            cost_dimension=resolved_cost_dim,
        )
        frontier_by_complexity[complexity] = frontier
        routing.append(
            _route_complexity(
                complexity, comp_summaries, frontier, resolved_quality_dim
            )
        )

        analysis = analyze_marginal_returns(
            runs, work_metric=work_metric, complexity=complexity
        )
        if analysis.available:
            marginal_returns.append(analysis)

    return EconomicsReport(
        total_runs=len(runs),
        architectures=architectures,
        complexities=complexities,
        cost_available=cost_available,
        human_economics_available=human_available,
        business_value_available=business_available,
        summaries=summaries,
        frontier_by_complexity=frontier_by_complexity,
        marginal_returns=marginal_returns,
        routing=routing,
    )


def _route_complexity(
    complexity: str,
    summaries: list[ArchitectureSummary],
    frontier: FrontierResult,
    quality_dimension: str,
) -> RoutingRecommendation:
    """Conservative PREFER / INVESTIGATE observation for one complexity."""
    if not summaries:
        return RoutingRecommendation(
            complexity, INVESTIGATE, None, "No runs available for this complexity."
        )
    if not frontier.available:
        return RoutingRecommendation(
            complexity,
            INVESTIGATE,
            None,
            "Cost/proxy dimension unavailable; efficiency cannot be judged yet.",
        )
    if not frontier.frontier:
        return RoutingRecommendation(
            complexity, INVESTIGATE, None, "No architecture on the value frontier."
        )

    entry_map = {entry.architecture: entry for entry in frontier.entries}
    frontier_entries = [entry_map[name] for name in frontier.frontier]

    if len(frontier_entries) == 1:
        entry = frontier_entries[0]
        return RoutingRecommendation(
            complexity,
            PREFER,
            entry.architecture,
            f"{entry.architecture} is the sole non-dominated architecture on the "
            f"{frontier.quality_dimension}/{frontier.cost_dimension} frontier.",
        )

    epsilon = _SUCCESS_EPSILON if quality_dimension == "success_rate" else _QUALITY_EPSILON
    qualities = [entry.quality_value for entry in frontier_entries]
    quality_spread = max(qualities) - min(qualities)

    if quality_spread > epsilon:
        return RoutingRecommendation(
            complexity,
            INVESTIGATE,
            None,
            "Frontier shows a genuine quality/cost trade-off "
            f"(quality spread {quality_spread:.2f} on {frontier.quality_dimension}); "
            "investigate before committing.",
        )

    cheapest = min(frontier_entries, key=lambda entry: entry.cost_value)
    return RoutingRecommendation(
        complexity,
        PREFER,
        cheapest.architecture,
        f"{cheapest.architecture} offers comparable {frontier.quality_dimension} "
        f"across the frontier at the lowest {frontier.cost_dimension}.",
    )


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _fmt(value, *, digits: int = 2, pct: bool = False, unit: str = "") -> str:
    """Format a metric, showing ``unavailable`` for ``None`` (never zero)."""
    if value is None:
        return "unavailable"
    if pct:
        return f"{value * 100:.0f}%"
    formatted = f"{value:.{digits}f}"
    return f"{formatted}{unit}" if unit else formatted


def _summary_line(summary: ArchitectureSummary) -> list[str]:
    return [
        f"  {summary.architecture} (runs: {summary.num_runs})",
        f"    Quality:        {_fmt(summary.avg_quality)}",
        f"    Success:        {_fmt(summary.success_rate, pct=True)}",
        f"    Avg tokens:     {_fmt(summary.avg_total_tokens, digits=0)}",
        f"    Avg searches:   {_fmt(summary.avg_web_searches, digits=1)}",
        f"    Avg model calls:{_fmt(summary.avg_model_calls, digits=1)}",
        f"    Avg subagents:  {_fmt(summary.avg_subagent_calls, digits=1)}",
        f"    Avg latency:    {_fmt(summary.avg_latency_seconds, digits=1, unit='s')}",
        f"    Avg agent cost: {_fmt(summary.avg_agent_cost, digits=4)}",
        f"    Effective cost: {_fmt(summary.avg_effective_task_cost, digits=4)}",
        f"    Cost/success:   {_fmt(summary.cost_per_successful_task, digits=4)}",
    ]


def render_economics_report(report: EconomicsReport) -> str:
    """Render an :class:`EconomicsReport` as a concise plain-text report."""
    lines: list[str] = []
    lines.append("Agent Economics Report")
    lines.append("======================")
    lines.append("")

    # DATA COVERAGE
    lines.append("DATA COVERAGE")
    lines.append(f"- {report.total_runs} runs")
    lines.append(
        f"- {len(report.architectures)} architectures: "
        f"{', '.join(report.architectures) or 'none'}"
    )
    lines.append(
        f"- Complexities: {', '.join(report.complexities) or 'none'}"
    )
    lines.append(
        "- Direct dollar cost "
        + ("available" if report.cost_available else "unavailable")
    )
    lines.append(
        "- Human economics "
        + ("available" if report.human_economics_available else "unavailable")
    )
    lines.append(
        "- Business value "
        + ("available" if report.business_value_available else "unavailable")
    )
    lines.append("")

    # PER-COMPLEXITY
    routing_by_complexity = {rec.complexity: rec for rec in report.routing}
    for complexity in report.complexities:
        comp_summaries = [
            summary for summary in report.summaries if summary.complexity == complexity
        ]
        lines.append(f"{complexity.upper()} TASKS")
        rec = routing_by_complexity.get(complexity)
        if rec is not None:
            preferred = rec.architecture or f"{rec.state} (no single winner)"
            lines.append(f"Preferred architecture: {preferred}")
        for summary in comp_summaries:
            lines.extend(_summary_line(summary))
        if rec is not None:
            lines.append(f"Observation: {rec.rationale}")
        lines.append("")

    # VALUE FRONTIER
    lines.append("VALUE FRONTIER")
    for complexity in report.complexities:
        frontier = report.frontier_by_complexity.get(complexity)
        if frontier is None:
            continue
        if not frontier.available:
            lines.append(f"- {complexity}: unavailable ({frontier.reason})")
            continue
        dims = f"[{frontier.quality_dimension} vs {frontier.cost_dimension}]"
        lines.append(
            f"- {complexity} {dims}: {', '.join(frontier.frontier) or 'none'}"
        )
    lines.append("")

    # DOMINATED
    lines.append("DOMINATED")
    any_dominated = False
    for complexity in report.complexities:
        frontier = report.frontier_by_complexity.get(complexity)
        if frontier is None or not frontier.available or not frontier.dominated:
            continue
        any_dominated = True
        lines.append(
            f"- {complexity}: {AVOID} {', '.join(frontier.dominated)}"
        )
    if not any_dominated:
        lines.append("- None detected")
    lines.append("")

    # MARGINAL RETURNS
    lines.append("MARGINAL RETURNS")
    if report.marginal_returns:
        for analysis in report.marginal_returns:
            scope = analysis.complexity or "all"
            for observation in analysis.observations:
                lines.append(f"- [{scope}] {observation}")
    else:
        lines.append("- Insufficient evidence for marginal-return analysis")
    lines.append("")

    # HUMAN ECONOMICS
    lines.append("HUMAN ECONOMICS")
    if report.human_economics_available:
        for summary in report.summaries:
            if summary.avg_human_cost is not None:
                lines.append(
                    f"- {summary.architecture} [{summary.complexity}]: "
                    f"avg human cost {_fmt(summary.avg_human_cost, digits=4)}, "
                    f"effective cost {_fmt(summary.avg_effective_task_cost, digits=4)}"
                )
    else:
        lines.append("- unavailable")
    lines.append("")

    # BUSINESS VALUE
    lines.append("BUSINESS VALUE")
    if report.business_value_available:
        for summary in report.summaries:
            if summary.avg_expected_net_value is not None:
                lines.append(
                    f"- {summary.architecture} [{summary.complexity}]: "
                    f"expected net value {_fmt(summary.avg_expected_net_value, digits=4)}"
                )
    else:
        lines.append("- unavailable")
    lines.append("")

    # RECOMMENDED ROUTING
    lines.append("RECOMMENDED ROUTING")
    for rec in report.routing:
        target = rec.architecture if rec.architecture else rec.state
        lines.append(f"- {rec.complexity:<8} -> {rec.state}: {target}")
    return "\n".join(lines)
