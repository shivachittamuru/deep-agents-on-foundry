# Agent Economics: End-to-End Framework

A practical framework for understanding, measuring, and optimizing the economics of AI agents from **tokens → agentic work → information gain → quality → task outcome → business value**.

This document is designed for architects, engineers, product leaders, and technical decision-makers building real-world agentic systems. It focuses on the full economic chain rather than treating token consumption as the final answer.

---

# 1. Why Agent Economics Matters

Traditional software systems are usually optimized around:

```text
latency
throughput
infrastructure cost
availability
```

Agentic systems introduce a new class of runtime behavior:

```text
multiple model calls
tool invocations
searches
retrieval
memory
subagents
summarization
planning
retries
verification
human review
```

This means a single user request may trigger a variable amount of work.

Two requests that look similar to the user may cost very different amounts internally.

Example:

```text
Request A:
1 model call
0 searches
5,000 tokens
4 seconds
```

```text
Request B:
5 model calls
4 searches
1 subagent
42,000 tokens
38 seconds
```

Raw token cost tells only part of the story.

The important question is not:

> How many tokens did the agent consume?

The better question is:

> What useful outcome did that work produce, and was the outcome worth the cost?

---

# 2. The Core Token-to-Value Ladder

The central Agent Economics framework is:

```text
TOKENS
  ↓
AGENTIC WORK
  ↓
INFORMATION GAIN
  ↓
QUALITY GAIN
  ↓
TASK OUTCOME
  ↓
BUSINESS VALUE
```

Each layer answers a different question.

| Layer | Core question |
|---|---|
| Tokens | What inference did we consume? |
| Agentic Work | What actions did the system perform? |
| Information Gain | What useful new evidence did those actions uncover? |
| Quality Gain | Did the output improve? |
| Task Outcome | Did the user/task succeed? |
| Business Value | What was successful completion worth? |

The biggest mistake in tokenomics is stopping at the first layer.

---

# 3. Token Economics vs Agent Economics

## Token Economics

Token economics asks:

```text
How much inference did we consume?
```

Typical measures:

```text
input tokens
output tokens
cached tokens
model calls
model cost
```

Token economics is necessary, but incomplete.

## Agent Economics

Agent economics asks:

```text
What useful work did those tokens fund?
```

An agent may use tokens to:

```text
plan
search
retrieve
compare
verify
delegate
summarize
retry
reason
synthesize
```

Two runs can consume the same number of tokens while producing radically different amounts of useful work.

That is why:

```text
token consumption
≠
productive work
```

---

# 4. A Four-Layer Economic View

A useful leadership-level abstraction is:

```text
TOKEN ECONOMICS
How much inference did we buy?
        ↓

AGENT ECONOMICS
What useful work did those tokens fund?
        ↓

TASK ECONOMICS
Did that work solve the task?
        ↓

BUSINESS ECONOMICS
What was successful task completion worth?
```

This is one of the most useful mental models for explaining agent economics to stakeholders.

---

# 5. Layer 1 — Inference Economics

Start with the easiest signals to measure.

For every run, capture:

```text
input_tokens
output_tokens
cached_tokens
model_calls
latency
```

A simple model-cost estimate:

```text
Model Cost
=
Input Tokens × Input Price
+
Output Tokens × Output Price
```

For agents, total run cost may also include:

```text
search cost
retrieval cost
embedding cost
tool/API cost
subagent calls
storage
compute
networking
```

A broader approximation is:

```text
Total Agent Cost
=
Model Cost
+ Tool Cost
+ Retrieval Cost
+ Infrastructure Cost
```

Important:

> Cost is the denominator of economics, not the objective by itself.

---

# 6. Layer 2 — Agentic Work

Tokens tell us how much computation happened.

They do not tell us what the system did.

Measure agentic work explicitly:

```text
model calls
web searches
tool calls
retrieval calls
memory reads
memory writes
skills loaded
subagent calls
summarizations
retries
planning steps
verification steps
```

This is essential because a 30K-token run could represent:

```text
productive multi-source research
```

or:

```text
repeated context + redundant retries
```

Same token count. Very different economics.

---

# 7. Productive Work vs Waste

A critical distinction is:

