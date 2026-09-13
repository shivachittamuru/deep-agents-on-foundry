"""Typed data models for the offline agent-economics framework (P8D).

P8C answers "did this change make the agent better?". P8D answers "was that
improvement worth the additional agentic work, cost, latency, and complexity?".

These records are deliberately explicit. Every operational or business metric is
optional and stays ``None`` when the caller did not supply it — missing evidence
is never silently coerced to zero, and token counts are never silently treated as
dollars. No serving/request-path logic lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any

# Conservative, human-readable routing states. There is no combined "economics
# score"; recommendations remain interpretable and evidence-based.
PREFER = "PREFER"
AVOID = "AVOID"
INVESTIGATE = "INVESTIGATE"


@dataclass
class EconomicsRun:
    """One agent run described in economic terms.

    Identity and grouping (``task_id``, ``architecture``, ``complexity``,
    ``run_id``) are required-ish; every metric below is optional. Unavailable
    metrics remain ``None`` and are excluded from analysis rather than assumed to
    be zero.
    """

    task_id: str
    architecture: str
    complexity: str = "simple"
    run_id: str | None = None

    # Token consumption. ``total_tokens`` may be derived from input+output.
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    model_calls: int | None = None

    # Agentic work (distinct from raw token consumption).
    web_searches: int | None = None
    tool_calls: int | None = None
    subagent_calls: int | None = None
    memory_reads: int | None = None
    skill_loads: int | None = None
    summarization_calls: int | None = None

    latency_seconds: float | None = None

    # Outcome.
    quality_score: float | None = None
    task_success: bool | None = None

    # Direct dollar cost of the agent run, when known/computed by the caller.
    agent_cost: float | None = None

    # Optional human-review economics (all three needed to derive a labor cost).
    human_review_minutes: float | None = None
    human_rework_minutes: float | None = None
    hourly_human_cost: float | None = None

    # Optional business-value economics.
    failure_cost: float | None = None
    business_value_if_success: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError("EconomicsRun.task_id must be a non-empty string.")
        if not isinstance(self.architecture, str) or not self.architecture.strip():
            raise ValueError("EconomicsRun.architecture must be a non-empty string.")
        if not isinstance(self.complexity, str) or not self.complexity.strip():
            raise ValueError("EconomicsRun.complexity must be a non-empty string.")

    def resolved_total_tokens(self) -> int | None:
        """Return total tokens, deriving from input+output when both exist.

        Returns ``None`` when neither an explicit total nor both components are
        available — a missing total is never reported as zero.
        """
        if self.total_tokens is not None:
            return int(self.total_tokens)
        if self.input_tokens is not None and self.output_tokens is not None:
            return int(self.input_tokens) + int(self.output_tokens)
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "architecture": self.architecture,
            "complexity": self.complexity,
            "run_id": self.run_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "resolved_total_tokens": self.resolved_total_tokens(),
            "model_calls": self.model_calls,
            "web_searches": self.web_searches,
            "tool_calls": self.tool_calls,
            "subagent_calls": self.subagent_calls,
            "memory_reads": self.memory_reads,
            "skill_loads": self.skill_loads,
            "summarization_calls": self.summarization_calls,
            "latency_seconds": self.latency_seconds,
            "quality_score": self.quality_score,
            "task_success": self.task_success,
            "agent_cost": self.agent_cost,
            "human_review_minutes": self.human_review_minutes,
            "human_rework_minutes": self.human_rework_minutes,
            "hourly_human_cost": self.hourly_human_cost,
            "failure_cost": self.failure_cost,
            "business_value_if_success": self.business_value_if_success,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EconomicsRun":
        """Build a run from a plain dict, ignoring derived/unknown keys."""
        known = {f.name for f in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in known})


@dataclass
class ArchitectureSummary:
    """Aggregated economics for one architecture at one complexity (or all).

    ``complexity`` is ``None`` when the summary aggregates across complexities.
    Every averaged field is ``None`` when no run supplied that metric; averages
    are computed only over runs that actually reported the value.
    """

    architecture: str
    complexity: str | None
    num_runs: int

    num_success_known: int
    num_success: int | None
    success_rate: float | None

    avg_quality: float | None

    avg_input_tokens: float | None
    avg_output_tokens: float | None
    avg_total_tokens: float | None
    avg_model_calls: float | None
    avg_web_searches: float | None
    avg_tool_calls: float | None
    avg_subagent_calls: float | None
    avg_memory_reads: float | None
    avg_skill_loads: float | None
    avg_summarization_calls: float | None
    avg_latency_seconds: float | None

    avg_agent_cost: float | None
    avg_human_cost: float | None
    avg_effective_task_cost: float | None
    avg_expected_net_value: float | None

    cost_per_successful_task: float | None
    tokens_per_successful_task: float | None
    searches_per_successful_task: float | None
    effective_cost_per_successful_task: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "architecture": self.architecture,
            "complexity": self.complexity,
            "num_runs": self.num_runs,
            "num_success_known": self.num_success_known,
            "num_success": self.num_success,
            "success_rate": self.success_rate,
            "avg_quality": self.avg_quality,
            "avg_input_tokens": self.avg_input_tokens,
            "avg_output_tokens": self.avg_output_tokens,
            "avg_total_tokens": self.avg_total_tokens,
            "avg_model_calls": self.avg_model_calls,
            "avg_web_searches": self.avg_web_searches,
            "avg_tool_calls": self.avg_tool_calls,
            "avg_subagent_calls": self.avg_subagent_calls,
            "avg_memory_reads": self.avg_memory_reads,
            "avg_skill_loads": self.avg_skill_loads,
            "avg_summarization_calls": self.avg_summarization_calls,
            "avg_latency_seconds": self.avg_latency_seconds,
            "avg_agent_cost": self.avg_agent_cost,
            "avg_human_cost": self.avg_human_cost,
            "avg_effective_task_cost": self.avg_effective_task_cost,
            "avg_expected_net_value": self.avg_expected_net_value,
            "cost_per_successful_task": self.cost_per_successful_task,
            "tokens_per_successful_task": self.tokens_per_successful_task,
            "searches_per_successful_task": self.searches_per_successful_task,
            "effective_cost_per_successful_task": self.effective_cost_per_successful_task,
        }


@dataclass
class EconomicsComparison:
    """Interpretable, per-metric deltas between two architecture summaries.

    ``deltas`` holds ``candidate - baseline`` for each comparable metric, with
    ``None`` where either side is unavailable. There is intentionally no single
    combined score.
    """

    baseline: ArchitectureSummary
    candidate: ArchitectureSummary
    complexity: str | None
    deltas: dict[str, float | None]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline": self.baseline.architecture,
            "candidate": self.candidate.architecture,
            "complexity": self.complexity,
            "deltas": self.deltas,
            "notes": self.notes,
        }


@dataclass
class FrontierEntry:
    """One architecture's position relative to the value frontier."""

    architecture: str
    complexity: str | None
    quality_value: float | None
    cost_value: float | None
    on_frontier: bool
    dominated_by: list[str] = field(default_factory=list)
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "architecture": self.architecture,
            "complexity": self.complexity,
            "quality_value": self.quality_value,
            "cost_value": self.cost_value,
            "on_frontier": self.on_frontier,
            "dominated_by": self.dominated_by,
            "reason": self.reason,
        }


