"""Stable async runner around an already-built Research Deep Agent (P8C).

The runner is intentionally boring: it stays fixed while the agent under test
changes. It never constructs the production agent — callers pass an already-built
agent (e.g. `build_research_agent(...)`), keeping runtime configuration separate
from experimentation.

All heavy evaluation logic is reused from `evaluation.py`; this module only
orchestrates invocation, timing, metric collection, and (optional) judging.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from ..content import content_text
from ..evaluation import (
    aggregate_usage,
    deterministic_evaluation,
    evaluate_with_rubric,
    extract_trajectory_features,
    trajectory_summary,
)
from ..persistence import thread_config
from .models import EvaluationCase, RunRecord, VariantResult

# Local tool name used by Deep Agents for subagent delegation.
_SUBAGENT_TOOL_NAMES = frozenset({"task"})

_OVERALL_QUALITY_KEYS = (
    "weighted_overall_score",
    "weighted_overall",
    "overall_score",
    "overall",
    "weighted_score",
    "score",
)


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def overall_quality(rubric_result: Any) -> float | None:
    """Extract a single 1-5 overall score from a judge result, tolerantly.

    Returns ``None`` when no recognizable overall score is present rather than
    guessing, so missing quality stays explicit downstream.
    """
    if not isinstance(rubric_result, dict):
        return None

    for key in _OVERALL_QUALITY_KEYS:
        if key in rubric_result:
            number = _as_float(rubric_result[key])
            if number is not None:
                return number

    # One level of nesting (e.g. {"overall": {"score": 4.2}}).
    for value in rubric_result.values():
        if isinstance(value, dict):
            for key in _OVERALL_QUALITY_KEYS:
                if key in value:
                    number = _as_float(value[key])
                    if number is not None:
                        return number
    return None


def _messages_of(result: Any) -> list:
    """Pull the message list out of an ainvoke result, tolerating shapes."""
    if isinstance(result, dict):
        return list(result.get("messages", []) or [])
    messages = getattr(result, "messages", None)
    return list(messages) if messages else []


def _final_text(messages: list) -> str:
    if not messages:
        return ""
    return content_text(messages[-1])


def _usage_present(messages: list) -> bool:
    return any(getattr(message, "usage_metadata", None) for message in messages)


def _count_model_calls(messages: list) -> int:
    return sum(1 for message in messages if getattr(message, "usage_metadata", None))


def _count_subagent_calls(local_tool_calls: list) -> int:
    return sum(1 for name in local_tool_calls if name in _SUBAGENT_TOOL_NAMES)


def _collect_metrics(messages: list, features: dict, errors: dict) -> dict:
    """Collect operational metrics, marking unavailable ones as ``None``.

    Token and model-call counts depend on usage metadata that the runtime may not
    expose; those become ``None`` rather than a misleading zero. Search/tool/
    subagent counts are always derivable from the trajectory, so a genuine zero is
    reported as zero.
    """
    local_tool_calls = features.get("local_tool_calls", []) or []

    if _usage_present(messages):
        try:
            usage = aggregate_usage(messages)
        except Exception as exc:  # tolerate a broken usage extraction
            errors["usage"] = str(exc)
            usage = {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        total_tokens = usage.get("total_tokens")
        model_calls = _count_model_calls(messages)
    else:
        input_tokens = output_tokens = total_tokens = None
        model_calls = None

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "model_calls": model_calls,
        "web_searches": features.get("server_tool_calls", 0),
        "tool_calls": len(local_tool_calls),
        "subagent_calls": _count_subagent_calls(local_tool_calls),
    }


def _improvement_checks(
    *, expected: dict, final_text: str, metrics: dict
) -> dict[str, bool]:
    """Thin improvement-layer checks that reuse already-collected metrics.

    Deliberately minimal — deterministic search/file/citation logic lives in
    `evaluation.deterministic_evaluation` and is not duplicated here.
    """
    checks: dict[str, bool] = {"answer_non_empty": bool(final_text.strip())}

    web_searches = metrics.get("web_searches")
    if "max_searches" in expected and web_searches is not None:
        checks["within_search_budget"] = web_searches <= expected["max_searches"]

    subagent_calls = metrics.get("subagent_calls")
    if "should_delegate" in expected and subagent_calls is not None:
        checks["delegation_as_expected"] = (
            subagent_calls > 0
        ) == bool(expected["should_delegate"])

    return checks


def _boolean_checks(deterministic: dict, improvement: dict) -> dict[str, bool]:
    """Merge the boolean pass/fail checks used for regression detection."""
    merged: dict[str, bool] = {
        key: value
        for key, value in deterministic.items()
        if isinstance(value, bool)
    }
    merged.update(improvement)
    return merged


async def run_case(
    agent,
    case: EvaluationCase,
    *,
    variant_label: str,
    judge_model=None,
    context: Any = None,
    thread_prefix: str = "improve",
) -> RunRecord:
    """Execute one case against ``agent`` and assemble a full ``RunRecord``.

    An isolated ``thread_id`` is created per run so cases never share state.
    Optional runtime ``context`` (e.g. ``ResearchContext``) is forwarded only when
    supplied. Missing optional metrics never crash the run.
    """
    errors: dict[str, str] = {}
    expected = dict(case.expected)

    thread_id = f"{thread_prefix}-{variant_label}-{case.id}-{uuid4().hex[:8]}"
    config = thread_config(thread_id)
    payload = {"messages": [{"role": "user", "content": case.prompt}]}

    started = time.perf_counter()
    if context is None:
        result = await agent.ainvoke(payload, config=config)
    else:
        result = await agent.ainvoke(payload, config=config, context=context)
    latency = time.perf_counter() - started

    messages = _messages_of(result)
    final_text = _final_text(messages)

    try:
        features = extract_trajectory_features(messages)
    except Exception as exc:
        errors["trajectory_features"] = str(exc)
        features = {}

    try:
        traj_summary = trajectory_summary(messages, elapsed_seconds=latency)
    except Exception as exc:
        errors["trajectory_summary"] = str(exc)
        traj_summary = {}

    metrics = _collect_metrics(messages, features, errors)

    try:
        deterministic = deterministic_evaluation(
            messages,
            expects_search=bool(expected.get("needs_web", False)),
            expects_file=bool(expected.get("expects_file", False)),
            elapsed_seconds=latency,
        )
    except Exception as exc:
        errors["deterministic"] = str(exc)
        deterministic = {}

    improvement = _improvement_checks(
        expected=expected, final_text=final_text, metrics=metrics
    )
    checks = _boolean_checks(deterministic, improvement)

    rubric = None
    quality = None
    if judge_model is not None:
        try:
            rubric = evaluate_with_rubric(
                judge_model,
                case.prompt,
                final_text,
                trajectory_summary=traj_summary,
            )
            quality = overall_quality(rubric)
        except Exception as exc:
            errors["rubric"] = str(exc)

    return RunRecord(
        case_id=case.id,
        complexity=case.complexity,
        prompt=case.prompt,
        expected=expected,
        variant_label=variant_label,
        thread_id=thread_id,
        latency_seconds=latency,
        final_text=final_text,
        metrics=metrics,
        trajectory_features=features,
        trajectory_summary=traj_summary,
        deterministic=deterministic,
        checks=checks,
        raw_result=result,
        rubric=rubric,
        quality=quality,
        errors=errors,
    )


async def evaluate_agent_variant(
    agent,
    dataset,
    *,
    variant_label: str,
    judge_model=None,
    context: Any = None,
    thread_prefix: str = "improve",
) -> VariantResult:
    """Run an already-built agent over a dataset and return a ``VariantResult``.

    ``dataset`` is an iterable of ``EvaluationCase``. The same runner is used for
    baseline and candidate so execution plumbing stays identical.
    """
    records: list[RunRecord] = []
    for case in dataset:
        record = await run_case(
            agent,
            case,
            variant_label=variant_label,
            judge_model=judge_model,
            context=context,
            thread_prefix=thread_prefix,
        )
        records.append(record)
    return VariantResult(label=variant_label, records=records)