```text
activity
≠
progress
```

Example:

```text
Search 1 → useful
Search 2 → useful
Search 3 → duplicate
Search 4 → duplicate
Search 5 → stale source
Search 6 → useful
```

Six searches occurred.

Only three contributed meaningful evidence.

This gives us the concept of:

```text
productive work
vs
waste work
```

Agent Economics should optimize:

```text
waste ↓
```

not blindly:

```text
tokens ↓
```

---

# 8. Agentic Waste Taxonomy

A reusable waste taxonomy:

## 8.1 Repeated Context

The same information is passed into model calls repeatedly without adding value.

Examples:

```text
large conversation history
repeated tool outputs
always-loaded procedural instructions
```

## 8.2 Redundant Search

Different search calls return substantially the same information.

## 8.3 Unnecessary Tool Calls

The agent invokes tools when internal reasoning would have been sufficient.

## 8.4 Unnecessary Subagents

The parent delegates work that could have been handled directly.

## 8.5 Failed Retries

Repeated retries occur without changing strategy.

## 8.6 Wrong Tool Selection

The agent chooses a more expensive or less suitable capability.

## 8.7 Irrelevant Memory Retrieval

Long-term memory is injected when it does not matter.

## 8.8 Irrelevant Skill Loading

Procedural context is loaded unnecessarily.

## 8.9 Excessive Summarization

The system pays to summarize context that did not need compaction.

## 8.10 Re-Research Caused by Lost Context

The agent repeats work because useful information was forgotten, truncated, or summarized poorly.

---

# 9. Layer 3 — Information Gain

Agentic work is valuable only when it produces new useful information.

For practical systems, we can classify evidence-producing actions as:

```text
novel + useful
novel but irrelevant
duplicate
incorrect / noisy
```

Example:

```text
Search 1
→ official architecture documentation
→ novel + useful

Search 2
→ managed identity documentation
→ novel + useful

Search 3
→ same architecture content
→ duplicate

Search 4
→ outdated blog
→ noisy
```

This introduces:

```text
Information Gain Efficiency
=
Useful Evidence Discoveries
───────────────────────────
Agentic Actions
```

This does not need to be mathematically perfect.

Even a simple classification provides enormous insight into wasted agentic work.

---

# 10. Information Gain vs Search Count

Consider:

```text
Agent A:
3 searches
3 useful discoveries
```

```text
Agent B:
10 searches
4 useful discoveries
```

Then:

```text
Agent A efficiency = 3 / 3 = 1.00
Agent B efficiency = 4 / 10 = 0.40
```

Agent B discovered slightly more information, but required far more work.

The economic question is:

> Was that extra information worth the additional cost?

---

# 11. Layer 4 — Quality Gain

The next question is:

> Did the extra information improve the final output?

Quality dimensions depend on the agent.

For a research agent:

```text
correctness
completeness
source quality
citation quality
architecture clarity
trade-off depth
decision usefulness
```

Example:

```text
Baseline quality = 4.0
Candidate quality = 4.6
```

So:

```text
ΔQuality = +0.6
```

But quality cannot be considered alone.

Also measure:

```text
ΔTokens
ΔLatency
ΔSearches
ΔTool Calls
ΔSubagent Calls
```

This exposes the trade-off.

---

# 12. Do Not Collapse Everything Into One Ratio Too Early

A tempting metric is:

```text
quality gain per token
```

This can be useful, but it can also mislead.

Example:

```text
Agent A:
+0.2 quality
+2K tokens
```

```text
Agent B:
+1.0 quality
+20K tokens
```

A simple ratio may favor Agent A.

But suppose task success requires:

```text
quality ≥ 4.5
```

If:

```text
Agent A = 4.2
Agent B = 5.0
```

then:

```text
Agent A = failure
Agent B = success
```

The threshold matters more than the ratio.

So initially keep:

```text
quality
tokens
latency
tool cost
task success
```

separate.

---

# 13. Layer 5 — Task Outcome

Quality scores are proxies.

The user ultimately wants something done.

Examples:

```text
Research agent
→ decision-ready research

Coding agent
→ code passes tests

Support agent
→ issue resolved

RAG agent
→ correct grounded answer

Sales agent
→ qualified opportunity created

Workflow agent
→ process completed without escalation
```

