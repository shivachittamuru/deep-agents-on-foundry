"""Tests for P8D economics-analysis JSON persistence (economics_log).

Deterministic and synthetic only: no Azure/Foundry, no network. All records are
built from fabricated ``EconomicsRun`` data and written under ``tmp_path``.
"""

from __future__ import annotations

import json

import pytest

from deep_agents_foundry.economics import (
    EconomicsRecord,
    EconomicsRun,
    analyze_agent_economics,
    list_economics_records,
    load_economics_record,
    save_economics_analysis,
    save_economics_record,
)
from deep_agents_foundry.economics.economics_log import DEFAULT_ECONOMICS_DIR
from deep_agents_foundry.errors import EconomicsLogError


def make_run(architecture, *, complexity="simple", **kwargs):
    return EconomicsRun(
        task_id=kwargs.pop("task_id", "task"),
        architecture=architecture,
        complexity=complexity,
        **kwargs,
    )


def sample_report():
    runs = [
        make_run("baseline", complexity="simple", quality_score=4.4,
                 total_tokens=12000, web_searches=1, latency_seconds=10,
                 agent_cost=0.05, task_success=True),
        make_run("deep", complexity="simple", quality_score=4.0,
                 total_tokens=23000, web_searches=3, latency_seconds=21,
                 agent_cost=0.40, task_success=True),
    ]
    return analyze_agent_economics(runs)


# --------------------------------------------------------------------------- #
# Default directory / file creation
# --------------------------------------------------------------------------- #
def test_save_creates_directory_and_file(tmp_path):
    record = EconomicsRecord.from_report(sample_report(), analysis_id="study-01")
    directory = tmp_path / "economics"
    path = save_economics_record(record, directory=directory)

    assert path.exists()
    assert path.parent == directory
    assert path.suffix == ".json"


def test_default_directory_constant_is_artifacts_economics():
    assert DEFAULT_ECONOMICS_DIR.as_posix() == "artifacts/economics"


# --------------------------------------------------------------------------- #
# JSON round-trip
# --------------------------------------------------------------------------- #
def test_json_round_trip(tmp_path):
    record = EconomicsRecord.from_report(sample_report(), analysis_id="study-01",
                                         notes="baseline vs deep")
    path = save_economics_record(record, directory=tmp_path)
    loaded = load_economics_record(path)

    assert loaded.analysis_id == "study-01"
    assert loaded.notes == "baseline vs deep"
    assert loaded.architectures == record.architectures
    assert loaded.complexities == record.complexities
    assert loaded.frontier_by_complexity == record.frontier_by_complexity
    assert loaded.to_dict() == record.to_dict()


