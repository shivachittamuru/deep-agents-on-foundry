"""Sample economics dataset + a load-or-build helper (P8D).

Provides a small, deterministic four-architecture study spanning simple, medium,
and complex tasks so the economics pipeline can be exercised end-to-end without
any Azure/Foundry calls. The numbers mirror the guided notebook and are shaped to
show three realistic patterns:

* simple  - deeper orchestration adds cost without improving quality,
* medium  - skills cut wasted searching, raising quality *and* lowering cost,
* complex - quality keeps climbing with cost, so no single option dominates.

``load_or_build_runs`` loads a JSON list of runs when one is present and falls
back to the built-in synthetic study otherwise, so a script can stay repeatable
whether or not real run data has been dropped in.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..paths import artifacts_dir
from .models import EconomicsRun

# Optional on-disk source; when absent the synthetic study is built instead.
DEFAULT_RUNS_PATH = artifacts_dir("economics", "economics_runs.json")

# Per-group success patterns (four repetitions each).
_ALL_OK = (True, True, True, True)
_THREE_OK = (True, True, True, False)
_HALF_OK = (True, True, False, False)

# (architecture, complexity, quality, agent_cost, total_tokens, web_searches,
#  model_calls, subagent_calls, latency_seconds, successes)
_SAMPLE_GROUPS: tuple[tuple, ...] = (
    # SIMPLE
    ("baseline-search", "simple", 4.4, 0.05, 12000, 1, 2, 0, 10, _ALL_OK),
    ("deep-agent", "simple", 4.4, 0.12, 20000, 2, 4, 0, 18, _ALL_OK),
    ("deep-agent-skills", "simple", 4.4, 0.15, 21000, 2, 4, 0, 19, _ALL_OK),
    ("deep-agent-subagents", "simple", 4.3, 0.30, 34000, 3, 6, 2, 28, _ALL_OK),
    # MEDIUM
    ("baseline-search", "medium", 3.8, 0.15, 15000, 2, 3, 0, 16, _THREE_OK),
    ("deep-agent", "medium", 4.1, 0.14, 22000, 3, 5, 0, 22, _ALL_OK),
    ("deep-agent-skills", "medium", 4.6, 0.12, 20000, 3, 5, 0, 21, _ALL_OK),
    ("deep-agent-subagents", "medium", 4.5, 0.30, 33000, 4, 7, 2, 30, _ALL_OK),
    # COMPLEX
    ("baseline-search", "complex", 3.5, 0.20, 18000, 3, 4, 0, 20, _HALF_OK),
    ("deep-agent", "complex", 4.0, 0.35, 30000, 5, 7, 0, 32, _THREE_OK),
    ("deep-agent-skills", "complex", 4.3, 0.42, 34000, 6, 8, 0, 36, _THREE_OK),
    ("deep-agent-subagents", "complex", 4.8, 0.80, 52000, 8, 12, 3, 55, _ALL_OK),
)


def _build_group(
    architecture: str,
    complexity: str,
    quality: float,
    agent_cost: float,
    total_tokens: int,
    web_searches: int,
    model_calls: int,
    subagent_calls: int,
    latency: float,
    successes: tuple[bool, ...],
) -> list[EconomicsRun]:
    runs: list[EconomicsRun] = []
    for index, ok in enumerate(successes, start=1):
        runs.append(
            EconomicsRun(
                task_id=f"{complexity}-{index}",
                architecture=architecture,
                complexity=complexity,
                run_id=f"{architecture}-{complexity}-r{index}",
                input_tokens=int(total_tokens * 0.7),
                output_tokens=int(total_tokens * 0.3),
                total_tokens=total_tokens,
                model_calls=model_calls,
                web_searches=web_searches,
                tool_calls=web_searches,
                subagent_calls=subagent_calls,
                latency_seconds=latency,
                quality_score=quality,
                task_success=ok,
                agent_cost=agent_cost,
            )
        )
    return runs


def build_sample_economics_runs() -> list[EconomicsRun]:
    """Return the built-in synthetic four-architecture study (fresh each call)."""
    runs: list[EconomicsRun] = []
    for group in _SAMPLE_GROUPS:
        runs.extend(_build_group(*group))
    return runs


def load_economics_runs(path: str | Path) -> list[EconomicsRun]:
    """Load a JSON list of run objects into ``EconomicsRun`` records.

    The file must contain a JSON array of objects whose keys match
    ``EconomicsRun`` fields; unknown/derived keys are ignored.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Economics runs file at {path} must be a JSON array.")
    return [EconomicsRun.from_dict(item) for item in data]


def load_or_build_runs(path: str | Path | None = None) -> list[EconomicsRun]:
    """Load runs from ``path`` when it exists, otherwise build the sample study.

    With ``path=None`` the default location (``artifacts/economics/economics_runs.json``)
    is checked; when it is absent the deterministic synthetic study is returned so
    callers stay repeatable without any setup.
    """
    target = Path(path) if path is not None else DEFAULT_RUNS_PATH
    if target.is_file():
        return load_economics_runs(target)
    return build_sample_economics_runs()
