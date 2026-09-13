"""Lightweight JSON persistence for P8C experiment history.

Persists a compact summary of each completed baseline-vs-candidate experiment so
results survive process exit and can be reviewed later. One JSON file per
experiment; no database, no raw traces. Detailed traces stay in
Foundry/App Insights or in the in-memory ``ComparisonReport``.

Saving is always explicit — ``compare_agent_variants`` never writes files.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..errors import ExperimentLogError
from ..paths import artifacts_dir
from .models import ComparisonReport

# Default on-disk location; created on demand when saving. Anchored to the
# repository-root ``artifacts/`` directory so history lives in one place.
DEFAULT_EXPERIMENTS_DIR = artifacts_dir("experiments")

# Aggregate metric deltas persisted as a compact summary. None stays None.
_SUMMARY_METRIC_KEYS = (
    "total_tokens",
    "latency_seconds",
    "web_searches",
    "model_calls",
    "tool_calls",
    "subagent_calls",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_stamp(iso_timestamp: str) -> str:
    """Convert an ISO-8601 timestamp into a filesystem-safe compact stamp."""
    try:
        moment = datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return re.sub(r"[^0-9A-Za-z\-T]", "", iso_timestamp) or "unknown"
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def _safe_change_id(change_id: str) -> str:
    """Reduce an arbitrary change id to a safe filename slug."""
    slug = re.sub(r"[^0-9A-Za-z._-]+", "-", str(change_id).strip())
    slug = slug.strip("-._")
    return slug or "experiment"


def _summary_deltas(aggregate: dict[str, Any]) -> dict[str, float | None]:
    """Pull compact aggregate deltas, preserving unavailable metrics as null."""
    summary: dict[str, float | None] = {}
    for key in _SUMMARY_METRIC_KEYS:
        entry = aggregate.get(key)
        summary[key] = entry.get("delta") if isinstance(entry, dict) else None
    return summary


@dataclass
class ExperimentRecord:
    """Compact, serializable summary of one improvement experiment.

    Answers: what changed, why we tested it, the important deltas, whether
    regressions were found, and the decision. Deliberately excludes raw model
    responses, traces, and runtime objects.
    """

    change_id: str
    baseline_label: str
    candidate_label: str
    decision: str
    observed_failure: str | None = None
    hypothesis: str | None = None
    change_description: str | None = None
    quality_delta: float | None = None
    deltas: dict[str, float | None] = field(default_factory=dict)
    regressions: list[str] = field(default_factory=list)
    evidence: str | None = None
    recommendation_reason: str | None = None
    notes: str = ""
    timestamp: str = field(default_factory=_utc_now_iso)

    @classmethod
    def from_report(
        cls,
        report: ComparisonReport,
        *,
        change_id: str,
        observed_failure: str | None = None,
        hypothesis: str | None = None,
        change_description: str | None = None,
        notes: str = "",
        decision: str | None = None,
    ) -> "ExperimentRecord":
        """Build a compact record from a ``ComparisonReport``."""
        return cls(
            change_id=change_id,
            baseline_label=report.baseline_label,
            candidate_label=report.candidate_label,
            decision=decision or report.recommendation,
            observed_failure=observed_failure,
            hypothesis=hypothesis,
            change_description=change_description,
            quality_delta=report.quality_delta,
            deltas=_summary_deltas(report.aggregate),
            regressions=list(report.regressions),
            evidence=report.evidence,
            recommendation_reason=report.recommendation_reason,
            notes=notes,
        )

    def filename(self) -> str:
        """Safe per-experiment filename derived from timestamp + change id."""
        return f"{_timestamp_stamp(self.timestamp)}_{_safe_change_id(self.change_id)}.json"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentRecord":
        known = {f.name for f in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in known})


def save_experiment_record(
    record: ExperimentRecord,
    path: str | Path | None = None,
    *,
    directory: str | Path | None = None,
) -> Path:
    """Write one experiment record to disk as indented UTF-8 JSON.

    With ``path`` the record is written to that exact file. Otherwise it is
    written into ``directory`` (default ``artifacts/experiments/``) using a safe
    filename derived from the record's timestamp and change id. The target
    directory is created automatically.
    """
    if path is not None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        base = Path(directory) if directory is not None else DEFAULT_EXPERIMENTS_DIR
        base.mkdir(parents=True, exist_ok=True)
        target = base / record.filename()

    target.write_text(
        json.dumps(record.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target


def load_experiment_record(path: str | Path) -> ExperimentRecord:
    """Read a single experiment record from a JSON file."""
    target = Path(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExperimentLogError(
            f"Malformed experiment record JSON at {target}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ExperimentLogError(
            f"Experiment record at {target} is not a JSON object."
        )
    return ExperimentRecord.from_dict(data)


def list_experiment_records(
    directory: str | Path | None = None,
) -> list[ExperimentRecord]:
    """Load all experiment records from a directory, ordered by filename.

    Returns an empty list when the directory does not exist. Filenames are
    timestamp-prefixed, so filename order is chronological.
    """
    base = Path(directory) if directory is not None else DEFAULT_EXPERIMENTS_DIR
    if not base.is_dir():
        return []
    return [load_experiment_record(path) for path in sorted(base.glob("*.json"))]


def save_improvement_experiment(
    report: ComparisonReport,
    *,
    change_id: str,
    observed_failure: str | None = None,
    hypothesis: str | None = None,
    change_description: str | None = None,
    notes: str = "",
    directory: str | Path | None = None,
    path: str | Path | None = None,
) -> Path:
    """Convert a ``ComparisonReport`` to an ``ExperimentRecord`` and save it."""
    record = ExperimentRecord.from_report(
        report,
        change_id=change_id,
        observed_failure=observed_failure,
        hypothesis=hypothesis,
        change_description=change_description,
        notes=notes,
    )
    return save_experiment_record(record, path=path, directory=directory)
