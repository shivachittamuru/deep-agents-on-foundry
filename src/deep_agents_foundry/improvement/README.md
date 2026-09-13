---
title: Reusable Agent Improvement Framework
description: Package overview and commands for running offline Research Deep Agent improvement experiments
ms.date: 2026-09-12
ms.topic: how-to
---

## Purpose

The `improvement` package is an offline engineering and evaluation control plane
for the Research Deep Agent. Use it to run the same cases against a baseline and
a candidate, compare quality and behavior, inspect regressions, make a
conservative `KEEP`, `REVERT`, or `INVESTIGATE` decision, and save a compact
experiment record.

The package is not part of the serving or request path. It does not construct or
modify production agents automatically. An engineer explicitly builds both
agents and starts each experiment.

For the framework design, evaluation methodology, and broader rationale, see the
[Reusable Agent Improvement Framework](../../../docs/Reusable_Agent_Improvement_Framework.md).

## Package roles

* `__init__.py` exposes the supported public API
* `models.py` defines evaluation, run, comparison, and report records
* `datasets.py` provides the compact core, DEV, and HELD-OUT datasets
* `runner.py` invokes an existing agent and collects results, usage, trajectory,
  deterministic checks, and optional rubric scores
* `comparison.py` calculates per-case and aggregate deltas, detects regressions,
  and produces a conservative recommendation
* `reporting.py` renders the structured comparison as readable text
* `diagnosis.py` defines the failure taxonomy and improvement-hypothesis model
* `experiment_log.py` explicitly saves and loads compact JSON experiment records

The execution flow is:

```text
Dataset
  -> stable runner
  -> existing evaluation helpers
  -> baseline/candidate comparison
  -> human-readable report
  -> explicit JSON save
```

Detailed run data remains available in memory through `ComparisonReport` and its
per-case records. Saved JSON deliberately excludes raw model responses, complete
traces, conversation history, and arbitrary runtime objects.

## Included experiment runner

The repository includes
[`scripts/run_improvement_experiment.py`](../../../scripts/run_improvement_experiment.py).
It compares:

* Baseline: standard Research Deep Agent with Skills disabled
* Candidate: the same Research Deep Agent with the repository Skills catalog
  enabled
* Judge: an explicit Foundry model shared by both variants, unless `--no-judge`
  is supplied

The candidate uses `build_research_agent(skills=["."])`. The `"."` value is a
skill source inside the filesystem backend. The backend root resolves to the
repository's absolute `skills/` directory, so running the script from `scripts/`
does not redirect skill discovery to `scripts/`.

For a guided, offline walkthrough of how the modules connect, open
[`run_improvement_experiment.ipynb`](run_improvement_experiment.ipynb). It runs the
full baseline-vs-candidate pipeline with deterministic fake agents, so every cell
returns instantly without Azure calls, and it ends by showing how to run the real
experiment.

## Prerequisites

Run commands from the repository root:

```powershell
Set-Location C:\Users\shchitt\Downloads\Projects\deep-agents-on-foundry
```

Install or synchronize the environment:

```powershell
uv sync --dev
```

Authenticate for `DefaultAzureCredential`:

```powershell
az login
```

Set the required Foundry values in `.env` or the current shell:

```powershell
$env:AZURE_AI_PROJECT_ENDPOINT = "https://<your-project-endpoint>"
$env:AZURE_AI_MODEL_DEPLOYMENT_NAME = "<your-model-deployment>"
```

Inspect the available runner options without invoking Azure:

```powershell
uv run python scripts/run_improvement_experiment.py --help
```

## Run commands

### Smoke test one case

Use one case to confirm authentication and agent invocation before spending quota
on a suite:

```powershell
uv run python scripts/run_improvement_experiment.py `
  --case skill_routing `
  --change-id technology-skill-v2-smoke
```

### Run the targeted DEV suite

The default targeted suite covers simple research, architecture research,
negative tool use, and skill routing. It excludes memory- and subagent-specific
cases because this experiment changes only Skills.

```powershell
uv run python scripts/run_improvement_experiment.py `
  --suite targeted-dev `
  --change-id technology-skill-v2
```

The suite is the default, so the equivalent shorter command is:

```powershell
uv run python scripts/run_improvement_experiment.py `
  --change-id technology-skill-v2
```

### Run without a rubric judge

This uses deterministic and trajectory evidence only. Missing rubric quality is
reported as unavailable rather than zero.

```powershell
uv run python scripts/run_improvement_experiment.py `
  --suite targeted-dev `
  --no-judge `
  --change-id technology-skill-v2-no-judge
```

### Run selected DEV cases

