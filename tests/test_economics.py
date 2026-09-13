"""Tests for the offline agent-economics framework (P8D).

Deterministic and synthetic only: no Azure/Foundry, no network, no live LLM. All
numeric conclusions are controlled by fabricated ``EconomicsRun`` records so the
economics logic is fully exercised in isolation.
"""

from __future__ import annotations

import json

import pytest

from deep_agents_foundry.economics import (
    AVOID,
    INVESTIGATE,
    PREFER,
    ArchitectureSummary,
    EconomicsReport,
    EconomicsRun,
    analyze_agent_economics,
    analyze_marginal_returns,
    build_sample_economics_runs,
    compare_architectures,
    compute_value_frontier,
    cost_per_successful_task,
    economics_run_from_run_record,
    economics_runs_from_comparison_report,
    economics_runs_from_variant_result,
    effective_task_cost,
    expected_business_value,
    expected_failure_cost,
    expected_net_value,
    load_or_build_runs,
    render_economics_report,
    success_rate,
    summarize_architecture,
    summarize_architectures,
    total_tokens,
)
from deep_agents_foundry.economics import metrics as metrics_module
from deep_agents_foundry.improvement import RunRecord, VariantResult, build_comparison_report


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def make_run(
    architecture,
    *,
    task_id="task",
    complexity="simple",
    run_id=None,
    input_tokens=None,
    output_tokens=None,
    total_tokens=None,
    model_calls=None,
    web_searches=None,
    tool_calls=None,
    subagent_calls=None,
    latency_seconds=None,
    quality_score=None,
    task_success=None,
    agent_cost=None,
    human_review_minutes=None,
    human_rework_minutes=None,
    hourly_human_cost=None,
    failure_cost=None,
    business_value_if_success=None,
):
    return EconomicsRun(
        task_id=task_id,
        architecture=architecture,
        complexity=complexity,
        run_id=run_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        model_calls=model_calls,
        web_searches=web_searches,
        tool_calls=tool_calls,
        subagent_calls=subagent_calls,
        latency_seconds=latency_seconds,
        quality_score=quality_score,
        task_success=task_success,
        agent_cost=agent_cost,
        human_review_minutes=human_review_minutes,
        human_rework_minutes=human_rework_minutes,
        hourly_human_cost=hourly_human_cost,
        failure_cost=failure_cost,
        business_value_if_success=business_value_if_success,
    )


def make_run_record(
    case_id,
    *,
    complexity="medium",
    quality=None,
    metrics=None,
    latency=1.0,
    checks=None,
):
    return RunRecord(
        case_id=case_id,
        complexity=complexity,
        prompt=f"prompt {case_id}",
        expected={},
        variant_label="v",
        thread_id=f"t-{case_id}",
        latency_seconds=latency,
        final_text="answer",
        metrics=metrics or {},
        trajectory_features={},
        trajectory_summary={},
        deterministic={},
        checks=checks or {},
        rubric=None if quality is None else {"weighted_overall_score": quality},
        quality=quality,
    )


# --------------------------------------------------------------------------- #
# A. Models
# --------------------------------------------------------------------------- #
def test_run_requires_identity_fields():
    with pytest.raises(ValueError):
        EconomicsRun(task_id="", architecture="deep")
    with pytest.raises(ValueError):
        EconomicsRun(task_id="t", architecture="  ")


def test_optional_metrics_default_to_none():
    run = make_run("baseline")
    assert run.input_tokens is None
    assert run.quality_score is None
    assert run.task_success is None
    assert run.agent_cost is None
    assert run.resolved_total_tokens() is None


def test_resolved_total_tokens_prefers_explicit_then_derives():
    assert make_run("a", total_tokens=500).resolved_total_tokens() == 500
    assert make_run("a", input_tokens=300, output_tokens=200).resolved_total_tokens() == 500
    # Only one component present -> still unavailable, never zero.
    assert make_run("a", input_tokens=300).resolved_total_tokens() is None


