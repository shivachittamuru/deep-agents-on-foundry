"""Offline agent-economics framework (P8D).

Where P8C answers "did this change make the agent better?", P8D answers "was that
improvement worth the additional agentic work, cost, latency, and complexity?".

It is a control-plane/analysis capability. It runs only when an engineer invokes
it, never inside the Hosted Agent request path, and it consumes P8C outputs rather
than redesigning them. The framework stays interpretable on purpose: there is no
single combined "economics score", missing metrics remain unavailable instead of
zero, and token counts are never silently treated as dollars.

Example — analyze a collection of economics runs and print a report::

    from deep_agents_foundry.economics import (
        analyze_agent_economics,
        render_economics_report,
    )

    report = analyze_agent_economics(runs)
    print(render_economics_report(report))

Example — reuse P8C comparison output::

    from deep_agents_foundry.economics import (
        economics_runs_from_comparison_report,
        analyze_agent_economics,
    )

    runs = economics_runs_from_comparison_report(p8c_report)
    report = analyze_agent_economics(runs)
"""

from __future__ import annotations

from .adapters import (
    economics_run_from_run_record,
    economics_runs_from_comparison_report,
    economics_runs_from_variant_result,
)
from .comparison import (
    analyze_marginal_returns,
    compare_architectures,
    summarize_architecture,
    summarize_architectures,
)
from .datasets import (
    build_sample_economics_runs,
    load_economics_runs,
    load_or_build_runs,
)
from .economics_log import (
    EconomicsRecord,
    list_economics_records,
    load_economics_record,
    save_economics_analysis,
    save_economics_record,
)
from .frontier import compute_value_frontier
from .metrics import (
    cost_per_successful_task,
    effective_task_cost,
    expected_business_value,
    expected_failure_cost,
    expected_net_value,
    labor_cost,
    per_successful_task,
    success_rate,
    total_tokens,
)
from .models import (
    AVOID,
    INVESTIGATE,
    PREFER,
    ArchitectureSummary,
    EconomicsComparison,
    EconomicsReport,
    EconomicsRun,
    FrontierEntry,
    FrontierResult,
    MarginalReturnAnalysis,
    MarginalReturnPoint,
    RoutingRecommendation,
)
from .reporting import analyze_agent_economics, render_economics_report

__all__ = [
    # Models and constants
    "EconomicsRun",
    "ArchitectureSummary",
    "EconomicsComparison",
    "FrontierEntry",
    "FrontierResult",
    "MarginalReturnPoint",
    "MarginalReturnAnalysis",
    "RoutingRecommendation",
    "EconomicsReport",
    "PREFER",
    "AVOID",
    "INVESTIGATE",
    # Metrics
    "total_tokens",
    "labor_cost",
    "expected_failure_cost",
    "effective_task_cost",
    "success_rate",
    "cost_per_successful_task",
    "per_successful_task",
    "expected_business_value",
    "expected_net_value",
    # Aggregation and comparison
    "summarize_architecture",
    "summarize_architectures",
    "compare_architectures",
    "analyze_marginal_returns",
    # Frontier
    "compute_value_frontier",
    # Orchestration and reporting
    "analyze_agent_economics",
    "render_economics_report",
    # P8C adapters
    "economics_run_from_run_record",
    "economics_runs_from_variant_result",
    "economics_runs_from_comparison_report",
    # Sample data
    "build_sample_economics_runs",
    "load_economics_runs",
    "load_or_build_runs",
    # Persistence
    "EconomicsRecord",
    "save_economics_record",
    "load_economics_record",
    "list_economics_records",
    "save_economics_analysis",
]
