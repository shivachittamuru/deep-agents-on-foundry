"""Repeatable P8D economics analysis over a set of runs.

Run this after exploring the guided notebook to reproduce the same offline
analysis quickly: it loads runs (or builds the built-in synthetic study), prints
the human-readable report, and explicitly saves a compact JSON record under
``artifacts/economics/``.

    python src/deep_agents_foundry/economics/run_agent_economics.py
"""

from __future__ import annotations

from deep_agents_foundry.economics import (
    analyze_agent_economics,
    load_or_build_runs,
    render_economics_report,
    save_economics_analysis,
)


def main() -> None:
    runs = load_or_build_runs()

    analysis = analyze_agent_economics(runs)

    print(render_economics_report(analysis))

    path = save_economics_analysis(
        analysis,
        analysis_id="architecture-study",
    )

    print(f"Saved economics analysis: {path}")


if __name__ == "__main__":
    main()