def test_saved_json_is_indented_utf8(tmp_path):
    record = EconomicsRecord.from_report(sample_report(), analysis_id="study-01")
    path = save_economics_record(record, directory=tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "\n  " in text  # indented
    # Valid JSON object.
    assert isinstance(json.loads(text), dict)


# --------------------------------------------------------------------------- #
# Multiple analyses -> separate files
# --------------------------------------------------------------------------- #
def test_multiple_analyses_create_separate_files(tmp_path):
    save_economics_analysis(sample_report(), analysis_id="study-01", directory=tmp_path)
    save_economics_analysis(sample_report(), analysis_id="study-02", directory=tmp_path)

    files = sorted(tmp_path.glob("*.json"))
    assert len(files) == 2
    records = list_economics_records(tmp_path)
    ids = {record.analysis_id for record in records}
    assert ids == {"study-01", "study-02"}


def test_list_records_missing_directory_returns_empty(tmp_path):
    assert list_economics_records(tmp_path / "nope") == []


# --------------------------------------------------------------------------- #
# Safe filename generation
# --------------------------------------------------------------------------- #
def test_safe_filename_generation(tmp_path):
    record = EconomicsRecord.from_report(
        sample_report(), analysis_id="arch study/01: prod?"
    )
    path = save_economics_record(record, directory=tmp_path)
    name = path.name
    # No unsafe characters leak into the filename.
    for bad in ("/", "\\", "?", ":", " "):
        assert bad not in name
    assert name.endswith(".json")


def test_explicit_path_overrides_directory(tmp_path):
    record = EconomicsRecord.from_report(sample_report(), analysis_id="study-01")
    target = tmp_path / "nested" / "custom.json"
    path = save_economics_record(record, path=target)
    assert path == target
    assert target.exists()


# --------------------------------------------------------------------------- #
# Missing values remain null
# --------------------------------------------------------------------------- #
def test_missing_values_remain_null(tmp_path):
    # No cost, no human, no business data supplied.
    runs = [
        make_run("baseline", complexity="simple", quality_score=4.0, total_tokens=1000),
    ]
    report = analyze_agent_economics(runs)
    path = save_economics_analysis(report, analysis_id="null-study", directory=tmp_path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["cost_available"] is False
    assert data["human_economics"] == []
    assert data["business_value"] == []

    summary = data["summaries"][0]
    assert summary["avg_agent_cost"] is None  # null, not 0
    assert summary["avg_quality"] == 4.0
    # Genuine data preserved, missing preserved as null.
    assert "avg_agent_cost" in summary


# --------------------------------------------------------------------------- #
# Frontier / dominated / recommendations persist
# --------------------------------------------------------------------------- #
def test_frontier_and_dominated_persist(tmp_path):
    report = sample_report()
    path = save_economics_analysis(report, analysis_id="frontier-study", directory=tmp_path)
    loaded = load_economics_record(path)

    # baseline dominates deep on simple (higher quality, lower cost).
    assert loaded.frontier_by_complexity["simple"] == ["baseline"]
    assert loaded.dominated_by_complexity["simple"] == ["deep"]


def test_recommendations_persist(tmp_path):
    report = sample_report()
    path = save_economics_analysis(report, analysis_id="routing-study", directory=tmp_path)
    loaded = load_economics_record(path)

    assert loaded.routing
    assert loaded.preferred_by_complexity.get("simple") == "baseline"
    # Every routing entry keeps its interpretable fields.
    for rec in loaded.routing:
        assert {"complexity", "state", "architecture", "rationale"} <= set(rec)


def test_marginal_returns_persist(tmp_path):
    runs = [
        make_run("deep", web_searches=1, quality_score=4.0),
        make_run("deep", web_searches=2, quality_score=4.6),
        make_run("deep", web_searches=3, quality_score=4.8),
        make_run("deep", web_searches=4, quality_score=4.81),
    ]
    report = analyze_agent_economics(runs)
    path = save_economics_analysis(report, analysis_id="marginal-study", directory=tmp_path)
    loaded = load_economics_record(path)

    assert loaded.marginal_returns
    assert any(entry["candidate_elbow"] == 3.0 for entry in loaded.marginal_returns)


# --------------------------------------------------------------------------- #
# Malformed JSON fails clearly
# --------------------------------------------------------------------------- #
def test_malformed_json_raises_clear_error(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(EconomicsLogError):
        load_economics_record(bad)


def test_non_object_json_raises_clear_error(tmp_path):
    bad = tmp_path / "list.json"
    bad.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(EconomicsLogError):
        load_economics_record(bad)


# --------------------------------------------------------------------------- #
# Only primitive values are serialized (no runtime objects)
# --------------------------------------------------------------------------- #
def test_record_holds_only_primitive_serializable_values(tmp_path):
    record = EconomicsRecord.from_report(sample_report(), analysis_id="study-01")
    # asdict + json.dumps would raise on any non-primitive runtime object.
    serialized = json.dumps(record.to_dict())
    assert isinstance(serialized, str)


def test_business_and_human_summaries_persist_when_available(tmp_path):
    runs = [
        make_run("deep", complexity="medium", quality_score=4.0, agent_cost=0.40,
                 task_success=True, business_value_if_success=1000.0, failure_cost=200.0,
                 human_rework_minutes=5, hourly_human_cost=120),
    ]
    report = analyze_agent_economics(runs)
    path = save_economics_analysis(report, analysis_id="value-study", directory=tmp_path)
    loaded = load_economics_record(path)

    assert loaded.human_economics_available is True
    assert loaded.business_value_available is True
    assert loaded.human_economics
    assert loaded.business_value
    assert loaded.human_economics[0]["avg_human_cost"] is not None
    assert loaded.business_value[0]["avg_expected_net_value"] is not None