Repeat `--case` to select multiple cases from the chosen suite:

```powershell
uv run python scripts/run_improvement_experiment.py `
  --suite dev `
  --case medium_architecture `
  --case skill_routing `
  --change-id technology-skill-v2-focused
```

### Run held-out confirmation

Use HELD-OUT after examining and iterating on DEV. The built-in held-out set also
contains a subagent-specific case; interpret that case only when both variants
have the required subagent capability.

```powershell
uv run python scripts/run_improvement_experiment.py `
  --suite held-out `
  --change-id technology-skill-v2-held-out
```

### Run the complete core dataset

The core dataset includes memory- and subagent-sensitive cases. Use it only when
both variants are configured with the required Store, context, and subagents.

```powershell
uv run python scripts/run_improvement_experiment.py `
  --suite core `
  --change-id full-agent-change-v1
```

### Choose another output directory

```powershell
uv run python scripts/run_improvement_experiment.py `
  --suite targeted-dev `
  --change-id technology-skill-v2 `
  --output-directory C:\temp\agent-experiments `
  --notes "First repeatability run"
```

## Read the report

The script prints a summary with these sections:

* `QUALITY` shows the average rubric-quality delta when a judge is enabled
* `TRAJECTORY` shows changes in searches, model calls, tools, and delegation
* `PERFORMANCE` shows token and latency changes when available
* `REGRESSIONS` identifies checks or quality dimensions that worsened
* `OBSERVATIONS` summarizes notable case and aggregate changes
* `RECOMMENDATION` returns `KEEP`, `REVERT`, or `INVESTIGATE` with a reason

The script then prints per-case quality and metric deltas. A negative operational
delta often means less work, but it is beneficial only when quality and required
behavior do not regress.

## Read saved experiment history

Saving is explicit and occurs after comparison and reporting. By default, one
human-readable JSON file per experiment is written to
`artifacts/experiments/`.

List saved records:

```powershell
Get-ChildItem artifacts\experiments\*.json |
  Sort-Object Name |
  Select-Object Name, Length, LastWriteTime
```

Read the newest record:

```powershell
$latest = Get-ChildItem artifacts\experiments\*.json |
  Sort-Object Name -Descending |
  Select-Object -First 1

Get-Content $latest.FullName -Raw
```

Load and summarize all records through the public API:

```powershell
uv run python -c "from deep_agents_foundry.improvement import list_experiment_records; [print(r.timestamp, r.change_id, r.decision, r.quality_delta) for r in list_experiment_records()]"
```

## Trend analysis over accumulated history

A single experiment answers whether one change helped. Accumulated experiment
records answer larger questions: whether quality trends upward over many changes,
which failure categories recur, and where regressions concentrate. Two supporting
files demonstrate that longer view.

* [`synthetic_experiment_logs.json`](synthetic_experiment_logs.json)
  is a labeled synthetic experiment history. It provides a realistic spread of
  decisions, failure categories, splits, and complexities so trend analysis can
  be taught and tested without running live experiments or exposing real results.
  It is demonstration data only and is not read by the framework at runtime.
* [`trend_analysis.ipynb`](trend_analysis.ipynb)
  is an exploratory, read-only notebook that loads the synthetic history into a
  DataFrame and shows how experiment logs become an audit trail, then trend
  evidence, then a map of recurring failure patterns, and finally a source of
  candidate regression cases. It inspects data quality, plots quality, token,
  latency, and search trends over time, analyzes decisions, failure categories,
  task complexity, and DEV versus held-out behavior, and proposes candidate
  regression cases for human review. It never modifies the framework, the
  production agent, or `datasets.py`.

Promotion of a recurring failure into a permanent evaluation case stays
deliberate: the notebook only surfaces suggestions, and an engineer decides what
to add through the normal review process.

Open the notebook to run it:

```powershell
code src/deep_agents_foundry/improvement/trend_analysis.ipynb
```

## Direct API usage

For a different candidate change, build both agents explicitly and use the same
comparison pipeline:

```python
from deep_agents_foundry.improvement import (
    compare_agent_variants,
    dev_cases,
    render_improvement_report,
    save_improvement_experiment,
)

report = await compare_agent_variants(
    baseline_agent=baseline_agent,
    candidate_agent=candidate_agent,
    dataset=dev_cases(),
    judge_model=judge_model,
    baseline_label="current",
    candidate_label="proposed-change",
)

print(render_improvement_report(report))

path = save_improvement_experiment(
    report,
    change_id="proposed-change-v1",
    hypothesis="The change improves quality without increasing unnecessary work",
    change_description="Describe the candidate configuration change",
)

print(f"Saved experiment: {path}")
```
