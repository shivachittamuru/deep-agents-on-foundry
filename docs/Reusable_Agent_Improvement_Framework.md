# Reusable Agent Improvement Framework

A practical, repeatable process for improving a production research agent using **tracing, evaluation, controlled experiments, and regression detection**.

This framework is designed for teams that already have a working agent and want to answer a disciplined question:

> **“I changed my agent. Did it actually get better, how did its behavior change, and should I keep the change?”**

It is intentionally separate from the serving path. The framework is an **offline engineering control plane** used by developers and architects to evaluate changes over time.

---

## 1. Why a reusable improvement framework is necessary

Agent development is unusually easy to do badly.

A typical failure pattern looks like this:

```text
The agent feels weak
      ↓
Change the prompt
      ↓
Add another tool
      ↓
Add memory
      ↓
Change model
      ↓
Run a few examples
      ↓
“It seems better”
```

The problem is that multiple variables changed at once, there is no stable baseline, and there is no reliable way to explain why the new version is better or worse.

A reusable improvement framework replaces that with:

```text
Observe
  ↓
Classify failure
  ↓
Form hypothesis
  ↓
Design targeted evaluation
  ↓
Make one meaningful change
  ↓
Run baseline and candidate through the same harness
  ↓
Compare quality + trajectory + operational metrics
  ↓
Keep / Revert / Investigate
```

This turns agent improvement into an engineering discipline.

---

# 2. Core principle: Trace + Eval

The framework is built on a simple distinction.

## Trace answers:

```text
What happened?
```

A trace can reveal:

- how many model calls occurred
- which tools were called
- which searches were repeated
- whether a Skill was loaded
- whether memory was retrieved
- whether a subagent was invoked
- whether retries occurred
- how much context was used
- how long the run took

## Evaluation answers:

```text
Was it good?
```

Evaluation can reveal:

- correctness
- completeness
- source quality
- citation quality
- task success
- architecture clarity
- trade-off depth
- decision usefulness

Neither is sufficient by itself.

A run may produce a high-quality answer with excessive work:

```text
Quality: 5/5
Web searches: 12
Model calls: 9
Latency: 95 seconds
```

Or it may be operationally efficient but wrong:

```text
Quality: 2/5
Web searches: 1
Latency: 4 seconds
```

The correct unit of analysis is:

```text
Trajectory
+
Quality
+
Operational Cost
```

---

# 3. The reusable improvement loop

The full loop is:

```text
TRACE
  ↓
FAILURE TAXONOMY
  ↓
HYPOTHESIS
  ↓
TARGETED EVAL
  ↓
SMALLEST CHANGE
  ↓
BASELINE VS CANDIDATE
  ↓
REGRESSION CHECK
  ↓
KEEP / REVERT / INVESTIGATE
```

Each stage has a specific purpose.

---

# 4. Step 1 — Observe the current behavior

Before changing the agent, inspect the existing behavior.

Do not begin with:

> “I think the prompt needs improvement.”

Begin with evidence.

Examples:

```text
Trace observation:
The agent performed three nearly identical searches.

Trace observation:
The technology-research Skill was available but never loaded.

Trace observation:
A simple question triggered a subagent.

Trace observation:
The answer was correct, but citation quality was poor.

Trace observation:
The agent forgot a user preference that should have been remembered.

Trace observation:
Summarization removed an important constraint.
```

The purpose of observation is to identify a concrete symptom.

---

# 5. Step 2 — Classify the failure

Use a stable failure taxonomy.

A reusable taxonomy prevents every issue from becoming a vague “prompt problem.”

## 5.1 Retrieval failures

Examples:

- poor search query
- insufficient evidence
- weak source selection
- stale sources
- relevant source missed

## 5.2 Reasoning failures

Examples:

- evidence was available but interpreted incorrectly
- trade-offs were poorly analyzed
- contradictory evidence was not reconciled
- conclusion did not follow from evidence

## 5.3 Tool-use failures

Examples:

- wrong tool selected
- unnecessary tool call
- duplicate tool call
- too many searches
- tool result ignored

## 5.4 Context failures

Examples:

- important context missing
- irrelevant context dominates
- history too large
- summarization loses critical details
- repeated context increases cost without benefit

## 5.5 Memory failures

Examples:

- relevant memory not retrieved
- stale memory used
- wrong user memory retrieved
- transient fact incorrectly persisted
- one-off request incorrectly inferred as a permanent preference