# --------------------------------------------------------------------------- #
# B. Metrics
# --------------------------------------------------------------------------- #
def test_total_tokens_formula():
    assert total_tokens(300, 200) == 500
    assert total_tokens(None, 200) is None
    assert total_tokens(1, 1, total=999) == 999


def test_human_review_and_rework_cost():
    # 15 minutes at $120/hr = $30.
    assert metrics_module.labor_cost(15, 120) == pytest.approx(30.0)
    assert metrics_module.labor_cost(None, 120) is None
    assert metrics_module.labor_cost(15, None) is None


def test_expected_failure_cost_formula():
    assert expected_failure_cost(0.25, 100) == pytest.approx(25.0)
    assert expected_failure_cost(None, 100) is None
    assert expected_failure_cost(0.25, None) is None


def test_effective_task_cost_sums_available_components():
    assert effective_task_cost(0.05) == pytest.approx(0.05)
    assert effective_task_cost(0.05, 0.10, 0.20, 0.30) == pytest.approx(0.65)
    # Missing agent cost -> unavailable (cannot anchor).
    assert effective_task_cost(None, 0.1) is None


def test_expected_business_value_and_net_value():
    assert expected_business_value(0.9, 1000) == pytest.approx(900.0)
    assert expected_business_value(None, 1000) is None
    net = expected_net_value(900.0, failure_cost_component=10.0, agent_cost=1.0, human_cost=5.0)
    assert net == pytest.approx(884.0)
    assert expected_net_value(None, agent_cost=1.0) is None


def test_cost_per_successful_task_and_zero_success():
    assert cost_per_successful_task(10.0, 4) == pytest.approx(2.5)
    assert cost_per_successful_task(10.0, 0) is None
    assert cost_per_successful_task(None, 4) is None


def test_success_rate_handles_zero_total():
    assert success_rate(3, 4) == pytest.approx(0.75)
    assert success_rate(0, 0) is None
    assert success_rate(None, 4) is None


# --------------------------------------------------------------------------- #
# C. Aggregation
# --------------------------------------------------------------------------- #
def test_architecture_and_complexity_grouping():
    runs = [
        make_run("baseline", complexity="simple", quality_score=4.0),
        make_run("baseline", complexity="complex", quality_score=3.0),
        make_run("deep", complexity="simple", quality_score=4.5),
    ]
    summaries = summarize_architectures(runs, by_complexity=True)
    keys = {(summary.architecture, summary.complexity) for summary in summaries}
    assert keys == {("baseline", "simple"), ("baseline", "complex"), ("deep", "simple")}


def test_repeated_runs_average_correctly():
    runs = [
        make_run("deep", quality_score=4.0, total_tokens=1000, web_searches=2),
        make_run("deep", quality_score=5.0, total_tokens=3000, web_searches=4),
    ]
    summary = summarize_architecture(runs, architecture="deep", complexity="simple")
    assert summary.num_runs == 2
    assert summary.avg_quality == pytest.approx(4.5)
    assert summary.avg_total_tokens == pytest.approx(2000)
    assert summary.avg_web_searches == pytest.approx(3.0)


def test_missing_values_not_treated_as_zero_in_average():
    runs = [
        make_run("deep", quality_score=4.0),
        make_run("deep", quality_score=None),  # missing quality
    ]
    summary = summarize_architecture(runs, architecture="deep")
    # Average over the single available value, not (4.0 + 0) / 2.
    assert summary.avg_quality == pytest.approx(4.0)


def test_success_rate_only_over_known_outcomes():
    runs = [
        make_run("deep", task_success=True),
        make_run("deep", task_success=False),
        make_run("deep", task_success=None),  # unknown, excluded
    ]
    summary = summarize_architecture(runs, architecture="deep")
    assert summary.num_success_known == 2
    assert summary.num_success == 1
    assert summary.success_rate == pytest.approx(0.5)


def test_cost_per_successful_task_aggregate():
    runs = [
        make_run("deep", agent_cost=1.0, task_success=True),
        make_run("deep", agent_cost=3.0, task_success=True),
        make_run("deep", agent_cost=2.0, task_success=False),
    ]
    summary = summarize_architecture(runs, architecture="deep")
    # Total agent cost 6.0 over 2 successes.
    assert summary.cost_per_successful_task == pytest.approx(3.0)


