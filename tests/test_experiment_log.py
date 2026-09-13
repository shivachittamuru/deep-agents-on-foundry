"""Tests for JSON persistence of P8C experiment history (tmp_path only)."""

from __future__ import annotations

import json

import pytest

from deep_agents_foundry.errors import ExperimentLogError
from deep_agents_foundry.improvement import (
    ExperimentRecord,
    RunRecord,
    VariantResult,
    build_comparison_report,
    list_experiment_records,
    load_experiment_record,
    save_experiment_record,
    save_improvement_experiment,
)


def _run_record(case_id, *, quality, web_searches, total_tokens, raw_result=None):
    return RunRecord(
        case_id=case_id,
        complexity="medium",
        prompt=f"prompt for {case_id}",
        expected={},
        variant_label="v",
        thread_id=f"t-{case_id}",
        latency_seconds=1.0,
        final_text="SECRET_FINAL_ANSWER",
        metrics={
            "input_tokens": None if total_tokens is None else 700,
            "output_tokens": None if total_tokens is None else 300,
            "total_tokens": total_tokens,
            "model_calls": None if total_tokens is None else 4,
            "web_searches": web_searches,
            "tool_calls": 3,
            "subagent_calls": 0,
        },
        trajectory_features={},
        trajectory_summary={},
        deterministic={},
        checks={"completed": True},
        raw_result=raw_result,
        rubric=None if quality is None else {"weighted_overall_score": quality},
        quality=quality,
    )


def _report(*, baseline_quality=3.0, candidate_quality=4.0, total_tokens=1000):
    baseline = VariantResult(
        label="baseline",
        records=[
            _run_record(
                "c1",
                quality=baseline_quality,
                web_searches=4,
                total_tokens=total_tokens,
                raw_result="SECRET_RAW_TRACE",
            )
        ],
    )
    candidate = VariantResult(
        label="candidate",
        records=[
            _run_record(
                "c1",
                quality=candidate_quality,
                web_searches=2,
                total_tokens=None if total_tokens is None else total_tokens - 200,
                raw_result="SECRET_RAW_TRACE",
            )
        ],
    )
    return build_comparison_report(baseline, candidate)


# a. save creates directory + file
def test_save_creates_directory_and_file(tmp_path):
    record = ExperimentRecord.from_report(_report(), change_id="exp-a")
    directory = tmp_path / "artifacts" / "experiments"

    path = save_experiment_record(record, directory=directory)

    assert path.exists()
    assert path.parent == directory
    assert path.suffix == ".json"


# b. saved JSON contains expected metadata and decision
def test_saved_json_contains_metadata_and_decision(tmp_path):
    record = ExperimentRecord.from_report(
        _report(),
        change_id="exp-b",
        hypothesis="reduce searches",
        change_description="tightened guidance",
        observed_failure="over-searching",
    )
    path = save_experiment_record(record, directory=tmp_path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["change_id"] == "exp-b"
    assert data["hypothesis"] == "reduce searches"
    assert data["change_description"] == "tightened guidance"
    assert data["observed_failure"] == "over-searching"
    assert data["decision"] == record.decision
    assert data["deltas"]["web_searches"] == pytest.approx(-2.0)


# c. load round-trips the record
def test_load_round_trips_record(tmp_path):
    record = ExperimentRecord.from_report(
        _report(), change_id="exp-c", notes="baseline run"
    )
    path = save_experiment_record(record, directory=tmp_path)

    loaded = load_experiment_record(path)
    assert isinstance(loaded, ExperimentRecord)
    assert loaded.to_dict() == record.to_dict()


# d. unavailable metrics remain null
def test_unavailable_metrics_remain_null(tmp_path):
    record = ExperimentRecord.from_report(
        _report(total_tokens=None), change_id="exp-d"
    )
    path = save_experiment_record(record, directory=tmp_path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["deltas"]["total_tokens"] is None
    assert data["deltas"]["model_calls"] is None
    # Derivable metric still present as a real number.
    assert data["deltas"]["web_searches"] == pytest.approx(-2.0)

    loaded = load_experiment_record(path)
    assert loaded.deltas["total_tokens"] is None


# e. safe filename generation for change_id
def test_safe_filename_generation(tmp_path):
    record = ExperimentRecord.from_report(
        _report(), change_id="skill/routing v2!!"
    )
    path = save_experiment_record(record, directory=tmp_path)

    name = path.name
    assert name.endswith(".json")
    # No unsafe path characters leaked into the filename.
    for bad in ("/", "\\", " ", "!", ":"):
        assert bad not in name
    assert "skill-routing-v2" in name


# f. list function returns saved records
def test_list_returns_saved_records(tmp_path):
    save_experiment_record(
        ExperimentRecord.from_report(_report(), change_id="exp-1"),
        directory=tmp_path,
    )
    records = list_experiment_records(directory=tmp_path)
    assert len(records) == 1
    assert records[0].change_id == "exp-1"


def test_list_missing_directory_returns_empty(tmp_path):
    assert list_experiment_records(directory=tmp_path / "nope") == []


# g. multiple experiments create separate files
def test_multiple_experiments_create_separate_files(tmp_path):
    r1 = ExperimentRecord.from_report(_report(), change_id="exp-1")
    r2 = ExperimentRecord.from_report(_report(), change_id="exp-2")
    r2.timestamp = "2030-01-01T00:00:00+00:00"

    p1 = save_experiment_record(r1, directory=tmp_path)
    p2 = save_experiment_record(r2, directory=tmp_path)

    assert p1 != p2
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 2
    assert {rec.change_id for rec in list_experiment_records(directory=tmp_path)} == {
        "exp-1",
        "exp-2",
    }


# h. raw agent results/traces are not serialized
def test_raw_results_are_not_persisted(tmp_path):
    path = save_improvement_experiment(
        _report(), change_id="exp-h", directory=tmp_path
    )
    text = path.read_text(encoding="utf-8")

    assert "SECRET_RAW_TRACE" not in text
    assert "SECRET_FINAL_ANSWER" not in text
    assert "raw_result" not in text
    assert "final_text" not in text


# i. malformed JSON raises a clear package-level error
def test_malformed_json_raises_experiment_log_error(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text("{ not valid json", encoding="utf-8")

    with pytest.raises(ExperimentLogError):
        load_experiment_record(bad)


def test_non_object_json_raises_experiment_log_error(tmp_path):
    bad = tmp_path / "list.json"
    bad.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ExperimentLogError):
        load_experiment_record(bad)


# Convenience helper end to end
def test_save_improvement_experiment_returns_path_and_persists(tmp_path):
    path = save_improvement_experiment(
        _report(),
        change_id="technology-skill-v2",
        hypothesis="Reduce redundant searches without lowering quality",
        change_description="Tightened technology-research skill search guidance",
        directory=tmp_path,
    )
    assert path.exists()

    loaded = load_experiment_record(path)
    assert loaded.change_id == "technology-skill-v2"
    assert loaded.hypothesis.startswith("Reduce redundant searches")
    assert isinstance(loaded, ExperimentRecord)


def test_explicit_path_overrides_directory(tmp_path):
    record = ExperimentRecord.from_report(_report(), change_id="exp-path")
    target = tmp_path / "nested" / "custom.json"

    path = save_experiment_record(record, path=target)
    assert path == target
    assert target.exists()
