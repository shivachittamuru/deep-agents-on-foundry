"""Tests for evaluation utilities (no live model/Azure/Foundry calls)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from deep_agents_foundry import evaluation as ev


def msg(content=None, tool_calls=None, content_blocks=None, usage_metadata=None):
    """Build a minimal stand-in for a LangChain message."""
    return SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
        content_blocks=content_blocks,
        usage_metadata=usage_metadata,
    )


def test_extract_trajectory_features_server_and_local_calls():
    messages = [
        msg(content_blocks=[{"type": "server_tool_call"}, {"type": "text"}]),
        msg(tool_calls=[{"name": "write_file"}, {"name": "read_file"}]),
        msg(content_blocks=[{"type": "server_tool_call"}]),
    ]

    features = ev.extract_trajectory_features(messages)

    assert features["server_tool_calls"] == 2
    assert features["has_write_file"] is True
    assert features["has_read_file"] is True
    assert features["local_tool_calls"] == ["write_file", "read_file"]


def test_extract_trajectory_features_no_activity():
    features = ev.extract_trajectory_features([msg(content="hello")])

    assert features["server_tool_calls"] == 0
    assert features["local_tool_calls"] == []
    assert features["has_write_file"] is False
    assert features["has_read_file"] is False


def test_aggregate_usage_across_messages():
    messages = [
        msg(usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}),
        msg(usage_metadata=None),
        msg(usage_metadata={"input_tokens": 3, "output_tokens": 7, "total_tokens": 10}),
    ]

    usage = ev.aggregate_usage(messages)

    assert usage == {"input_tokens": 13, "output_tokens": 12, "total_tokens": 25}


def test_has_citation_like_content_detection():
    assert ev.has_citation_like_content(msg(content="see https://example.com")) is True
    assert ev.has_citation_like_content(msg(content="Source: docs")) is True
    assert ev.has_citation_like_content(msg(content="please cite this")) is True
    assert ev.has_citation_like_content(msg(content="no evidence here")) is False


def test_deterministic_evaluation_search_and_citations():
    messages = [
        msg(content_blocks=[{"type": "server_tool_call"}]),
        msg(content="Answer with a source: https://example.com"),
    ]

    checks = ev.deterministic_evaluation(
        messages,
        expects_search=True,
        expects_file=False,
        elapsed_seconds=12.3,
    )

    assert checks["completed"] is True
    assert checks["searched_when_expected"] is True
    assert checks["citations_present"] is True
    assert checks["server_tool_calls"] == 1
    assert checks["elapsed_seconds"] == 12.3
    assert "wrote_file" not in checks


def test_deterministic_evaluation_file_checks():
    messages = [
        msg(tool_calls=[{"name": "write_file"}, {"name": "read_file"}]),
        msg(content="done"),
    ]

    checks = ev.deterministic_evaluation(
        messages,
        expects_search=False,
        expects_file=True,
    )

    assert checks["wrote_file"] is True
    assert checks["read_file"] is True
    assert "searched_when_expected" not in checks
    assert "citations_present" not in checks


def test_deterministic_evaluation_empty_final_response():
    assert (
        ev.deterministic_evaluation(
            [msg(content="")], expects_search=False, expects_file=False
        )["completed"]
        is False
    )
    assert (
        ev.deterministic_evaluation(
            [], expects_search=False, expects_file=False
        )["completed"]
        is False
    )


def test_build_rubric_prompt_basic():
    prompt = ev.build_rubric_prompt("What is X?", "X is Y.")

    assert "enterprise technical research agent" in prompt
    assert "USER TASK:\nWhat is X?" in prompt
    assert "AGENT RESPONSE:\nX is Y." in prompt
    assert prompt.rstrip().endswith("Return valid JSON.")
    assert "TRAJECTORY SUMMARY:" not in prompt


def test_build_rubric_prompt_with_trajectory():
    prompt = ev.build_rubric_prompt(
        "q", "r", trajectory_summary={"server_search_calls": 2}
    )

    assert "TRAJECTORY SUMMARY:" in prompt
    assert '"server_search_calls": 2' in prompt


def test_evaluate_with_rubric_invokes_judge_and_parses(monkeypatch):
    captured = {}

    def fake_invoke(prompt):
        captured["prompt"] = prompt
        return msg(content='{"overall": 4, "task_completion": 5}')

    judge = SimpleNamespace(invoke=fake_invoke)

    result = ev.evaluate_with_rubric(judge, "the task", "the answer")

    assert result == {"overall": 4, "task_completion": 5}
    assert "the task" in captured["prompt"]
    assert "the answer" in captured["prompt"]


def test_parse_judge_json_from_content_blocks():
    text = ev._message_text(
        msg(content=[{"type": "text", "text": '{"a": 1}'}])
    )
    assert ev.parse_judge_json(text) == {"a": 1}


def test_parse_judge_json_with_code_fence():
    fenced = '```json\n{"score": 3}\n```'
    assert ev.parse_judge_json(fenced) == {"score": 3}


def test_parse_judge_json_malformed_raises():
    with pytest.raises(ValueError):
        ev.parse_judge_json("there is no json here")