def test_summarize_mixed_architectures_requires_label():
    runs = [make_run("a"), make_run("b")]
    with pytest.raises(ValueError):
        summarize_architecture(runs)


# --------------------------------------------------------------------------- #
# D. Comparison
# --------------------------------------------------------------------------- #
def test_comparison_produces_interpretable_deltas_no_score():
    baseline = summarize_architecture(
        [make_run("baseline", quality_score=4.0, total_tokens=1000, web_searches=1)],
        architecture="baseline",
    )
    candidate = summarize_architecture(
        [make_run("deep", quality_score=4.5, total_tokens=3000, web_searches=3)],
        architecture="deep",
    )
    comparison = compare_architectures(baseline, candidate)
    assert comparison.deltas["quality"] == pytest.approx(0.5)
    assert comparison.deltas["total_tokens"] == pytest.approx(2000)
    assert comparison.deltas["web_searches"] == pytest.approx(2)
    # No combined score field exists.
    assert not hasattr(comparison, "score")
    assert "score" not in comparison.deltas


def test_comparison_delta_unavailable_when_metric_missing():
    baseline = summarize_architecture([make_run("baseline")], architecture="baseline")
    candidate = summarize_architecture([make_run("deep")], architecture="deep")
    comparison = compare_architectures(baseline, candidate)
    assert comparison.deltas["quality"] is None
    assert comparison.deltas["agent_cost"] is None


# --------------------------------------------------------------------------- #
# E. Frontier
# --------------------------------------------------------------------------- #
def test_dominated_architecture_detected():
    summaries = [
        summarize_architecture(
            [make_run("a", quality_score=4.5, agent_cost=0.05)], architecture="a"
        ),
        summarize_architecture(
            [make_run("b", quality_score=4.0, agent_cost=0.40)], architecture="b"
        ),
    ]
    result = compute_value_frontier(
        summaries, quality_dimension="avg_quality", cost_dimension="avg_agent_cost"
    )
    assert result.available is True
    assert result.frontier == ["a"]
    assert result.dominated == ["b"]


def test_multiple_frontier_architectures_supported():
    summaries = [
        summarize_architecture(
            [make_run("cheap", quality_score=4.0, agent_cost=0.05)], architecture="cheap"
        ),
        summarize_architecture(
            [make_run("rich", quality_score=4.8, agent_cost=0.40)], architecture="rich"
        ),
    ]
    result = compute_value_frontier(summaries)
    # A genuine trade-off: neither dominates the other.
    assert set(result.frontier) == {"cheap", "rich"}
    assert result.dominated == []


def test_frontier_unavailable_when_cost_missing():
    summaries = [
        summarize_architecture([make_run("a", quality_score=4.0)], architecture="a"),
        summarize_architecture([make_run("b", quality_score=4.5)], architecture="b"),
    ]
    result = compute_value_frontier(
        summaries, quality_dimension="avg_quality", cost_dimension="avg_agent_cost"
    )
    assert result.available is False
    assert result.frontier == []
    assert "cannot be calculated" in (result.reason or "")


def test_frontier_supports_token_proxy_dimension():
    summaries = [
        summarize_architecture(
            [make_run("a", quality_score=4.5, total_tokens=1000)], architecture="a"
        ),
        summarize_architecture(
            [make_run("b", quality_score=4.0, total_tokens=3000)], architecture="b"
        ),
    ]
    result = compute_value_frontier(
        summaries, quality_dimension="avg_quality", cost_dimension="avg_total_tokens"
    )
    assert result.available is True
    assert result.cost_dimension == "avg_total_tokens"
    assert result.frontier == ["a"]


# --------------------------------------------------------------------------- #
# F. Marginal returns
# --------------------------------------------------------------------------- #
def test_marginal_returns_detects_diminishing_pattern():
    runs = [
        make_run("deep", web_searches=1, quality_score=4.0),
        make_run("deep", web_searches=2, quality_score=4.6),
        make_run("deep", web_searches=3, quality_score=4.8),
        make_run("deep", web_searches=4, quality_score=4.81),
    ]
    analysis = analyze_marginal_returns(runs, work_metric="web_searches")
    assert analysis.available is True
    assert analysis.candidate_elbow == pytest.approx(3.0)
    assert any("diminishing" in obs or "little observed" in obs for obs in analysis.observations)


