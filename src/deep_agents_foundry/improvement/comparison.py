"""Baseline-vs-candidate comparison and conservative recommendation (P8C).

Preserves per-case results and computes interpretable deltas instead of one
opaque score. The recommendation is deterministic: it prefers INVESTIGATE when
evidence is mixed or insufficient and only recommends KEEP/REVERT on a clear,
one-directional signal without offsetting regressions.
"""

from __future__ import annotations

from typing import Any

from .models import (
    INVESTIGATE,
    KEEP,
    REVERT,
    CaseComparison,
    ComparisonReport,
    RecommendationRules,
    RunRecord,
    VariantResult,
)
from .runner import evaluate_agent_variant

# Metrics compared as candidate - baseline. Lower is better for all of these.
_METRIC_KEYS = (
    "total_tokens",
    "input_tokens",
    "output_tokens",
    "model_calls",
    "web_searches",
    "tool_calls",
    "subagent_calls",
)


def _metric_delta(baseline: RunRecord, candidate: RunRecord, key: str) -> float | None:
    base = baseline.metrics.get(key)
    cand = candidate.metrics.get(key)
    if base is None or cand is None:
        return None
    return float(cand) - float(base)


def _compare_case(
    baseline: RunRecord, candidate: RunRecord, rules: RecommendationRules
) -> CaseComparison:
    deltas: dict[str, float | None] = {
        key: _metric_delta(baseline, candidate, key) for key in _METRIC_KEYS
    }
    deltas["latency_seconds"] = candidate.latency_seconds - baseline.latency_seconds

    quality_delta: float | None = None
    if baseline.quality is not None and candidate.quality is not None:
        quality_delta = candidate.quality - baseline.quality

    regressions: list[str] = []
    improvements: list[str] = []

    # Boolean check transitions (pass -> fail is a critical behavioral regression).
    critical = False
    for name, base_value in baseline.checks.items():
        cand_value = candidate.checks.get(name)
        if cand_value is None:
            continue
        if base_value and not cand_value:
            regressions.append(f"check '{name}' regressed (pass -> fail)")
            critical = True
        elif not base_value and cand_value:
            improvements.append(f"check '{name}' improved (fail -> pass)")

    # Rubric quality drop on this case.
    if quality_delta is not None:
        if quality_delta <= -rules.per_case_quality_regression:
            regressions.append(f"rubric quality dropped {quality_delta:+.2f}")
            critical = True
        elif quality_delta >= rules.per_case_quality_regression:
            improvements.append(f"rubric quality rose {quality_delta:+.2f}")

    # Soft efficiency regression: materially more searching without quality gain.
    search_delta = deltas.get("web_searches")
    if (
        search_delta is not None
        and search_delta >= rules.search_regression_delta
        and (quality_delta is None or quality_delta <= 0)
    ):
        regressions.append(
            f"web searches increased by {int(search_delta)} without quality gain"
        )

    # Simple task that starts delegating unnecessarily.
    base_sub = baseline.metrics.get("subagent_calls")
    cand_sub = candidate.metrics.get("subagent_calls")
    if (
        baseline.complexity == "simple"
        and base_sub == 0
        and cand_sub is not None
        and cand_sub > 0
        and not bool(baseline.expected.get("should_delegate", False))
    ):
        regressions.append("simple task began unnecessary delegation")
        critical = True

    return CaseComparison(
        case_id=candidate.case_id,
        complexity=candidate.complexity,
        baseline=baseline,
        candidate=candidate,
        deltas=deltas,
        quality_delta=quality_delta,
        regressions=regressions,
        improvements=improvements,
        critical_regression=critical,
    )


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _aggregate(cases: list[CaseComparison]) -> dict[str, Any]:
    """Average baseline/candidate metrics and deltas across cases where available."""
    aggregate: dict[str, Any] = {}

    for key in _METRIC_KEYS + ("latency_seconds",):
        base_values: list[float] = []
        cand_values: list[float] = []
        for case in cases:
            if key == "latency_seconds":
                base_values.append(case.baseline.latency_seconds)
                cand_values.append(case.candidate.latency_seconds)
                continue
            base = case.baseline.metrics.get(key)
            cand = case.candidate.metrics.get(key)
            if base is not None and cand is not None:
                base_values.append(float(base))
                cand_values.append(float(cand))

        base_avg = _mean(base_values)
        cand_avg = _mean(cand_values)
        delta = None if base_avg is None or cand_avg is None else cand_avg - base_avg
        pct = (
            (delta / base_avg * 100.0)
            if delta is not None and base_avg not in (None, 0)
            else None
        )
        aggregate[key] = {
            "baseline": base_avg,
            "candidate": cand_avg,
            "delta": delta,
            "pct": pct,
            "available": len(base_values),
        }

    return aggregate


