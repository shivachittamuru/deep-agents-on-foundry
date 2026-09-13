---
title: Agent Economics Framework
description: Package overview and commands for running offline Research Deep Agent economics analysis
ms.date: 2026-09-13
ms.topic: how-to
---

## Purpose

The `economics` package is an offline analysis and control-plane capability for
the Research Deep Agent. Where the `improvement` package (P8C) answers "did this
change make the agent better?", the `economics` package (P8D) answers "was that
improvement worth the additional agentic work, cost, latency, and complexity?".

Use it to aggregate repeated runs by architecture and task complexity, compare
architectures with explicit metric deltas, place them on a value frontier,
inspect marginal returns, produce conservative routing observations, and save a
compact economics record.

The package is not part of the serving or request path. It runs only when an
engineer invokes it, it never modifies the production agent, and it consumes
outputs from the `improvement` package rather than redesigning them. It stays
interpretable on purpose: there is no single combined "economics score", missing
metrics remain unavailable instead of zero, and token counts are never silently
treated as dollars.

For the framework design, metrics, formulas, and broader rationale, see the
[Research Agent Economics Framework](../../../docs/Research_Agent_Economics_Framework.md).

## Package roles

* `__init__.py` exposes the supported public API
* `models.py` defines `EconomicsRun` and the summary, comparison, frontier,
  marginal-return, routing, and report records
* `metrics.py` holds small, transparent formulas (effective task cost, expected
  failure cost, expected net value, cost per successful task, and similar)
* `comparison.py` aggregates runs into per-architecture summaries, computes
  interpretable deltas, and analyzes marginal returns
* `frontier.py` computes the Pareto/value frontier and flags dominated
  architectures
* `reporting.py` orchestrates the full analysis, derives conservative routing
  observations, and renders the human-readable report
* `economics_log.py` explicitly saves and loads compact JSON economics records
* `adapters.py` converts `improvement` (P8C) outputs into `EconomicsRun` records
* `datasets.py` provides a deterministic sample study and a load-or-build helper

The execution flow is:

```text
EconomicsRun records (synthetic or converted from P8C)
  -> metrics
  -> per-architecture summaries and comparisons
  -> value frontier
  -> full analysis, routing, and human-readable report
  -> explicit JSON save
```

Detailed analysis remains available in memory through `EconomicsReport` and its
per-architecture summaries. Saved JSON deliberately excludes raw model responses,
complete traces, conversation history, and arbitrary runtime objects.

## Dependency direction

The dependency is one way. P8D consumes P8C outputs; P8C does not depend on P8D
and remains independently usable.

```text
improvement (P8C) outputs
  -> economics (P8D) analysis
```

Use `economics_runs_from_comparison_report(...)` or
`economics_runs_from_variant_result(...)` to turn existing improvement results
into `EconomicsRun` records without changing the `improvement` package.

## Included analysis script

The package includes
[`run_agent_economics.py`](run_agent_economics.py). It loads runs (or builds the
built-in synthetic study when no run data is present), runs the full analysis,
prints the report, and explicitly saves a compact JSON record under
`artifacts/economics/`.

`load_or_build_runs()` reads
`artifacts/economics/economics_runs.json` when it exists and otherwise returns
the deterministic sample study from `datasets.py`, so the script is repeatable
with no setup. Drop a JSON array of run objects at that path to analyze your own
data with the same script.

For a guided, offline walkthrough of how the modules connect, open
[`run_economics_analysis.ipynb`](run_economics_analysis.ipynb). It walks the full
pipeline one stage at a time on synthetic runs, so every cell returns instantly
without Azure calls, and it ends by saving and reloading an economics record.

## Prerequisites

Run commands from the repository root:

```powershell
Set-Location C:\Users\shchitt\Downloads\Projects\deep-agents-on-foundry
```

Install or synchronize the environment:

```powershell
uv sync --dev
```

The economics analysis is fully offline: it needs no Azure authentication, no
Foundry endpoint, and no network access. It operates on `EconomicsRun` records
you supply or on the built-in synthetic study.

## Run commands

### Run the analysis script

```powershell
uv run python src/deep_agents_foundry/economics/run_agent_economics.py
```

This prints the economics report and writes one JSON record to
`artifacts/economics/`.

### Analyze your own runs

Provide a JSON array of run objects whose keys match `EconomicsRun` fields, then
run the same script. Unknown or derived keys are ignored on load.

```powershell
New-Item -ItemType Directory -Force artifacts\economics | Out-Null
# Write your runs to artifacts\economics\economics_runs.json, then:
uv run python src/deep_agents_foundry/economics/run_agent_economics.py
```

### Open the guided notebook

```powershell
code src/deep_agents_foundry/economics/run_economics_analysis.ipynb
```

## Read the report

The report prints these sections:

* `DATA COVERAGE` lists run counts, architectures, complexities, and which
  classes of metric (cost, human, business) were available
* `SIMPLE`, `MEDIUM`, and `COMPLEX TASKS` show per-architecture quality, success,
  work, latency, and cost, with a preferred architecture when the evidence
  supports one
* `VALUE FRONTIER` lists the non-dominated architectures per complexity
* `DOMINATED` lists architectures another option beats on both quality and cost
* `MARGINAL RETURNS` notes observed diminishing returns and a candidate elbow
* `HUMAN ECONOMICS` and `BUSINESS VALUE` appear only when those inputs are
  supplied and are shown as unavailable otherwise
* `RECOMMENDED ROUTING` returns `PREFER` with an architecture or `INVESTIGATE`
  per complexity

Economics is downstream of quality: a lower operational cost is beneficial only
when quality and required behavior do not regress. The analysis is separated by
task complexity because the right architecture depends on task difficulty.

## Read saved economics history

Saving is explicit and occurs after analysis and reporting. By default, one
human-readable JSON file per analysis is written to `artifacts/economics/`.

List saved records:

```powershell
Get-ChildItem artifacts\economics\*.json |
  Sort-Object Name |
  Select-Object Name, Length, LastWriteTime
```

Read the newest record:

```powershell
$latest = Get-ChildItem artifacts\economics\*.json |
  Sort-Object Name -Descending |
  Select-Object -First 1

Get-Content $latest.FullName -Raw
```

Load and summarize all records through the public API:

```powershell
uv run python -c "from deep_agents_foundry.economics import list_economics_records; [print(r.timestamp, r.analysis_id, r.preferred_by_complexity) for r in list_economics_records()]"
```

## Direct API usage

Build `EconomicsRun` records directly, or convert them from an improvement
comparison, then run the same analysis pipeline:

```python
from deep_agents_foundry.economics import (
    analyze_agent_economics,
    economics_runs_from_comparison_report,
    render_economics_report,
    save_economics_analysis,
)

# Reuse existing P8C comparison output (P8D consumes P8C).
runs = economics_runs_from_comparison_report(comparison_report)

analysis = analyze_agent_economics(runs)

print(render_economics_report(analysis))

path = save_economics_analysis(
    analysis,
    analysis_id="architecture-study-01",
    notes="Baseline vs deeper orchestration across simple, medium, and complex tasks",
)

print(f"Saved economics analysis: {path}")
```