def test_marginal_returns_insufficient_evidence():
    runs = [make_run("deep", web_searches=2, quality_score=4.0)]
    analysis = analyze_marginal_returns(runs, work_metric="web_searches")
    assert analysis.available is False
    assert "Insufficient evidence" in analysis.observations[0]


# --------------------------------------------------------------------------- #
# G. Complexity analysis
# --------------------------------------------------------------------------- #
def test_complexity_tiers_remain_separate():
    runs = [
        make_run("deep", complexity="simple", quality_score=4.0, agent_cost=0.05),
        make_run("deep", complexity="complex", quality_score=3.0, agent_cost=0.50),
    ]
    report = analyze_agent_economics(runs)
    assert "simple" in report.complexities
    assert "complex" in report.complexities
    simple = [s for s in report.summaries if s.complexity == "simple"]
    complex_ = [s for s in report.summaries if s.complexity == "complex"]
    assert simple[0].avg_quality == pytest.approx(4.0)
    assert complex_[0].avg_quality == pytest.approx(3.0)


# --------------------------------------------------------------------------- #
# H. Human economics
# --------------------------------------------------------------------------- #
def test_higher_inference_cost_can_have_lower_effective_cost():
    # Agent A: cheap inference but 15 min rework. Agent B: pricier, 1 min rework.
    agent_a = summarize_architecture(
        [
            make_run(
                "A",
                agent_cost=0.05,
                human_rework_minutes=15,
                hourly_human_cost=120,
            )
        ],
        architecture="A",
    )
    agent_b = summarize_architecture(
        [
            make_run(
                "B",
                agent_cost=0.40,
                human_rework_minutes=1,
                hourly_human_cost=120,
            )
        ],
        architecture="B",
    )
    # A: 0.05 + 30.0 = 30.05 ; B: 0.40 + 2.0 = 2.40
    assert agent_a.avg_effective_task_cost == pytest.approx(30.05)
    assert agent_b.avg_effective_task_cost == pytest.approx(2.40)
    assert agent_b.avg_agent_cost > agent_a.avg_agent_cost
    assert agent_b.avg_effective_task_cost < agent_a.avg_effective_task_cost


# --------------------------------------------------------------------------- #
# I. Business economics
# --------------------------------------------------------------------------- #
def test_expected_net_value_with_business_inputs():
    runs = [
        make_run(
            "deep",
            agent_cost=1.0,
            task_success=True,
            business_value_if_success=1000.0,
            failure_cost=200.0,
        ),
        make_run(
            "deep",
            agent_cost=1.0,
            task_success=False,
            business_value_if_success=1000.0,
            failure_cost=200.0,
        ),
    ]
    summary = summarize_architecture(runs, architecture="deep")
    # Success run: 1000 - 0 - 1 = 999 ; failure run: 0 - 200 - 1 = -201 ; avg = 399.
    assert summary.avg_expected_net_value == pytest.approx(399.0)


def test_business_value_stays_unavailable_without_inputs():
    summary = summarize_architecture(
        [make_run("deep", agent_cost=1.0, task_success=True)], architecture="deep"
    )
    assert summary.avg_expected_net_value is None


# --------------------------------------------------------------------------- #
# J. Reporting
# --------------------------------------------------------------------------- #
def test_report_sections_and_unavailable_rendering():
    runs = [
        make_run("baseline", complexity="simple", quality_score=4.4, total_tokens=12000,
                 web_searches=1, latency_seconds=10, agent_cost=0.05, task_success=True),
        make_run("deep", complexity="simple", quality_score=4.5, total_tokens=23000,
                 web_searches=3, latency_seconds=21, agent_cost=0.12, task_success=True),
    ]
    report = analyze_agent_economics(runs)
    text = render_economics_report(report)

    assert "Agent Economics Report" in text
    assert "DATA COVERAGE" in text
    assert "SIMPLE TASKS" in text
    assert "VALUE FRONTIER" in text
    assert "DOMINATED" in text
    assert "MARGINAL RETURNS" in text
    assert "HUMAN ECONOMICS" in text
    assert "BUSINESS VALUE" in text
    assert "RECOMMENDED ROUTING" in text
    # Human economics not supplied -> shown as unavailable, never a fabricated 0.
    assert "unavailable" in text


