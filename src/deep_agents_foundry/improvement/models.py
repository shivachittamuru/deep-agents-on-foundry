"""Typed data models for the offline improvement framework (P8C).

These are lightweight records for experiment bookkeeping and reporting. They hold
raw per-run data so individual failures can be diagnosed, not only aggregates.
No serving/request-path logic lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Recommendation labels. The decision is deterministic and conservative.
KEEP = "KEEP"
REVERT = "REVERT"
INVESTIGATE = "INVESTIGATE"


@dataclass(frozen=True)
class EvaluationCase:
    """A single reusable evaluation case.

    `expected` carries behavior metadata the checks interpret (e.g. `needs_web`,
    `max_searches`, `should_delegate`, `expects_file`, `expected_skill`,
    `expected_subagent`). Evaluation logic lives in the runner/comparison layers,
    not in this model.
    """

    id: str
    prompt: str
    complexity: str = "simple"
    expected: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    protects_against: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("EvaluationCase.id must be a non-empty string.")
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ValueError("EvaluationCase.prompt must be a non-empty string.")


@dataclass
class RunRecord:
    """Everything captured for one agent run over one case.

    Optional metrics that the runtime did not expose are held as `None`, never
    silently coerced to zero. `raw_result` is retained for diagnosis.
    """

    case_id: str
    complexity: str
    prompt: str
    expected: dict[str, Any]
    variant_label: str
    thread_id: str
    latency_seconds: float
    final_text: str
    metrics: dict[str, Any]
    trajectory_features: dict[str, Any]
    trajectory_summary: dict[str, Any]
    deterministic: dict[str, Any]
    checks: dict[str, bool]
    raw_result: Any = None
    rubric: dict[str, Any] | None = None
    quality: float | None = None
    errors: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize without the (possibly unpicklable) raw result."""
        return {
            "case_id": self.case_id,
            "complexity": self.complexity,
            "prompt": self.prompt,
            "expected": self.expected,
            "variant_label": self.variant_label,
            "thread_id": self.thread_id,
            "latency_seconds": self.latency_seconds,
            "final_text": self.final_text,
            "metrics": self.metrics,
            "trajectory_features": self.trajectory_features,
            "trajectory_summary": self.trajectory_summary,
            "deterministic": self.deterministic,
            "checks": self.checks,
            "rubric": self.rubric,
            "quality": self.quality,
            "errors": self.errors,
        }


@dataclass
class VariantResult:
    """All run records for one agent variant over a dataset."""

    label: str
    records: list[RunRecord]

    def by_case(self) -> dict[str, RunRecord]:
        return {record.case_id: record for record in self.records}


@dataclass
class CaseComparison:
    """Baseline vs candidate for a single case, with interpretable deltas."""

    case_id: str
    complexity: str
    baseline: RunRecord
    candidate: RunRecord
    deltas: dict[str, float | None]
    quality_delta: float | None
    regressions: list[str]
    improvements: list[str]
    critical_regression: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "complexity": self.complexity,
            "deltas": self.deltas,
            "quality_delta": self.quality_delta,
            "regressions": self.regressions,
            "improvements": self.improvements,
            "critical_regression": self.critical_regression,
            "baseline": self.baseline.to_dict(),
            "candidate": self.candidate.to_dict(),
        }


@dataclass(frozen=True)
class RecommendationRules:
    """Explicit, configurable thresholds for regression/recommendation logic.

    Kept simple on purpose: P8C measures and explains changes; it does not build a
    statistical-significance framework.
    """

    quality_keep: float = 0.10
    quality_revert: float = -0.10
    per_case_quality_regression: float = 0.25
    search_regression_delta: int = 2


@dataclass
class ComparisonReport:
    """Structured baseline-vs-candidate result plus a conservative recommendation."""

    baseline_label: str
    candidate_label: str
    case_comparisons: list[CaseComparison]
    aggregate: dict[str, Any]
    quality_delta: float | None
    regressions: list[str]
    improvements: list[str]
    observations: list[str]
    evidence: str
    recommendation: str
    recommendation_reason: str
    rules: RecommendationRules

    @property
    def has_regression(self) -> bool:
        return any(case.regressions for case in self.case_comparisons)

    @property
    def has_improvement(self) -> bool:
        return any(case.improvements for case in self.case_comparisons)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_label": self.baseline_label,
            "candidate_label": self.candidate_label,
            "aggregate": self.aggregate,
            "quality_delta": self.quality_delta,
            "regressions": self.regressions,
            "improvements": self.improvements,
            "observations": self.observations,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "recommendation_reason": self.recommendation_reason,
            "cases": [case.to_dict() for case in self.case_comparisons],
        }