@dataclass
class FrontierResult:
    """Pareto/value-frontier analysis for a set of architecture summaries.

    ``available`` is ``False`` (with a ``reason``) when the chosen cost or quality
    dimension cannot be computed for any architecture — the frontier is never
    fabricated from missing data.
    """

    complexity: str | None
    quality_dimension: str
    cost_dimension: str
    available: bool
    entries: list[FrontierEntry]
    frontier: list[str]
    dominated: list[str]
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "complexity": self.complexity,
            "quality_dimension": self.quality_dimension,
            "cost_dimension": self.cost_dimension,
            "available": self.available,
            "frontier": self.frontier,
            "dominated": self.dominated,
            "reason": self.reason,
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass
class MarginalReturnPoint:
    """Observed mean quality at one level of an agentic-work metric."""

    work_value: float
    quality_value: float
    num_runs: int
    work_delta: float | None
    quality_delta: float | None
    diminishing: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_value": self.work_value,
            "quality_value": self.quality_value,
            "num_runs": self.num_runs,
            "work_delta": self.work_delta,
            "quality_delta": self.quality_delta,
            "diminishing": self.diminishing,
        }


@dataclass
class MarginalReturnAnalysis:
    """Descriptive diminishing-returns analysis for one work/quality pairing.

    Deliberately makes no statistical-significance claim: it reports *observed*
    marginal deltas and a *candidate* elbow, or that evidence is insufficient.
    """

    work_metric: str
    quality_metric: str
    complexity: str | None
    available: bool
    points: list[MarginalReturnPoint]
    observations: list[str]
    candidate_elbow: float | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_metric": self.work_metric,
            "quality_metric": self.quality_metric,
            "complexity": self.complexity,
            "available": self.available,
            "candidate_elbow": self.candidate_elbow,
            "reason": self.reason,
            "observations": self.observations,
            "points": [point.to_dict() for point in self.points],
        }


@dataclass
class RoutingRecommendation:
    """Conservative, evidence-based routing observation for one complexity."""

    complexity: str
    state: str
    architecture: str | None
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "complexity": self.complexity,
            "state": self.state,
            "architecture": self.architecture,
            "rationale": self.rationale,
        }


@dataclass
class EconomicsReport:
    """Full offline economics analysis across architectures and complexities.

    Availability flags make explicit which classes of metric were present so the
    renderer can distinguish "unavailable" from a genuine zero.
    """

    total_runs: int
    architectures: list[str]
    complexities: list[str]
    cost_available: bool
    human_economics_available: bool
    business_value_available: bool
    summaries: list[ArchitectureSummary]
    frontier_by_complexity: dict[str, FrontierResult]
    marginal_returns: list[MarginalReturnAnalysis]
    routing: list[RoutingRecommendation]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_runs": self.total_runs,
            "architectures": self.architectures,
            "complexities": self.complexities,
            "cost_available": self.cost_available,
            "human_economics_available": self.human_economics_available,
            "business_value_available": self.business_value_available,
            "summaries": [summary.to_dict() for summary in self.summaries],
            "frontier_by_complexity": {
                key: result.to_dict()
                for key, result in self.frontier_by_complexity.items()
            },
            "marginal_returns": [
                analysis.to_dict() for analysis in self.marginal_returns
            ],
            "routing": [rec.to_dict() for rec in self.routing],
        }
