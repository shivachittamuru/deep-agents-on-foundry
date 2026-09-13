"""Lightweight JSON persistence for P8D economics analyses (P8D).

Persists a compact, human-readable interpretation of one economics analysis so
results survive process exit and can be reviewed or trend-analyzed later. One
JSON file per analysis; no database, no raw traces, no runtime objects.

Only the compact economic interpretation is stored: architecture summaries,
frontier/dominated architectures, routing recommendations, marginal-return
observations, and optional human/business roll-ups. Raw model outputs, full
trajectories, and secrets are never persisted. Missing metrics stay ``null`` —
they are never coerced to zero.

Saving is always explicit. ``analyze_agent_economics``,
``compare_architectures``, and ``render_economics_report`` never write files; the
caller decides when an analysis is worth preserving.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..errors import EconomicsLogError
from ..paths import artifacts_dir
from .models import PREFER, ArchitectureSummary, EconomicsReport

# Default on-disk location; created on demand when saving. Anchored to the
# repository-root ``artifacts/`` directory so history lives in one place.
DEFAULT_ECONOMICS_DIR = artifacts_dir("economics")


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


def _safe_analysis_id(analysis_id: str) -> str:
    """Reduce an arbitrary analysis id to a safe filename slug."""
    slug = re.sub(r"[^0-9A-Za-z._-]+", "-", str(analysis_id).strip())
    slug = slug.strip("-._")
    return slug or "analysis"


def _human_economics(summaries: list[ArchitectureSummary]) -> list[dict[str, Any]]:
    """Compact human-economics roll-up for architectures that reported it."""
    return [
        {
            "architecture": summary.architecture,
            "complexity": summary.complexity,
            "avg_human_cost": summary.avg_human_cost,
            "avg_effective_task_cost": summary.avg_effective_task_cost,
            "effective_cost_per_successful_task": (
                summary.effective_cost_per_successful_task
            ),
        }
        for summary in summaries
        if summary.avg_human_cost is not None
    ]


def _business_value(summaries: list[ArchitectureSummary]) -> list[dict[str, Any]]:
    """Compact business-value roll-up for architectures that reported it."""
    return [
        {
            "architecture": summary.architecture,
            "complexity": summary.complexity,
            "avg_expected_net_value": summary.avg_expected_net_value,
        }
        for summary in summaries
        if summary.avg_expected_net_value is not None
    ]


@dataclass
class EconomicsRecord:
    """Compact, serializable summary of one economics analysis.

    Holds only primitive-serializable values (numbers, strings, booleans, ``None``,
    and containers of those). Unavailable metrics remain ``None``; genuine zeros
    are preserved as zero. Deliberately excludes raw responses, traces, and
    runtime objects.
    """

    analysis_id: str
    total_runs: int = 0
    architectures: list[str] = field(default_factory=list)
    complexities: list[str] = field(default_factory=list)
    cost_available: bool = False
    human_economics_available: bool = False
    business_value_available: bool = False
    preferred_by_complexity: dict[str, str | None] = field(default_factory=dict)
    routing: list[dict[str, Any]] = field(default_factory=list)
    frontier_by_complexity: dict[str, list[str]] = field(default_factory=dict)
    dominated_by_complexity: dict[str, list[str]] = field(default_factory=dict)
    summaries: list[dict[str, Any]] = field(default_factory=list)
    marginal_returns: list[dict[str, Any]] = field(default_factory=list)
    human_economics: list[dict[str, Any]] = field(default_factory=list)
    business_value: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""
    timestamp: str = field(default_factory=_utc_now_iso)

    @classmethod
    def from_report(
        cls,
        report: EconomicsReport,
        *,
        analysis_id: str,
        notes: str = "",
    ) -> "EconomicsRecord":
        """Build a compact record from an :class:`EconomicsReport`."""
        preferred = {
            rec.complexity: rec.architecture
            for rec in report.routing
            if rec.state == PREFER
        }
        frontier = {
            complexity: list(result.frontier)
            for complexity, result in report.frontier_by_complexity.items()
        }
        dominated = {
            complexity: list(result.dominated)
            for complexity, result in report.frontier_by_complexity.items()
        }
        marginal = [
            {
                "work_metric": analysis.work_metric,
                "complexity": analysis.complexity,
                "candidate_elbow": analysis.candidate_elbow,
                "observations": list(analysis.observations),
            }
            for analysis in report.marginal_returns
        ]

        return cls(
            analysis_id=analysis_id,
            total_runs=report.total_runs,
            architectures=list(report.architectures),
            complexities=list(report.complexities),
            cost_available=report.cost_available,
            human_economics_available=report.human_economics_available,
            business_value_available=report.business_value_available,
            preferred_by_complexity=preferred,
            routing=[rec.to_dict() for rec in report.routing],
            frontier_by_complexity=frontier,
            dominated_by_complexity=dominated,
            summaries=[summary.to_dict() for summary in report.summaries],
            marginal_returns=marginal,
            human_economics=(
                _human_economics(report.summaries)
                if report.human_economics_available
                else []
            ),
            business_value=(
                _business_value(report.summaries)
                if report.business_value_available
                else []
            ),
            notes=notes,
        )

    def filename(self) -> str:
        """Safe per-analysis filename derived from timestamp + analysis id."""
        return f"{_timestamp_stamp(self.timestamp)}_{_safe_analysis_id(self.analysis_id)}.json"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EconomicsRecord":
        known = {f.name for f in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in known})


def save_economics_record(
    record: EconomicsRecord,
    path: str | Path | None = None,
    *,
    directory: str | Path | None = None,
) -> Path:
    """Write one economics record to disk as indented UTF-8 JSON.

    With ``path`` the record is written to that exact file. Otherwise it is
    written into ``directory`` (default ``artifacts/economics/``) using a safe
    filename derived from the record's timestamp and analysis id. The target
    directory is created automatically.
    """
    if path is not None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        base = Path(directory) if directory is not None else DEFAULT_ECONOMICS_DIR
        base.mkdir(parents=True, exist_ok=True)
        target = base / record.filename()

    target.write_text(
        json.dumps(record.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target


def load_economics_record(path: str | Path) -> EconomicsRecord:
    """Read a single economics record from a JSON file."""
    target = Path(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EconomicsLogError(
            f"Malformed economics record JSON at {target}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise EconomicsLogError(
            f"Economics record at {target} is not a JSON object."
        )
    return EconomicsRecord.from_dict(data)


def list_economics_records(
    directory: str | Path | None = None,
) -> list[EconomicsRecord]:
    """Load all economics records from a directory, ordered by filename.

    Returns an empty list when the directory does not exist. Filenames are
    timestamp-prefixed, so filename order is chronological.
    """
    base = Path(directory) if directory is not None else DEFAULT_ECONOMICS_DIR
    if not base.is_dir():
        return []
    return [load_economics_record(path) for path in sorted(base.glob("*.json"))]


def save_economics_analysis(
    report: EconomicsReport,
    *,
    analysis_id: str,
    notes: str | None = None,
    directory: str | Path | None = None,
    path: str | Path | None = None,
) -> Path:
    """Convert an :class:`EconomicsReport` to a record and save it explicitly."""
    record = EconomicsRecord.from_report(
        report, analysis_id=analysis_id, notes=notes or ""
    )
    return save_economics_record(record, path=path, directory=directory)
