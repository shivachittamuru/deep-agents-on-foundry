"""Human-readable rendering of a ``ComparisonReport`` (P8C).

Readable observations matter as much as the numbers. The renderer never invents
data: unavailable metrics are shown as "n/a" so missing evidence stays visible.
"""

from __future__ import annotations

from .models import ComparisonReport


def _fmt(value, *, pct: bool = False, signed: bool = False) -> str:
    if value is None:
        return "n/a"
    if pct:
        return f"{value:+.1f}%"
    if signed:
        return f"{value:+.2f}"
    return f"{value:.2f}"


def _metric_line(label: str, entry: dict) -> str:
    baseline = _fmt(entry.get("baseline"))
    candidate = _fmt(entry.get("candidate"))
    delta = _fmt(entry.get("delta"), signed=True)
    pct = entry.get("pct")
    pct_text = f" ({_fmt(pct, pct=True)})" if pct is not None else ""
    return f"- {label}: {baseline} -> {candidate} (delta {delta}{pct_text})"


def render_improvement_report(report: ComparisonReport) -> str:
    """Render a ``ComparisonReport`` as a concise plain-text report."""
    lines: list[str] = []
    lines.append("Research Agent Improvement Report")
    lines.append("=================================")
    lines.append("")
    lines.append(f"{report.candidate_label} vs {report.baseline_label}")
    lines.append(f"Cases compared: {len(report.case_comparisons)}")
    lines.append("")

    # QUALITY
    lines.append("QUALITY")
    if report.quality_delta is not None:
        lines.append(f"- Overall rubric quality delta: {report.quality_delta:+.2f}")
    else:
        lines.append("- Overall rubric quality: n/a (no judge model)")
    improved = sum(1 for case in report.case_comparisons if case.improvements)
    regressed = sum(1 for case in report.case_comparisons if case.regressions)
    lines.append(
        f"- Cases improved: {improved}, regressed: {regressed}, "
        f"total: {len(report.case_comparisons)}"
    )
    lines.append("")

    # TRAJECTORY
    lines.append("TRAJECTORY")
    aggregate = report.aggregate
    lines.append(_metric_line("Avg web searches", aggregate.get("web_searches", {})))
    lines.append(_metric_line("Avg model calls", aggregate.get("model_calls", {})))
    lines.append(_metric_line("Avg tool calls", aggregate.get("tool_calls", {})))
    lines.append(_metric_line("Avg subagent calls", aggregate.get("subagent_calls", {})))
    lines.append("")

    # PERFORMANCE
    lines.append("PERFORMANCE")
    lines.append(_metric_line("Avg total tokens", aggregate.get("total_tokens", {})))
    lines.append(_metric_line("Avg latency (s)", aggregate.get("latency_seconds", {})))
    lines.append("")

    # REGRESSIONS
    lines.append("REGRESSIONS")
    if report.regressions:
        for item in report.regressions:
            lines.append(f"- {item}")
    else:
        lines.append("- None detected")
    lines.append("")

    # OBSERVATIONS
    lines.append("OBSERVATIONS")
    for observation in report.observations:
        lines.append(observation)
    lines.append("")

    # RECOMMENDATION
    lines.append("RECOMMENDATION")
    lines.append(report.recommendation)
    lines.append("")
    lines.append(f"Evidence: {report.evidence}")
    lines.append("Reason:")
    lines.append(report.recommendation_reason)

    return "\n".join(lines)
