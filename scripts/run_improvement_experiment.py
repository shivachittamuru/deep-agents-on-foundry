"""Run an offline P8C baseline-vs-candidate Skills experiment.

The baseline uses the standard Research Deep Agent. The candidate enables the
repository Skills catalog. Results are printed and a compact experiment summary
is explicitly saved under artifacts/experiments by default.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from deep_agents_foundry import build_model, build_research_agent
from deep_agents_foundry.improvement import (
    compare_agent_variants,
    core_research_dataset,
    dev_cases,
    held_out_cases,
    render_improvement_report,
    save_improvement_experiment,
)

_TARGETED_DEV_CASE_IDS = {
    "simple_definition",
    "medium_architecture",
    "tool_negative",
    "skill_routing",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare the Research Deep Agent with Skills disabled vs enabled."
    )
    parser.add_argument(
        "--suite",
        choices=("targeted-dev", "dev", "held-out", "core"),
        default="targeted-dev",
        help="Dataset subset to run (default: targeted-dev).",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="case_ids",
        help="Run only this case ID; repeat to select multiple cases.",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip rubric judging and use deterministic/trajectory evidence only.",
    )
    parser.add_argument(
        "--change-id",
        default="technology-skill-v2",
        help="Identifier used in the persisted experiment filename and record.",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        help="Save directory (default: artifacts/experiments).",
    )
    parser.add_argument("--notes", default="", help="Optional experiment notes.")
    return parser.parse_args()


def _select_dataset(suite: str, case_ids: list[str] | None):
    if suite == "targeted-dev":
        dataset = [
            case for case in dev_cases() if case.id in _TARGETED_DEV_CASE_IDS
        ]
    elif suite == "dev":
        dataset = dev_cases()
    elif suite == "held-out":
        dataset = held_out_cases()
    else:
        dataset = core_research_dataset()

    if case_ids:
        requested = set(case_ids)
        selected = [case for case in dataset if case.id in requested]
        missing = requested - {case.id for case in selected}
        if missing:
            available = ", ".join(case.id for case in dataset)
            raise ValueError(
                f"Unknown case(s) for suite {suite!r}: {', '.join(sorted(missing))}. "
                f"Available: {available}"
            )
        dataset = selected

    return dataset


async def _run(args: argparse.Namespace) -> Path:
    dataset = _select_dataset(args.suite, args.case_ids)

    baseline_agent = build_research_agent()
    candidate_agent = build_research_agent(skills=["."])
    judge_model = None if args.no_judge else build_model()

    report = await compare_agent_variants(
        baseline_agent=baseline_agent,
        candidate_agent=candidate_agent,
        dataset=dataset,
        judge_model=judge_model,
        baseline_label="skills-off",
        candidate_label="skills-on",
    )

    print(render_improvement_report(report))
    print("\nPER-CASE RESULTS")
    for case in report.case_comparisons:
        print(f"\n{case.case_id}")
        print(f"  quality delta: {case.quality_delta}")
        print(f"  metric deltas: {case.deltas}")
        print(f"  improvements: {case.improvements or ['none']}")
        print(f"  regressions: {case.regressions or ['none']}")

    return save_improvement_experiment(
        report,
        change_id=args.change_id,
        observed_failure=(
            "Research tasks may search inefficiently or miss procedural guidance"
        ),
        hypothesis="Skills reduce redundant work without lowering answer quality",
        change_description=(
            "Enabled the repository Skills catalog for the candidate agent"
        ),
        notes=args.notes
        or f"{args.suite} run; baseline skills disabled, candidate skills enabled.",
        directory=args.output_directory,
    )


def main() -> None:
    args = _parse_args()
    path = asyncio.run(_run(args))
    print(f"\nSaved experiment: {path.resolve()}")


if __name__ == "__main__":
    main()