Define success explicitly.

For a research agent:

```text
quality threshold reached
required dimensions covered
citations grounded
no critical error
human accepts result
minimal rework required
```

---

# 14. Quality Thresholds Change Economics

Suppose:

```text
Baseline
quality = 3.8
cost = $0.08
```

```text
Candidate
quality = 4.7
cost = $0.21
```

Required threshold:

```text
quality ≥ 4.5
```

Then:

```text
Baseline = failure
Candidate = success
```

The cheaper system is not economically better.

A more useful metric is:

```text
Cost per Successful Task
=
Total Cost
──────────
Successful Tasks
```

---

# 15. Success Rate

For repeated workloads:

```text
Success Rate
=
Successful Tasks
────────────────
Total Tasks
```

Agent architectures should be compared using:

```text
cost per successful task
```

rather than only:

```text
cost per request
```

This is especially important for high-value or high-risk workflows.

---

# 16. Human Review and Rework

Human effort often dominates model cost.

Example:

```text
Agent A
inference = $0.05
human editing = 15 minutes
```

```text
Agent B
inference = $0.40
human editing = 1 minute
```

If loaded labor cost is:

```text
$100/hour
```

then:

```text
Agent A human cost = $25
Total ≈ $25.05
```

```text
Agent B human cost ≈ $1.67
Total ≈ $2.07
```

The “more expensive” model is dramatically cheaper economically.

---

# 17. Effective Task Cost

A stronger metric is:

```text
Effective Task Cost
=
Agent Cost
+
Human Review Cost
+
Human Rework Cost
+
Expected Failure Cost
```

This is much closer to what the business actually experiences.

---

# 18. Reliability and Failure Cost

Suppose:

```text
Cheap agent:
90% success
$0.10/run
```

```text
Expensive agent:
99% success
$0.50/run
```

Failure cost:

```text
$100
```

Cheap architecture:

```text
Expected failure cost
= 10% × $100
= $10
```

Total:

```text
≈ $10.10
```

Expensive architecture:

```text
Expected failure cost
= 1% × $100
= $1
```

Total:

```text
≈ $1.50
```

The 5× more expensive inference system is economically cheaper.

---

# 19. Layer 6 — Business Value

Now ask:

> What is successful completion worth?

Examples:

```text
30 minutes of developer time saved
2 hours of analyst research avoided
ticket resolved without escalation
proposal delivered a day faster
manual workflow step eliminated
risk of expensive error reduced
```

A simple approximation:

```text
Expected Business Value
=
P(success)
×
Value(success)
```

---

# 20. Expected Net Value

A stronger formula:

```text
Expected Net Value
=
P(success) × Value(success)
− P(failure) × Cost(failure)
− Agent Cost
− Human Cost
```

This is a much more complete economic view.

---

# 21. Token Margin vs Value Margin

AI products often focus on:

```text
Token Margin
=
Revenue
− Inference Cost
```

A more useful strategic measure is:

```text
Value Margin
=
Value Delivered
− Total Cost to Deliver
```

Total delivery cost may include:

```text
inference
tools
retrieval
infrastructure
human review
rework
failure cost
```

This reframes tokenomics around value.

---

# 22. The Efficiency Ladder

A useful executive framework:

```text
1. Token Efficiency
   Are we reducing unnecessary inference?

2. Work Efficiency
   Is agentic work productive?

3. Information Efficiency
   Does that work produce useful new evidence?

4. Quality Efficiency
   Does the evidence improve output quality?

5. Outcome Efficiency
   Does quality improve task success?

6. Value Efficiency
   Is successful completion worth more than total delivery cost?
```

---

# 23. Marginal Value of Agentic Work

This is one of the most important concepts in Agent Economics.

Suppose:

```text
0 searches → quality 2.5
1 search   → quality 4.0
2 searches → quality 4.6
3 searches → quality 4.8
4 searches → quality 4.82
5 searches → quality 4.83
```

Initially:

```text
extra work
→ large quality gain
```

Later:

```text
extra work
→ almost no quality gain
```

This is:

```text
diminishing marginal returns
```