def test_report_distinguishes_unavailable_from_zero():
    # subagent_calls is genuinely zero; agent_cost is unavailable.
    runs = [
        make_run("deep", complexity="simple", quality_score=4.0,
                 subagent_calls=0, total_tokens=1000),
    ]
    report = analyze_agent_economics(runs)
    text = render_economics_report(report)
    assert "Avg subagents:  0.0" in text
    assert "Avg agent cost: unavailable" in text


def test_report_no_fabricated_dollar_values_without_cost():
    runs = [
        make_run("baseline", complexity="simple", quality_score=4.0, total_tokens=1000),
        make_run("deep", complexity="simple", quality_score=4.2, total_tokens=3000),
    ]
    report = analyze_agent_economics(runs)
    assert report.cost_available is False
    text = render_economics_report(report)
    assert "Avg agent cost: unavailable" in text


def test_routing_prefers_cheaper_when_quality_comparable():
    runs = [
        make_run("baseline", complexity="simple", quality_score=4.5, agent_cost=0.05),
        make_run("deep", complexity="simple", quality_score=4.52, agent_cost=0.40),
    ]
    report = analyze_agent_economics(runs)
    routing = {rec.complexity: rec for rec in report.routing}
    assert routing["simple"].state == PREFER
    assert routing["simple"].architecture == "baseline"


def test_routing_investigates_on_genuine_tradeoff():
    runs = [
        make_run("baseline", complexity="complex", quality_score=3.5, agent_cost=0.05),
        make_run("deep", complexity="complex", quality_score=4.8, agent_cost=0.40),
    ]
    report = analyze_agent_economics(runs)
    routing = {rec.complexity: rec for rec in report.routing}
    assert routing["complex"].state == INVESTIGATE


def test_dominated_architecture_rendered_with_avoid():
    runs = [
        make_run("a", complexity="simple", quality_score=4.5, agent_cost=0.05),
        make_run("b", complexity="simple", quality_score=4.0, agent_cost=0.40),
    ]
    report = analyze_agent_economics(runs)
    text = render_economics_report(report)
    assert AVOID in text
    assert "b" in report.frontier_by_complexity["simple"].dominated


# --------------------------------------------------------------------------- #
# K. P8C compatibility (adapters)
# --------------------------------------------------------------------------- #
def test_economics_run_from_run_record_reuses_metrics():
    record = make_run_record(
        "case1",
        complexity="medium",
        quality=4.2,
        metrics={
            "input_tokens": 700,
            "output_tokens": 300,
            "total_tokens": 1000,
            "model_calls": 4,
            "web_searches": 2,
            "tool_calls": 3,
            "subagent_calls": 0,
        },
        latency=1.5,
    )
    run = economics_run_from_run_record(record, "deep-agent", agent_cost=0.1)
    assert run.task_id == "case1"
    assert run.architecture == "deep-agent"
    assert run.complexity == "medium"
    assert run.total_tokens == 1000
    assert run.web_searches == 2
    assert run.quality_score == 4.2
    assert run.latency_seconds == 1.5
    assert run.agent_cost == 0.1
    # No human/business data supplied -> stays unavailable.
    assert run.human_review_minutes is None
    assert run.business_value_if_success is None


def test_economics_run_success_from_checks():
    passing = make_run_record("c", checks={"a": True, "b": True})
    failing = make_run_record("c", checks={"a": True, "b": False})
    none_checks = make_run_record("c", checks={})

    assert economics_run_from_run_record(
        passing, "deep", success_from_checks=True
    ).task_success is True
    assert economics_run_from_run_record(
        failing, "deep", success_from_checks=True
    ).task_success is False
    assert economics_run_from_run_record(
        none_checks, "deep", success_from_checks=True
    ).task_success is None


