"""Reusable failure taxonomy and improvement-hypothesis model (P8C).

Deliberately flat: a tuple of category labels plus one dataclass. No class
hierarchies. Economics is only a label here ("too much work for too little
quality improvement"); actual economic analysis belongs to P8D.
"""

from __future__ import annotations

from dataclasses import dataclass

FAILURE_CATEGORIES: tuple[str, ...] = (
    "retrieval",
    "reasoning",
    "tool_use",
    "context",
    "memory",
    "skill",
    "subagent",
    "synthesis",
    "economics",
)


@dataclass(frozen=True)
class ImprovementHypothesis:
    """Experiment bookkeeping: what we saw, why, and what we changed.

    `primary_metric` is the metric expected to improve; `guardrail_metric` is the
    metric that must not regress.
    """

    symptom: str
    failure_category: str
    hypothesis: str
    proposed_change: str
    primary_metric: str
    guardrail_metric: str

    def __post_init__(self) -> None:
        if self.failure_category not in FAILURE_CATEGORIES:
            raise ValueError(
                "failure_category must be one of "
                f"{FAILURE_CATEGORIES!r}, got {self.failure_category!r}."
            )