The agent should ideally stop near the elbow of the curve.

---

# 24. Marginal Cost and Marginal Value

For agentic step `n`:

```text
Marginal Value(n)
=
Value after step n
− Value after step n-1
```

```text
Marginal Cost(n)
=
Cost after step n
− Cost after step n-1
```

Conceptually, continue extra work while:

```text
Marginal Value
>
Marginal Cost
```

This is the economic interpretation of adaptive orchestration.

---

# 25. Agentic Budget

A practical control mechanism is to give each task an agentic budget.

Example:

```python
{
    "max_model_calls": 8,
    "max_searches": 5,
    "max_subagents": 2,
    "max_input_tokens": 50000,
    "max_latency_seconds": 90,
}
```

The budget should depend on:

```text
task complexity
task value
risk
latency tolerance
quality requirement
```

Example:

```text
Simple FAQ
→ small budget
```

```text
Architecture decision
→ medium budget
```

```text
High-value enterprise decision
→ larger budget
```

---

# 26. Adaptive Spend

A key design principle:

```text
Do not use maximum agentic capability for every task.
```

Instead:

```text
simple task
→ light architecture
```

```text
medium task
→ deeper agentic work
```

```text
complex task
→ richer agentic architecture
```

This is:

```text
adaptive spend
```

---

# 27. Complexity Routing

A likely architecture:

```text
                     User Task
                         ↓
                Complexity Router
              /          |          \
          Simple       Medium       Complex
            ↓             ↓             ↓
     Model + Search   Deep Agent   Deep Agent
                                  + Skills
                                  + Subagents
```

The key design objective is:

> Use the minimum sufficient agentic work for the task.

---

# 28. Value Frontier

Different agent architectures should be compared using:

```text
quality
vs
cost
```

Example:

```text
A = model only
B = model + search
C = Deep Agent
D = Deep Agent + memory
E = Deep Agent + skills
F = Deep Agent + subagents
```

Conceptually:

```text
quality
  ↑
5 |                    F
  |               E
4 |          C
  |     B
3 | A
  +--------------------------→ cost
```

The goal is not to pick one architecture universally.

The goal is to understand which architectures lie on the **value frontier**.

---

# 29. Pareto Efficiency

An architecture is Pareto-efficient if no other architecture is:

```text
cheaper
AND
higher quality
```

Example:

```text
A
cheap, lower quality
```

```text
C
moderate cost, high quality
```

```text
F
high cost, highest quality
```

All may be useful.

But if architecture X is:

```text
more expensive than C
AND
lower quality than C
```

then X is dominated and should generally be removed from consideration.

---

# 30. Economics of Memory

Memory can reduce:

```text
repeated user explanation
repeated research
repeated context
```

But it adds:

```text
retrieval cost
storage cost
embedding cost if semantic
context injection
stale-memory risk
```

Measure:

```text
Did memory reduce repeated work?
Did personalization improve success?
Did memory add irrelevant context?
```

Memory must earn its keep.

---

# 31. Economics of Skills

Without Skills:

```text
large always-loaded procedural prompt
```

With Skills:

```text
small skill catalog
→ selective procedure loading
```

Potential benefits:

```text
lower context cost
better specialized behavior
```

Potential costs:

```text
skill routing
skill reads
wrong skill selection
extra context
```

Measure:

```text
routing accuracy
quality delta
token delta
latency delta
```

---

# 32. Economics of Middleware

Summarization can reduce repeated context.

Example:

```text
5K → 10K → 20K → 35K
```

becomes:

```text
5K → 10K → compact → 8K → 12K
```

Benefits:

```text
lower context
lower latency
lower input token cost
```

Costs:

```text
summary generation
information loss
possible re-research
```

The real question:

```text
Context Saved
− Summary Cost
− Quality Loss
```

---

# 33. Economics of Subagents

Subagents may improve:

```text
specialization
context isolation
coverage
parallelism
```

but increase:

```text
model calls
searches
tokens
coordination overhead
```

Important distinction:

> Subagents may improve context efficiency while reducing compute efficiency.

Measure:

```text
ΔQuality
ΔCoverage
ΔLatency
ΔTotalTokens
ΔParentContext
ΔSubagentCalls
```