def test_economics_runs_from_variant_result():
    records = [
        make_run_record("c1", metrics={"total_tokens": 1000}),
        make_run_record("c2", metrics={"total_tokens": 2000}),
    ]
    variant = VariantResult(label="deep-agent", records=records)
    runs = economics_runs_from_variant_result(variant)
    assert len(runs) == 2
    assert all(run.architecture == "deep-agent" for run in runs)


def test_economics_runs_from_comparison_report():
    baseline_records = [
        make_run_record("c1", metrics={"total_tokens": 1000, "web_searches": 1}, quality=4.0),
    ]
    candidate_records = [
        make_run_record("c1", metrics={"total_tokens": 2000, "web_searches": 3}, quality=4.3),
    ]
    baseline = VariantResult(label="baseline", records=baseline_records)
    candidate = VariantResult(label="candidate", records=candidate_records)
    report = build_comparison_report(baseline, candidate)

    runs = economics_runs_from_comparison_report(report)
    architectures = {run.architecture for run in runs}
    assert architectures == {"baseline", "candidate"}
    # Both sides can now be aggregated and analyzed by P8D.
    summaries = summarize_architectures(runs)
    assert len(summaries) == 2


def test_full_analysis_from_p8c_data_is_offline():
    records_base = [
        make_run_record("c1", complexity="simple",
                        metrics={"total_tokens": 1000, "web_searches": 1}, quality=4.4),
    ]
    records_cand = [
        make_run_record("c1", complexity="simple",
                        metrics={"total_tokens": 2000, "web_searches": 3}, quality=4.5),
    ]
    report = build_comparison_report(
        VariantResult(label="baseline", records=records_base),
        VariantResult(label="deep", records=records_cand),
    )
    runs = economics_runs_from_comparison_report(report)
    econ_report = analyze_agent_economics(runs)
    assert isinstance(econ_report, EconomicsReport)
    assert isinstance(render_economics_report(econ_report), str)


# --------------------------------------------------------------------------- #
# M. Sample dataset / load-or-build helper
# --------------------------------------------------------------------------- #
def test_build_sample_runs_is_deterministic_and_fresh():
    first = build_sample_economics_runs()
    second = build_sample_economics_runs()
    assert len(first) == 48
    assert first is not second
    assert {run.architecture for run in first} == {
        "baseline-search", "deep-agent", "deep-agent-skills", "deep-agent-subagents"
    }
    assert {run.complexity for run in first} == {"simple", "medium", "complex"}


def test_load_or_build_falls_back_to_sample_when_missing(tmp_path):
    runs = load_or_build_runs(tmp_path / "nope.json")
    assert len(runs) == 48


def test_load_or_build_reads_json_runs(tmp_path):
    source = [
        make_run("deep", complexity="simple", quality_score=4.0, total_tokens=1000).to_dict(),
        make_run("baseline", complexity="simple", quality_score=4.2).to_dict(),
    ]
    path = tmp_path / "runs.json"
    path.write_text(json.dumps(source), encoding="utf-8")

    runs = load_or_build_runs(path)
    assert len(runs) == 2
    assert all(isinstance(run, EconomicsRun) for run in runs)
    # Derived keys in the dict (e.g. resolved_total_tokens) are ignored on load.
    assert runs[0].architecture == "deep"


def test_economics_run_dict_round_trip():
    run = make_run("deep", complexity="medium", quality_score=4.5, total_tokens=2000,
                   agent_cost=0.2, task_success=True)
    restored = EconomicsRun.from_dict(run.to_dict())
    assert restored.to_dict() == run.to_dict()


def test_sample_dataset_drives_expected_routing():
    report = analyze_agent_economics(build_sample_economics_runs())
    routing = {rec.complexity: rec for rec in report.routing}
    assert routing["simple"].architecture == "baseline-search"
    assert routing["medium"].architecture == "deep-agent-skills"
    assert routing["complex"].state == INVESTIGATE