def _aggregate_quality_delta(cases: list[CaseComparison]) -> float | None:
    deltas = [case.quality_delta for case in cases if case.quality_delta is not None]
    return _mean(deltas)


def _has_deterministic_signal(cases: list[CaseComparison]) -> bool:
    return any(case.regressions or case.improvements for case in cases)


def _classify_evidence(
    quality_delta: float | None,
    cases: list[CaseComparison],
    rules: RecommendationRules,
) -> str:
    """Return 'insufficient', 'mixed', or 'clear'."""
    has_signal = _has_deterministic_signal(cases)
    if quality_delta is None and not has_signal:
        return "insufficient"

    any_regression = any(case.regressions for case in cases)
    any_improvement = any(case.improvements for case in cases)

    quality_clear = quality_delta is not None and (
        quality_delta >= rules.quality_keep or quality_delta <= rules.quality_revert
    )

    if any_regression and any_improvement:
        return "mixed"
    if quality_delta is not None and not quality_clear and not has_signal:
        return "insufficient"
    if quality_clear or any_improvement or any_regression:
        return "clear"
    return "mixed"


def _recommend(
    quality_delta: float | None,
    cases: list[CaseComparison],
    rules: RecommendationRules,
) -> tuple[str, str]:
    """Deterministic, conservative KEEP / REVERT / INVESTIGATE decision."""
    critical_regressions = [case for case in cases if case.critical_regression]
    any_improvement = any(case.improvements for case in cases)
    has_signal = _has_deterministic_signal(cases)

    # 1. Insufficient evidence.
    if quality_delta is None and not has_signal:
        return (
            INVESTIGATE,
            "No rubric scores and no deterministic signal were available; "
            "insufficient evidence to decide.",
        )

    # 2. Clear regression -> REVERT.
    if critical_regressions and (
        quality_delta is None or quality_delta <= rules.quality_revert
    ):
        return (
            REVERT,
            f"{len(critical_regressions)} case(s) show critical regressions "
            "with no offsetting quality gain.",
        )
    if (
        quality_delta is not None
        and quality_delta <= rules.quality_revert
        and not any_improvement
    ):
        return (
            REVERT,
            f"Overall rubric quality fell {quality_delta:+.2f} with no improvements.",
        )

    # 3. Clear improvement -> KEEP.
    if not critical_regressions:
        if quality_delta is not None and quality_delta >= rules.quality_keep:
            return (
                KEEP,
                f"Overall rubric quality improved {quality_delta:+.2f} "
                "with no critical regressions.",
            )
        if quality_delta is None and any_improvement:
            return (
                KEEP,
                "Deterministic checks improved with no critical regressions "
                "(no judge model supplied).",
            )

    # 4. Everything else is mixed or inconclusive.
    return (
        INVESTIGATE,
        "Evidence is mixed or below thresholds; manual review recommended "
        "before keeping or reverting.",
    )