---

# 34. Economics of Retrieval

Retrieval is not free.

Costs include:

```text
search queries
vector retrieval
reranking
context insertion
model interpretation
```

A retrieval step is economically justified only if it materially improves:

```text
accuracy
coverage
grounding
task success
```

Repeated retrieval of already-known facts is pure waste.

---

# 35. Search Stopping Conditions

A good research agent should stop when:

```text
evidence is sufficient
important uncertainty is resolved
additional sources are mostly redundant
quality improvement has flattened
```

Poor stopping behavior is one of the most common sources of agentic waste.

---

# 36. Evidence Productivity

A useful research metric:

```text
Evidence Productivity
=
Novel Useful Evidence
─────────────────────
Search / Retrieval Calls
```

This is more informative than search count alone.

---

# 37. Agent Economics Record

Every run should produce a canonical record.

Example:

```python
{
    "task_id": "...",
    "architecture": "...",
    "complexity": "...",

    "input_tokens": 0,
    "output_tokens": 0,
    "model_calls": 0,

    "web_searches": 0,
    "tool_calls": 0,
    "subagent_calls": 0,
    "memory_reads": 0,
    "skill_loads": 0,
    "summarizations": 0,

    "latency_seconds": 0.0,

    "quality_score": 0.0,
    "citation_score": 0.0,
    "task_success": False,

    "estimated_agent_cost": 0.0,

    "human_review_minutes": 0.0,
    "human_rework_minutes": 0.0,

    "failure_cost": 0.0,
    "business_value_if_success": 0.0
}
```

---

# 38. Derived Metrics

Useful derived metrics include:

```text
total tokens
cost per successful task
tokens per successful task
searches per successful task
quality delta
latency delta
success-rate delta
```

Again:

> Keep metrics interpretable.

Avoid creating a single opaque economics score prematurely.

---

# 39. Experimental Design

A good economics experiment compares architectures across task complexity.

Example:

```text
A. Baseline model + Web Search
B. Deep Agent
C. Deep Agent + Skills
D. Deep Agent + Skills + Subagents
```

Across:

```text
simple
medium
complex
```

With:

```text
3 repetitions
```

Total:

```text
4 architectures
× 3 complexities
× 3 repetitions
= 36 runs
```

This is large enough to show patterns without becoming unmanageable.

---

# 40. Why Repetitions Matter

Agent systems are stochastic.

One run can be misleading.

Repeated runs help expose:

```text
variance
unstable routing
occasional over-searching
sporadic subagent use
quality variance
latency variance
```

For architecture comparisons, use repeated measurements.

---

# 41. Hypothesis Before Measurement

State expectations before running.

Example:

```text
Simple:
baseline should win economically
```

```text
Medium:
Deep Agent + Skills may win
```

```text
Complex:
Deep Agent + Skills + selective Subagents may win
```

The experiment must be allowed to prove the hypothesis wrong.

---

# 42. Compare by Complexity

Do not average everything together.

A single global average may hide:

```text
simple-task over-agenting
complex-task quality gains
```

Always analyze:

```text
simple
medium
complex
```

separately.

---

# 43. Cost per Successful Task

One of the best architecture metrics:

```text
Cost per Successful Task
=
Total Cost
──────────
Successful Tasks
```

This naturally combines:

```text
cost
+
reliability
```

and is often more useful than cost per request.

---

# 44. Effective Cost per Successful Task

Extend it further:

```text
Effective Cost per Successful Task
=
Agent Cost
+
Human Cost
+
Expected Failure Cost
```

divided by successful tasks.

This is closer to real enterprise economics.

---

# 45. Task Value

Task value can be estimated from:

```text
human time saved
revenue enabled
risk avoided
cycle time reduced
manual steps eliminated
support escalation avoided
```

Do not assume every task has the same value.

---

# 46. Value-Weighted Routing

A simple task with high business impact may justify more agentic work than a complex but low-value task.

Routing should eventually consider:

```text
complexity
+
risk
+
value
```

not complexity alone.

---

# 47. Economic Optimization Objective

A conceptual objective:

```text
maximize:

Business Value
──────────────
Total Agentic Work
```

subject to:

