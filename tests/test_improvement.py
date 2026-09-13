"""Tests for the offline improvement framework (P8C).

Deterministic only: fake async agents and fake judge models, no live Azure/
Foundry calls. Comparison/report/recommendation logic is exercised with fabricated
``RunRecord`` results so the numeric conclusions are fully controlled.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from deep_agents_foundry.improvement import (
    INVESTIGATE,
    KEEP,
    REVERT,
    ComparisonReport,
    EvaluationCase,
    FAILURE_CATEGORIES,
    ImprovementHypothesis,
    RecommendationRules,
    RunRecord,
    VariantResult,
    build_comparison_report,
    compare_agent_variants,
    core_research_dataset,
    dev_cases,
    evaluate_agent_variant,
    held_out_cases,
    render_improvement_report,
)
from deep_agents_foundry.improvement import runner as runner_module


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
def msg(content=None, tool_calls=None, content_blocks=None, usage_metadata=None):
    return SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
        content_blocks=content_blocks,
        usage_metadata=usage_metadata,
    )


class FakeAgent:
    """Async agent stand-in that returns scripted results and records calls."""

    def __init__(self, script):
        self._script = script
        self.calls = []

    async def ainvoke(self, payload, config=None, context=None):
        self.calls.append({"payload": payload, "config": config, "context": context})
        return self._script(payload, config, context)


class FakeJudge:
    """Judge model stand-in returning a fixed JSON string with an overall score."""

    def __init__(self, overall):
        self._overall = overall

    def invoke(self, prompt):
        import json

        return SimpleNamespace(
            content=json.dumps({"weighted_overall_score": self._overall})
        )


def make_record(
    case_id,
    *,
    complexity="medium",
    quality=None,
    web_searches=3,
    total_tokens=1000,
    model_calls=4,
    tool_calls=3,
    subagent_calls=0,
    latency=1.0,
    checks=None,
    expected=None,
    variant_label="v",
):
    metrics = {
        "input_tokens": None if total_tokens is None else int(total_tokens * 0.7),
        "output_tokens": None if total_tokens is None else int(total_tokens * 0.3),
        "total_tokens": total_tokens,
        "model_calls": model_calls,
        "web_searches": web_searches,
        "tool_calls": tool_calls,
        "subagent_calls": subagent_calls,
    }
    return RunRecord(
        case_id=case_id,
        complexity=complexity,
        prompt=f"prompt for {case_id}",
        expected=expected or {},
        variant_label=variant_label,
        thread_id=f"t-{case_id}",
        latency_seconds=latency,
        final_text="an answer",
        metrics=metrics,
        trajectory_features={},
        trajectory_summary={},
        deterministic={},
        checks=checks or {"completed": True, "answer_non_empty": True},
        raw_result=None,
        rubric=None if quality is None else {"weighted_overall_score": quality},
        quality=quality,
    )


# --------------------------------------------------------------------------- #
# A. Dataset
# --------------------------------------------------------------------------- #
def test_core_dataset_loads_and_has_required_fields():
    dataset = core_research_dataset()
    assert 6 <= len(dataset) <= 12
    for case in dataset:
        assert isinstance(case, EvaluationCase)
        assert case.id and case.prompt and case.complexity


def test_core_dataset_ids_unique():
    ids = [case.id for case in core_research_dataset()]
    assert len(ids) == len(set(ids))


def test_dev_and_held_out_do_not_overlap_and_cover_dataset():
    dev = {case.id for case in dev_cases()}
    held = {case.id for case in held_out_cases()}
    all_ids = {case.id for case in core_research_dataset()}

    assert dev
    assert held
    assert dev.isdisjoint(held)
    assert dev | held == all_ids


def test_dataset_covers_representative_behaviors():
    dataset = core_research_dataset()
    complexities = {case.complexity for case in dataset}
    assert {"simple", "medium", "complex"} <= complexities

    # A negative tool-use case exists.
    assert any(case.expected.get("needs_web") is False for case in dataset)
    # A skill-routing case exists.
    assert any("expected_skill" in case.expected for case in dataset)
    # A delegation/subagent case exists.
    assert any(case.expected.get("should_delegate") for case in dataset)


# --------------------------------------------------------------------------- #
# B. Runner
# --------------------------------------------------------------------------- #
def test_runner_invokes_agent_and_records_result():
    def script(payload, config, context):
        return {"messages": [msg(content="hello world")]}

    agent = FakeAgent(script)
    case = EvaluationCase(id="c1", prompt="hi", complexity="simple")

    result = asyncio.run(
        evaluate_agent_variant(agent, [case], variant_label="baseline")
    )

    assert isinstance(result, VariantResult)
    record = result.records[0]
    assert record.final_text == "hello world"
    assert record.latency_seconds >= 0.0
    assert len(agent.calls) == 1


def test_runner_creates_independent_thread_ids():
    def script(payload, config, context):
        return {"messages": [msg(content="ok")]}

    agent = FakeAgent(script)
    cases = [
        EvaluationCase(id="a", prompt="p", complexity="simple"),
        EvaluationCase(id="b", prompt="p", complexity="simple"),
    ]

    asyncio.run(evaluate_agent_variant(agent, cases, variant_label="cand"))

    thread_ids = [
        call["config"]["configurable"]["thread_id"] for call in agent.calls
    ]
    assert len(thread_ids) == len(set(thread_ids)) == 2


def test_runner_propagates_context_only_when_supplied():
    seen = {}

    def script(payload, config, context):
        seen["context"] = context
        return {"messages": [msg(content="ok")]}

    agent = FakeAgent(script)
    case = EvaluationCase(id="c", prompt="p", complexity="simple")
    sentinel = object()

    asyncio.run(
        evaluate_agent_variant(
            agent, [case], variant_label="v", context=sentinel
        )
    )
    assert seen["context"] is sentinel


def test_runner_without_context_omits_context_kwarg():
    class NoContextAgent:
        def __init__(self):
            self.calls = 0

        async def ainvoke(self, payload, config=None):
            self.calls += 1
            return {"messages": [msg(content="ok")]}

    agent = NoContextAgent()
    case = EvaluationCase(id="c", prompt="p", complexity="simple")
    asyncio.run(evaluate_agent_variant(agent, [case], variant_label="v"))
    assert agent.calls == 1


# --------------------------------------------------------------------------- #
# C. Trajectory / evaluation integration
# --------------------------------------------------------------------------- #
def test_runner_reuses_evaluation_helpers(monkeypatch):
    called = {"traj": 0, "usage": 0, "det": 0}

    real_traj = runner_module.extract_trajectory_features
    real_usage = runner_module.aggregate_usage
    real_det = runner_module.deterministic_evaluation

    def spy_traj(messages):
        called["traj"] += 1
        return real_traj(messages)

    def spy_usage(messages):
        called["usage"] += 1
        return real_usage(messages)

    def spy_det(messages, **kwargs):
        called["det"] += 1
        return real_det(messages, **kwargs)

    monkeypatch.setattr(runner_module, "extract_trajectory_features", spy_traj)
    monkeypatch.setattr(runner_module, "aggregate_usage", spy_usage)
    monkeypatch.setattr(runner_module, "deterministic_evaluation", spy_det)

    def script(payload, config, context):
        return {
            "messages": [
                msg(content_blocks=[{"type": "server_tool_call"}]),
                msg(
                    content="Answer with a source https://example.com",
                    usage_metadata={
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "total_tokens": 15,
                    },
                ),
            ]
        }

    agent = FakeAgent(script)
    case = EvaluationCase(
        id="c", prompt="p", complexity="simple", expected={"needs_web": True}
    )
    result = asyncio.run(evaluate_agent_variant(agent, [case], variant_label="v"))
    record = result.records[0]

    assert called["traj"] >= 1
    assert called["usage"] >= 1
    assert called["det"] >= 1
    assert record.metrics["web_searches"] == 1
    assert record.metrics["total_tokens"] == 15


def test_runner_missing_usage_does_not_crash_and_is_none():
    def script(payload, config, context):
        return {"messages": [msg(content="no usage here")]}

    agent = FakeAgent(script)
    case = EvaluationCase(id="c", prompt="p", complexity="simple")
    result = asyncio.run(evaluate_agent_variant(agent, [case], variant_label="v"))
    record = result.records[0]

    assert record.metrics["total_tokens"] is None
    assert record.metrics["model_calls"] is None
    # Derivable metrics are still real zeros, not missing.
    assert record.metrics["web_searches"] == 0
    assert record.metrics["tool_calls"] == 0


def test_runner_applies_judge_and_extracts_quality():
    def script(payload, config, context):
        return {"messages": [msg(content="answer")]}

    agent = FakeAgent(script)
    case = EvaluationCase(id="c", prompt="p", complexity="simple")
    result = asyncio.run(
        evaluate_agent_variant(
            agent, [case], variant_label="v", judge_model=FakeJudge(4.2)
        )
    )
    assert result.records[0].quality == pytest.approx(4.2)


# --------------------------------------------------------------------------- #
# D. Baseline / candidate comparison deltas
# --------------------------------------------------------------------------- #
def test_comparison_computes_expected_deltas():
    baseline = VariantResult(
        label="baseline",
        records=[
            make_record("c1", quality=3.0, web_searches=4, total_tokens=1000),
        ],
    )
    candidate = VariantResult(
        label="candidate",
        records=[
            make_record("c1", quality=4.0, web_searches=2, total_tokens=800),
        ],
    )

    report = build_comparison_report(baseline, candidate)
    case = report.case_comparisons[0]

    assert case.quality_delta == pytest.approx(1.0)
    assert case.deltas["web_searches"] == pytest.approx(-2.0)
    assert case.deltas["total_tokens"] == pytest.approx(-200.0)
    assert report.quality_delta == pytest.approx(1.0)


def test_comparison_flags_regressed_check():
    baseline = VariantResult(
        label="baseline",
        records=[
            make_record(
                "c1",
                quality=3.0,
                checks={"completed": True, "citations_present": True},
            )
        ],
    )
    candidate = VariantResult(
        label="candidate",
        records=[
            make_record(
                "c1",
                quality=3.0,
                checks={"completed": True, "citations_present": False},
            )
        ],
    )

    report = build_comparison_report(baseline, candidate)
    case = report.case_comparisons[0]

    assert case.critical_regression is True
    assert any("citations_present" in reason for reason in case.regressions)
    assert report.has_regression is True


def test_comparison_missing_quality_yields_none_delta():
    baseline = VariantResult(label="b", records=[make_record("c1", quality=None)])
    candidate = VariantResult(label="c", records=[make_record("c1", quality=None)])

    report = build_comparison_report(baseline, candidate)
    assert report.quality_delta is None
    assert report.case_comparisons[0].quality_delta is None


# --------------------------------------------------------------------------- #
# E. Reporting
# --------------------------------------------------------------------------- #
def _report(baseline_records, candidate_records):
    return build_comparison_report(
        VariantResult(label="baseline", records=baseline_records),
        VariantResult(label="candidate", records=candidate_records),
    )


def test_report_identifies_improvement():
    report = _report(
        [make_record("c1", quality=3.0)],
        [make_record("c1", quality=4.0)],
    )
    assert report.has_improvement is True
    assert report.evidence == "clear"
    text = render_improvement_report(report)
    assert "RECOMMENDATION" in text
    assert "Improvement Report" in text


def test_report_identifies_regression():
    report = _report(
        [make_record("c1", quality=4.0, checks={"completed": True, "citations_present": True})],
        [make_record("c1", quality=3.0, checks={"completed": True, "citations_present": False})],
    )
    assert report.has_regression is True
    assert "clear" == report.evidence or "mixed" == report.evidence


def test_report_identifies_mixed_evidence():
    report = _report(
        [
            make_record("c1", quality=3.0, checks={"citations_present": True}),
            make_record("c2", quality=3.0, checks={"completed": True}),
        ],
        [
            make_record("c1", quality=4.0, checks={"citations_present": True}),
            make_record("c2", quality=3.0, checks={"completed": False}),
        ],
    )
    assert report.has_improvement is True
    assert report.has_regression is True
    assert report.evidence == "mixed"


def test_report_identifies_insufficient_evidence():
    report = _report(
        [make_record("c1", quality=None, checks={"completed": True})],
        [make_record("c1", quality=None, checks={"completed": True})],
    )
    assert report.evidence == "insufficient"


# --------------------------------------------------------------------------- #
# F. Recommendation
# --------------------------------------------------------------------------- #
def test_recommendation_keep_on_clear_improvement():
    report = _report(
        [make_record("c1", quality=3.0), make_record("c2", quality=3.0)],
        [make_record("c1", quality=4.0), make_record("c2", quality=3.8)],
    )
    assert report.recommendation == KEEP


def test_recommendation_revert_on_clear_regression():
    report = _report(
        [make_record("c1", quality=4.0, checks={"completed": True, "citations_present": True})],
        [make_record("c1", quality=3.0, checks={"completed": True, "citations_present": False})],
    )
    assert report.recommendation == REVERT


def test_recommendation_investigate_on_mixed_evidence():
    report = _report(
        [make_record("c1", quality=3.0, checks={"citations_present": True})],
        [make_record("c1", quality=3.6, checks={"citations_present": False})],
    )
    assert report.recommendation == INVESTIGATE


def test_recommendation_investigate_on_insufficient_evidence():
    report = _report(
        [make_record("c1", quality=None, checks={"completed": True})],
        [make_record("c1", quality=None, checks={"completed": True})],
    )
    assert report.recommendation == INVESTIGATE


def test_recommendation_keep_deterministic_only_improvement():
    report = _report(
        [make_record("c1", quality=None, checks={"completed": True, "citations_present": False})],
        [make_record("c1", quality=None, checks={"completed": True, "citations_present": True})],
    )
    assert report.recommendation == KEEP


# --------------------------------------------------------------------------- #
# Models / bookkeeping
# --------------------------------------------------------------------------- #
def test_improvement_hypothesis_validates_category():
    with pytest.raises(ValueError):
        ImprovementHypothesis(
            symptom="s",
            failure_category="not_a_category",
            hypothesis="h",
            proposed_change="c",
            primary_metric="quality",
            guardrail_metric="tokens",
        )

    hypothesis = ImprovementHypothesis(
        symptom="duplicate searches",
        failure_category="tool_use",
        hypothesis="tighten search policy",
        proposed_change="add dedupe guidance",
        primary_metric="web_searches",
        guardrail_metric="quality",
    )
    assert hypothesis.failure_category in FAILURE_CATEGORIES


def test_report_to_dict_round_trips_structure():
    report = _report(
        [make_record("c1", quality=3.0)],
        [make_record("c1", quality=4.0)],
    )
    data = report.to_dict()
    assert data["recommendation"] == report.recommendation
    assert data["cases"][0]["case_id"] == "c1"


# --------------------------------------------------------------------------- #
# High-level async API end to end (fakes only)
# --------------------------------------------------------------------------- #
def test_compare_agent_variants_end_to_end():
    def baseline_script(payload, config, context):
        return {
            "messages": [
                msg(content_blocks=[{"type": "server_tool_call"}]),
                msg(content_blocks=[{"type": "server_tool_call"}]),
                msg(content="answer https://example.com"),
            ]
        }

    def candidate_script(payload, config, context):
        return {
            "messages": [
                msg(content_blocks=[{"type": "server_tool_call"}]),
                msg(content="answer https://example.com"),
            ]
        }

    baseline_agent = FakeAgent(baseline_script)
    candidate_agent = FakeAgent(candidate_script)
    dataset = [
        EvaluationCase(
            id="c1", prompt="p", complexity="simple", expected={"needs_web": True}
        )
    ]

    report = asyncio.run(
        compare_agent_variants(
            baseline_agent,
            candidate_agent,
            dataset=dataset,
            judge_model=FakeJudge(4.0),
        )
    )

    assert isinstance(report, ComparisonReport)
    case = report.case_comparisons[0]
    assert case.deltas["web_searches"] == pytest.approx(-1.0)
    assert report.recommendation in {KEEP, REVERT, INVESTIGATE}


def test_recommendation_rules_are_configurable():
    strict = RecommendationRules(quality_keep=2.0)
    report = build_comparison_report(
        VariantResult(label="b", records=[make_record("c1", quality=3.0)]),
        VariantResult(label="c", records=[make_record("c1", quality=4.0)]),
        rules=strict,
    )
    # A +1.0 quality gain no longer clears the raised KEEP threshold.
    assert report.recommendation == INVESTIGATE