## 5.6 Skill failures

Examples:

- wrong Skill selected
- relevant Skill not selected
- Skill procedure ignored
- too many Skills loaded

## 5.7 Subagent failures

Examples:

- unnecessary delegation
- wrong specialist
- duplicate specialist research
- parent sends too little context
- parent sends too much context
- parent synthesis is weak

## 5.8 Synthesis failures

Examples:

- good evidence, weak final answer
- unsupported conclusion
- missing trade-offs
- poor structure
- decision is not actionable

## 5.9 Economics failures

Examples:

- extra work produces little quality gain
- latency increases with no outcome improvement
- more searches but no additional useful evidence
- subagents increase token consumption without improving success

At this stage, economics is primarily a diagnosis label. Deeper economic analysis belongs in a dedicated Agent Economics framework.

---

# 6. Step 3 — Form an improvement hypothesis

Every change should correspond to a measurable hypothesis.

Bad:

```text
“Improve the system prompt.”
```

Good:

```text
Observed symptom:
Three nearly identical searches.

Failure category:
Tool-use failure.

Hypothesis:
The agent lacks a clear stopping condition for research.

Proposed change:
Tighten the search policy in the agent instructions.

Primary metric:
Average web-search count.

Guardrail metric:
Research quality score must not decrease.
```

Another example:

```text
Observed symptom:
Architecture answers omit state ownership.

Failure category:
Skill failure.

Hypothesis:
The technology-research Skill does not emphasize state boundaries strongly enough.

Proposed change:
Update the Skill checklist.

Primary metric:
Architecture completeness score.

Guardrail metric:
Token usage and latency should not increase materially.
```

A useful experiment record contains:

```text
Observed symptom
Failure category
Hypothesis
Proposed change
Primary metric
Guardrail metric
```

---

# 7. Step 4 — Use a compact evaluation dataset

Do not begin with hundreds of prompts.

A small, representative dataset is often more useful.

A strong initial dataset may contain 6–20 cases covering:

```text
Simple task
Medium research task
Complex research task
Tool-routing case
Negative tool-use case
Skill-routing case
Memory case
Subagent case
Long-context case
Regression cases
```

Example cases:

### Simple

```text
What are Microsoft Foundry Hosted Agents?
```

### Medium

```text
Explain Microsoft Foundry Hosted Agents architecture, state/session boundaries, and identity model.
```

### Complex

```text
Compare Microsoft Foundry Hosted Agents with a custom AKS-hosted LangGraph agent for enterprise workloads. Cover architecture, state ownership, identity, scaling, observability, reliability, portability, and economics.
```

### Negative tool-use case

```text
Explain the difference between a tool and middleware in one paragraph.
```

Expected behavior:

```text
No web search
No subagent
No unnecessary Skill
```

---

# 8. DEV and held-out evaluation sets

Do not optimize against every prompt you use to measure success.

Split the dataset conceptually into:

```text
DEV CASES
→ used frequently
→ diagnose
→ iterate
```

and:

```text
HELD-OUT CASES
→ used less often
→ confirm generalization
```

This helps prevent eval overfitting.

A useful workflow is:

```text
Change agent
   ↓
Run DEV set
   ↓
Improve until acceptable
   ↓
Run held-out set
   ↓
Confirm change generalizes
```

If performance improves on DEV but degrades on held-out cases, the correct recommendation is often:

```text
INVESTIGATE
```

not:

```text
KEEP
```

---

# 9. Stable runner, changing agent

The experimental harness should remain stable while the agent implementation changes.

Conceptually:

```text
Stable dataset
+
Stable runner
+
Stable evaluator
+
Stable judge
+
Changing agent
```

This is critical.

The framework should accept an already-built agent:

```python
baseline_agent = build_research_agent(...)
candidate_agent = build_research_agent(...)
```

Then use the same runner:

```python
report = await compare_agent_variants(
    baseline_agent=baseline_agent,
    candidate_agent=candidate_agent,
    dataset=dev_cases(),
    judge_model=judge_model,
)
```

The improvement framework should not own production-agent construction.

That keeps experimentation separate from runtime configuration.

---

# 10. What every run should capture

Each run should preserve both the raw result and useful normalized metrics.

Recommended fields:

```text
case_id
run_label
complexity
prompt
final_text
raw_result

latency_seconds

input_tokens
output_tokens
model_calls

web_searches
tool_calls
subagent_calls

trajectory_features
trajectory_summary

deterministic_results
rubric_results
```