```text
quality ≥ required threshold
reliability ≥ required threshold
latency ≤ acceptable threshold
risk ≤ acceptable threshold
```

This is fundamentally different from:

```text
minimize tokens
```

---

# 48. Optimization Order

A good optimization sequence is:

```text
1. Make the task succeed reliably
2. Remove obvious waste
3. Improve routing
4. Reduce unnecessary context
5. Optimize model/tool selection
6. Optimize infrastructure
```

Do not begin by minimizing tokens.

A cheap failed task is still a failed task.

---

# 49. Leading vs Lagging Indicators

Useful leading indicators:

```text
search count
model calls
tool calls
subagent calls
context size
token count
latency
```

Useful lagging indicators:

```text
quality
task success
human rework
business value
```

Leading indicators help explain behavior.

Lagging indicators tell you whether it mattered.

---

# 50. Operational Metrics vs Business Metrics

Operational metrics:

```text
tokens
latency
searches
tool calls
model calls
```

Business metrics:

```text
success rate
rework
time saved
failure cost
value delivered
```

The strongest Agent Economics systems connect both.

---

# 51. Trend Analysis

Over many experiments, analyze:

```text
quality over time
token usage over time
latency over time
success rate over time
search efficiency
regression frequency
architecture decisions
```

Questions include:

```text
Are we becoming more efficient?
Are we trading quality for cost?
Are certain capabilities repeatedly causing regressions?
Do complex tasks benefit more from deeper orchestration?
```

---

# 52. Economics and Experiment History

Your improvement experiment log becomes valuable economics data.

A history may reveal:

```text
Skill changes
→ improve medium-task quality

Subagents
→ only help complex tasks

Memory
→ improves personalization but not generic research

Routing changes
→ reduce simple-task waste
```

That evidence can guide architecture.

---

# 53. From Experiments to Adaptive Architecture

Eventually, repeated experiments may justify:

```text
simple
→ model + search
```

```text
medium
→ Deep Agent + Skills
```

```text
complex
→ Deep Agent + Skills + selective Subagents
```

This should emerge from evidence, not intuition alone.

---

# 54. Agent Economics Reporting

A useful report should summarize:

```text
QUALITY
SUCCESS
AGENTIC WORK
TOKENS
LATENCY
COST
MARGINAL RETURNS
DOMINATED ARCHITECTURES
RECOMMENDED ROUTING
```

Example:

```text
Agent Economics Report
======================

SIMPLE TASKS
Best architecture: Model + Search
Reason:
- same success
- fewer tokens
- lower latency

MEDIUM TASKS
Best architecture: Deep Agent + Skills
Reason:
- better quality
- improved success
- moderate cost increase

COMPLEX TASKS
Best architecture: Deep Agent + Skills + Subagents
Reason:
- highest success
- deeper coverage
- extra cost justified

DOMINATED ARCHITECTURES
Deep Agent + Subagents on simple tasks

MARGINAL RETURNS
Searches beyond ~3 produced little additional quality.

RECOMMENDED ROUTING
simple  → baseline + search
medium  → Deep Agent + Skills
complex → Deep Agent + Skills + selective Subagents
```

---

# 55. Human-Readable Observations Matter

Do not stop at tables.

Translate metrics into statements such as:

```text
“Subagents improved complex-task quality but introduced unnecessary work on simple tasks.”
```

```text
“Search count fell 22% while quality remained stable.”
```

```text
“Latency increased 30% without improving success rate.”
```

This makes economics actionable.

---

# 56. What Not to Do

Avoid these anti-patterns.

## Token Minimization as the Goal

Bad:

```text
Use fewer tokens at all costs.
```

Better:

```text
Reduce wasted work while preserving required quality.
```

## One Universal Architecture

Bad:

```text
Every task uses maximum orchestration.
```

Better:

```text
Route according to task requirements.
```

## One Magic Economics Score

Bad:

```text
economics_score = 83
```

Better:

```text
quality
success
tokens
latency
cost
human rework
value
```

## Ignoring Failure Cost

Cheap inference may be extremely expensive if failure is costly.

## Ignoring Human Cost

A low-cost agent requiring heavy editing is not cheap.