def _observations(
    quality_delta: float | None,
    aggregate: dict[str, Any],
    cases: list[CaseComparison],
) -> list[str]:
    observations: list[str] = []

    if quality_delta is not None:
        marker = "\u2713" if quality_delta > 0 else "\u26a0"
        observations.append(
            f"{marker} Overall rubric quality delta: {quality_delta:+.2f}"
        )
    else:
        observations.append("\u26a0 No rubric quality available (no judge model).")

    search = aggregate.get("web_searches", {})
    if search.get("delta") is not None and search["delta"] < 0:
        observations.append("\u2713 Average web searches decreased.")
    elif search.get("delta") is not None and search["delta"] > 0:
        observations.append("\u26a0 Average web searches increased.")

    tokens = aggregate.get("total_tokens", {})
    if tokens.get("pct") is not None and tokens["pct"] < 0:
        observations.append(f"\u2713 Average tokens changed {tokens['pct']:+.1f}%.")
    elif tokens.get("pct") is not None and tokens["pct"] > 0:
        observations.append(f"\u26a0 Average tokens changed {tokens['pct']:+.1f}%.")

    improved = [case.case_id for case in cases if case.improvements]
    regressed = [case.case_id for case in cases if case.regressions]
    if improved:
        observations.append(f"\u2713 Improved cases: {', '.join(improved)}.")
    if regressed:
        observations.append(f"\u26a0 Regressed cases: {', '.join(regressed)}.")

    simple_deltas = [
        case.quality_delta
        for case in cases
        if case.complexity == "simple" and case.quality_delta is not None
    ]
    if simple_deltas and all(abs(delta) < 0.05 for delta in simple_deltas):
        observations.append("\u26a0 No measurable benefit on simple tasks.")

    return observations


def build_comparison_report(
    baseline: VariantResult,
    candidate: VariantResult,
    *,
    rules: RecommendationRules | None = None,
) -> ComparisonReport:
    """Assemble a ``ComparisonReport`` from two already-run variants.

    Synchronous and pure so it can be exercised with deterministic fake results.
    Only cases present in both variants are compared.
    """
    rules = rules or RecommendationRules()

    baseline_by_case = baseline.by_case()
    candidate_by_case = candidate.by_case()
    shared_ids = [cid for cid in baseline_by_case if cid in candidate_by_case]

    cases = [
        _compare_case(baseline_by_case[cid], candidate_by_case[cid], rules)
        for cid in shared_ids
    ]

    aggregate = _aggregate(cases)
    quality_delta = _aggregate_quality_delta(cases)
    evidence = _classify_evidence(quality_delta, cases, rules)
    recommendation, reason = _recommend(quality_delta, cases, rules)
    observations = _observations(quality_delta, aggregate, cases)

    regressions = [
        f"{case.case_id}: {reason}"
        for case in cases
        for reason in case.regressions
    ]
    improvements = [
        f"{case.case_id}: {reason}"
        for case in cases
        for reason in case.improvements
    ]

    return ComparisonReport(
        baseline_label=baseline.label,
        candidate_label=candidate.label,
        case_comparisons=cases,
        aggregate=aggregate,
        quality_delta=quality_delta,
        regressions=regressions,
        improvements=improvements,
        observations=observations,
        evidence=evidence,
        recommendation=recommendation,
        recommendation_reason=reason,
        rules=rules,
    )


async def compare_agent_variants(
    baseline_agent,
    candidate_agent,
    *,
    dataset,
    judge_model=None,
    baseline_label: str = "baseline",
    candidate_label: str = "candidate",
    context: Any = None,
    rules: RecommendationRules | None = None,
) -> ComparisonReport:
    """Run two already-built agents over the same dataset and compare them.

    The framework never constructs the agents. Both variants use identical
    execution plumbing and, when supplied, the same judge model and rubric.
    """
    baseline = await evaluate_agent_variant(
        baseline_agent,
        dataset,
        variant_label=baseline_label,
        judge_model=judge_model,
        context=context,
    )
    candidate = await evaluate_agent_variant(
        candidate_agent,
        dataset,
        variant_label=candidate_label,
        judge_model=judge_model,
        context=context,
    )
    return build_comparison_report(baseline, candidate, rules=rules)