Missing optional fields should remain explicitly unavailable.

Do not silently convert missing metrics to zero.

For example:

```text
subagent_calls = unknown
```

is different from:

```text
subagent_calls = 0
```

---

# 11. Deterministic evaluation first

Run cheap deterministic checks before using an LLM judge.

Examples:

```text
Answer is non-empty
Citation-like content exists
Required source is present
Search count is below budget
No subagent on simple task
Expected Skill is available
No user-memory leak
Correct thread/user isolation
```

Deterministic checks are useful because they are:

- cheap
- repeatable
- easy to debug
- stable over time

They should be used whenever success can be expressed objectively.

---

# 12. Rubric evaluation

Some qualities are difficult to encode deterministically.

Use rubric evaluation for dimensions such as:

```text
Correctness
Completeness
Source quality
Architecture clarity
Trade-off depth
Decision usefulness
```

Important practices:

1. Use the same judge for baseline and candidate.
2. Keep the rubric stable.
3. Hide architecture labels from the judge where possible.
4. Do not tell the judge which answer is “new” or “improved.”
5. Keep raw deterministic metrics alongside rubric scores.

Rubric evaluation should complement deterministic evaluation, not replace it.

---

# 13. Trajectory evaluation

Agent evaluation must examine the path, not only the answer.

A final response can be excellent while the trajectory is poor.

Trajectory dimensions include:

```text
Tool necessity
Tool selection
Search novelty
Delegation appropriateness
Context discipline
Retry discipline
Work efficiency
```

Examples:

```text
Simple question
→ should not invoke a subagent
```

```text
Technical architecture research
→ technology-research Skill may be appropriate
```

```text
Identity-heavy research
→ identity specialist may be appropriate
```

```text
Web research
→ repeated searches should add new evidence
```

The objective is not:

```text
fewest possible steps
```

The objective is:

```text
necessary + productive steps
```

---

# 14. Baseline vs candidate comparison

The framework should always compare two explicit variants.

```text
Baseline
= known-good current behavior

Candidate
= one meaningful experimental change
```

Examples of candidate changes:

```text
Prompt update
Skill update
Memory-policy update
Tool-policy update
New middleware
Subagent addition
Model change
Context-management change
```

Do not change several major components simultaneously unless the experiment explicitly intends to evaluate a whole architecture.

For normal improvement work:

> **Change one meaningful variable at a time.**

---

# 15. Compare interpretable deltas

Do not compress the entire experiment into one “agent score.”

Compare dimensions separately.

Examples:

```text
Δ Quality
Δ Citation Quality
Δ Task Success
Δ Input Tokens
Δ Output Tokens
Δ Latency
Δ Search Count
Δ Model Calls
Δ Tool Calls
Δ Subagent Calls
```

Why?

Because a candidate may:

```text
improve quality
but increase latency
```

or:

```text
reduce searches
but lose citation coverage
```

Those trade-offs should remain visible.

---

# 16. Regression detection

A candidate should be flagged if it introduces regressions.

Examples:

```text
A deterministic check passed before and fails now.
```

```text
Citation coverage disappears.
```

```text
Simple tasks begin invoking tools unnecessarily.
```

```text
Subagent calls increase but quality does not.
```

```text
Latency increases significantly with no useful improvement.
```

Regression thresholds should be explicit and configurable.

Do not hide them inside reporting logic.

---

# 17. KEEP / REVERT / INVESTIGATE

The framework should end with one of three conservative recommendations.

## KEEP

Use when evidence clearly shows improvement without unacceptable regressions.

Example:

```text
Quality: +0.5
Searches: -20%
Latency: -5%
No deterministic regressions
Held-out cases stable
```

## REVERT

Use when the candidate materially degrades behavior.

Example:

```text
Quality: -0.6
Citations lost
Simple tasks over-agent
Latency +30%
```

## INVESTIGATE

Use when evidence is mixed, incomplete, or contradictory.

Example:

```text
Quality improves on medium tasks
but degrades on held-out complex tasks.
```

Or:

```text
Tokens fall by 20%
but quality metrics are unavailable.
```

When evidence is insufficient, the framework should prefer:

```text
INVESTIGATE
```

rather than inventing certainty.

---

# 18. Human-readable reporting

A useful improvement report should explain the result, not merely dump metrics.

Example:

```text
Research Agent Improvement Report
=================================

Candidate vs Baseline

QUALITY
- Overall rubric quality: +0.42
- Source quality: improved
- 5/6 DEV cases improved or unchanged

TRAJECTORY
- Avg web searches: 3.2 → 2.4
- Avg model calls: 4.1 → 4.0
- Duplicate research reduced

PERFORMANCE
- Input tokens: -8.3%
- Latency: -4.1%

REGRESSIONS
- One held-out case lost citation completeness

OBSERVATIONS
✓ Medium/complex research improved
✓ Search efficiency improved
⚠ No meaningful improvement on simple tasks
⚠ One citation regression requires investigation

RECOMMENDATION
INVESTIGATE

Reason:
The candidate appears better overall, but the held-out citation regression should be resolved before promotion.
```

This is far more useful than:

```text
agent_score = 84.7
```

---

# 19. Feature-specific regression tests

Every important real failure should eventually become a regression case.

This is how the evaluation dataset gets smarter over time.

Examples:

## Memory

Observed bug:

```text
User B saw User A's preference.
```

Add regression:

```text
User isolation must always hold.
```

## Skills

Observed bug:

```text
Simple request loaded technology-research Skill.
```

Add regression:

```text
Simple non-research prompts should not trigger specialized research Skills.
```

## Subagents

Observed bug:

```text
Simple definition question delegated to architecture specialist.
```

Add regression:

```text
Simple tasks remain with parent agent.
```

## Summarization

Observed bug:

```text
Important user constraint disappeared after compaction.
```

Add regression:

```text
Critical constraint survives summarization.
```

Over time, the eval suite becomes institutional memory for the agent.

---

# 20. Avoid eval overfitting

A mature eval system can itself create problems.

The failure pattern:

```text
Optimize repeatedly against 10 prompts
   ↓
Agent becomes excellent on those prompts
   ↓
General behavior becomes worse
```

Mitigations:

- maintain held-out cases
- periodically refresh evaluation tasks
- inspect traces qualitatively
- incorporate real production-like failures
- avoid optimizing a single aggregate score
- use multiple task complexities

The eval suite should evolve with the agent.

---

# 21. Recommended development cadence

Use the framework at three levels.

## During development

Run a small DEV suite after meaningful changes.

```text
Fast feedback
Low cost
Frequent iteration
```

## Before merge / release

Run:

```text
DEV
+
Held-out
```

This validates generalization.

## Periodically

Add new regression cases discovered through:

```text
Traces
Customer scenarios
Production-like testing
New capabilities
Unexpected failures
```

---

# 22. Experiment log

Keep a lightweight log of meaningful experiments.

Suggested fields:

```text
timestamp
change_id
baseline
candidate
observed_failure
hypothesis
change_description
quality_delta
token_delta
latency_delta
search_delta
decision
notes
```

Do not build a database initially.

A simple JSON, CSV, or in-memory representation is sufficient.

The purpose is traceability:

> “Why did we change this part of the agent three months ago?”

---

# 23. What belongs in production vs the improvement framework

A clean boundary is essential.

## Production package

Reusable runtime/evaluation mechanics may include:

```text
telemetry.py
evaluation.py
agent.py
memory.py
skills.py
streaming.py
persistence.py
```

## Improvement framework

Offline experiment orchestration:

```text
improvement/
├── models.py
├── datasets.py
├── runner.py
├── diagnosis.py
├── comparison.py
└── reporting.py
```

The improvement framework should **not** be imported by the Hosted Agent request path.

Think of it as:

```text
Production Agent
= product

Improvement Framework
= engineering control plane
```

---

# 24. Suggested public API

A small public surface is preferable.

Conceptually:

```python
from deep_agents_foundry.improvement import (
    EvaluationCase,
    ImprovementHypothesis,
    core_research_dataset,
    dev_cases,
    held_out_cases,
    evaluate_agent_variant,
    compare_agent_variants,
    render_improvement_report,
)
```

The exact names can vary, but the API should make this workflow easy:

```python
baseline = build_research_agent(...)
candidate = build_research_agent(...)

report = await compare_agent_variants(
    baseline_agent=baseline,
    candidate_agent=candidate,
    dataset=dev_cases(),
    judge_model=judge,
)

print(render_improvement_report(report))
```

---

# 25. Recommended step-by-step workflow for engineers

Use this every time you make a meaningful change.

## Step 1 — Identify the observed failure

Example:

```text
Agent repeats searches.
```

## Step 2 — Classify it

```text
Tool-use failure.
```

## Step 3 — Form hypothesis

```text
Search stopping policy is too weak.
```

## Step 4 — Pick or add targeted eval

```text
Medium architecture research case.
```

## Step 5 — Freeze baseline

```text
Known-good current agent.
```

## Step 6 — Build candidate

```text
Same agent + search policy change.
```

## Step 7 — Run DEV comparison

Collect:

```text
quality
trajectory
tokens
latency
searches
```

## Step 8 — Inspect individual failures

Do not rely only on aggregate averages.

## Step 9 — Check regression signals

Especially:

```text
citations
tool use
simple-task behavior
quality thresholds
```

## Step 10 — Run held-out cases

Confirm generalization.

## Step 11 — Decide

```text
KEEP
REVERT
INVESTIGATE
```

## Step 12 — Record the experiment

Add the result to the experiment log.

---

# 26. Practical example

Suppose tracing shows:

```text
Baseline:
5 web searches
4.4 quality
38K tokens
42 sec latency
```

You change the search policy.

Candidate:

```text
3 web searches
4.5 quality
31K tokens
34 sec latency
```

The report may conclude:

```text
QUALITY
+0.1

TRAJECTORY
Searches: 5 → 3

PERFORMANCE
Tokens: -18%
Latency: -19%

REGRESSIONS
None detected

RECOMMENDATION
KEEP
```

Now consider another candidate:

```text
2 searches
3.9 quality
25K tokens
25 sec latency
```

It is cheaper and faster.

But quality fell materially.

Recommendation:

```text
REVERT
```

This demonstrates why:

```text
lower cost
≠
better agent
```

---

# 27. Relationship to Agent Economics

The improvement framework asks:

> **Did the candidate improve the agent?**

Agent Economics asks the next question:

> **Was that improvement worth the additional work or cost?**

The bridge is:

```text
Improvement Framework
   ↓
Δ Quality
Δ Task Success
Δ Tokens
Δ Latency
Δ Searches
Δ Tool Calls
Δ Subagent Calls
   ↓
Agent Economics
```

Do not prematurely combine these frameworks.

A good sequence is:

```text
First:
prove the change is better

Then:
decide whether the improvement is economically worthwhile
```

---

# 28. Key anti-patterns

Avoid these.

## Anti-pattern 1 — Random prompt tuning

```text
Change prompt
Run one example
Declare success
```

## Anti-pattern 2 — Multiple simultaneous changes

```text
new prompt
+ new model
+ memory
+ Skills
+ subagents
```

No causal understanding.

## Anti-pattern 3 — Only judging final answer

Ignores trajectory waste.

## Anti-pattern 4 — Only minimizing tokens

Can create cheap failures.

## Anti-pattern 5 — One magic agent score

Hides trade-offs.

## Anti-pattern 6 — No held-out cases

Encourages eval overfitting.

## Anti-pattern 7 — No regression cases

Previously solved failures return.

## Anti-pattern 8 — Improvement framework in serving path

Offline experimentation should stay separate from production request handling.

---

# 29. Final mental model

The framework can be summarized as:

```text
                    ┌─────────────┐
                    │   TRACE     │
                    └──────┬──────┘
                           ↓
                 What actually happened?
                           ↓
                ┌───────────────────┐
                │ FAILURE TAXONOMY  │
                └────────┬──────────┘
                         ↓
                 Why might it happen?
                         ↓
                  ┌────────────┐
                  │ HYPOTHESIS │
                  └─────┬──────┘
                        ↓
               What should improve?
                        ↓
               ┌─────────────────┐
               │ TARGETED EVAL   │
               └────────┬────────┘
                        ↓
                Make smallest change
                        ↓
          ┌────────────────────────────┐
          │ BASELINE VS CANDIDATE RUN │
          └──────────────┬─────────────┘
                         ↓
         Quality + Trajectory + Performance
                         ↓
              Regression detection
                         ↓
             ┌─────────────────────┐
             │ KEEP / REVERT /     │
             │ INVESTIGATE         │
             └─────────────────────┘
```

---

# 30. The principle to remember

> **Do not ask whether the new agent feels better.**
>
> Ask:
>
> **What failure did we observe, what change did we make, what evidence shows that it improved, what regressions appeared, and should we keep it?**

That is the foundation of continuous, evidence-driven agent improvement.