## Ignoring Variance

One lucky run does not prove an architecture is better.

---

# 57. Maturity Model

A useful maturity progression:

## Level 1 — Token Accounting

Measure:

```text
input/output tokens
model cost
```

## Level 2 — Agentic Work Accounting

Add:

```text
searches
tools
subagents
retries
```

## Level 3 — Quality Economics

Add:

```text
quality
grounding
task success
```

## Level 4 — Human Economics

Add:

```text
review time
rework time
acceptance
```

## Level 5 — Business Economics

Add:

```text
value
failure cost
expected net value
```

## Level 6 — Adaptive Optimization

Use evidence to dynamically select:

```text
model
tools
search depth
skills
subagents
agentic budget
```

---

# 58. Recommended Implementation Sequence

A pragmatic engineering sequence:

```text
Phase 1
Capture:
tokens
latency
model calls
searches
tools
quality
task success
```

```text
Phase 2
Add:
Skills/subagent/memory/context metrics
```

```text
Phase 3
Add:
human review
rework
acceptance
```

```text
Phase 4
Add:
business value
failure cost
expected net value
```

```text
Phase 5
Use results for adaptive routing
```

---

# 59. Relationship to the Improvement Framework

The Reusable Agent Improvement Framework asks:

> Did the candidate get better?

Agent Economics asks:

> Was that improvement worth the extra work?

The bridge is:

```text
Improvement Framework
      ↓
ΔQuality
ΔSuccess
ΔTokens
ΔLatency
ΔSearches
ΔTool Calls
ΔSubagent Calls
      ↓
Agent Economics
```

Do not combine them prematurely.

First:

```text
prove improvement
```

Then:

```text
evaluate economic value
```

---

# 60. Relationship to Tracing

Tracing provides the raw operational evidence.

Example:

```text
model calls
tool calls
searches
subagent calls
latency
usage
```

Agent Economics transforms that into:

```text
productive work
waste
marginal returns
cost per success
value frontier
```

So:

```text
Tracing
→ operational facts

Evaluation
→ quality facts

Agent Economics
→ value interpretation
```

---

# 61. A Complete End-to-End Workflow

The full process:

```text
1. Define task classes
   ↓
2. Define candidate architectures
   ↓
3. Define success thresholds
   ↓
4. Run repeated experiments
   ↓
5. Capture tokens + trajectory + latency
   ↓
6. Evaluate quality
   ↓
7. Determine task success
   ↓
8. Estimate direct agent cost
   ↓
9. Add human review/rework if available
   ↓
10. Add failure cost if meaningful
   ↓
11. Estimate task/business value
   ↓
12. Compare architectures by complexity
   ↓
13. Identify dominated architectures
   ↓
14. Study marginal returns
   ↓
15. Recommend routing / agentic budgets
   ↓
16. Monitor trends over time
```

---

# 62. Example Architecture Comparison

Suppose:

```text
Architecture A
Model + Search
```

```text
Architecture B
Deep Agent
```

```text
Architecture C
Deep Agent + Skills
```

```text
Architecture D
Deep Agent + Skills + Subagents
```

For simple tasks:

```text
A may dominate.
```

For medium tasks:

```text
C may offer the best value.
```

For complex tasks:

```text
D may justify its extra cost.
```

This is why architecture selection should be conditional.

---

# 63. Example Decision Logic

A useful qualitative rule:

```text
If quality threshold is not met:
increase capability.

If threshold is met:
look for waste.

If quality improves but cost rises:
evaluate marginal value.

If extra work produces no useful improvement:
remove it.

If different architectures win by task class:
route dynamically.
```

---

# 64. Executive-Level Summary

Agent Economics is not about minimizing tokens.

It is about answering:

```text
How much useful work did the agent perform?
Did that work improve quality?
Did quality improve task success?
Was success worth the total cost?
```

The full ladder is:

```text
TOKENS
  ↓
WORK
  ↓
INFORMATION
  ↓
QUALITY
  ↓
OUTCOME
  ↓
VALUE
```

The guiding principle:

> **Reduce wasted work, not useful intelligence.**

And the end-state design principle:

> **Use the minimum sufficient agentic work required to achieve the desired business outcome.**
