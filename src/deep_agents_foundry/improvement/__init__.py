"""Offline agent-improvement framework (P8C).

An engineering/evaluation control-plane capability for answering: "I changed my
agent. Did it actually get better, how did its behavior change, and should I keep
the change?" It runs only when an engineer explicitly invokes it and is never
imported by the serving/request path (``hosting.py``).

It reuses the production evaluation primitives in ``deep_agents_foundry.evaluation``
rather than reimplementing them, and never constructs the production agent — the
caller passes already-built agents.

Example — compare, report, then explicitly persist a compact summary::

    report = await compare_agent_variants(
        baseline_agent, candidate_agent, dataset=core_research_dataset()
    )

    print(render_improvement_report(report))

    path = save_improvement_experiment(
        report,
        change_id="technology-skill-v2",
        hypothesis="Reduce redundant searches without lowering quality",
        change_description="Tightened technology-research skill search guidance",
    )

    print(f"Saved experiment: {path}")

Saving is always explicit; comparisons never write files on their own.
"""

from __future__ import annotations

from .comparison import build_comparison_report, compare_agent_variants
from .datasets import (
    core_research_dataset,
    dev_cases,
    held_out_cases,
)
from .diagnosis import FAILURE_CATEGORIES, ImprovementHypothesis
from .experiment_log import (
    ExperimentRecord,
    list_experiment_records,
    load_experiment_record,
    save_experiment_record,
    save_improvement_experiment,
)
from .models import (
    INVESTIGATE,
    KEEP,
    REVERT,
    CaseComparison,
    ComparisonReport,
    EvaluationCase,
    RecommendationRules,
    RunRecord,
    VariantResult,
)
from .reporting import render_improvement_report
from .runner import evaluate_agent_variant

__all__ = [
    "EvaluationCase",
    "ImprovementHypothesis",
    "FAILURE_CATEGORIES",
    "ExperimentRecord",
    "save_experiment_record",
    "load_experiment_record",
    "list_experiment_records",
    "save_improvement_experiment",
    "RecommendationRules",
    "RunRecord",
    "VariantResult",
    "CaseComparison",
    "ComparisonReport",
    "KEEP",
    "REVERT",
    "INVESTIGATE",
    "core_research_dataset",
    "dev_cases",
    "held_out_cases",
    "evaluate_agent_variant",
    "compare_agent_variants",
    "build_comparison_report",
    "render_improvement_report",
]
