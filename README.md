---
title: Hosted Deep Agents on Microsoft Foundry
description: Production-oriented Deep Agent engineering harness on Microsoft Foundry
---

> **Build, evaluate, host, operate, improve, and optimize production-oriented Deep Agent harnesses on Microsoft Foundry, from reliability to agent economics.**

This repository is an end-to-end reference implementation and engineering lab for building production-oriented AI agents with **LangGraph / Deep Agents** on **Microsoft Foundry**.

The project started as a simple research agent and evolved into a complete agent-engineering harness covering:

- agent construction and tool use
- streaming
- tracing and observability
- deterministic and rubric-based evaluation
- Hosted Agent deployment using the Responses protocol
- durable thread state
- long-term user memory
- Skills and context engineering
- notebook-driven subagent experiments and reusable specs
- reusable offline agent-improvement experiments
- experiment logging and trend analysis
- Agent Economics
- PostgreSQL-backed persistence
- Microsoft Entra authentication
- production-oriented async pooling

The project is intentionally **use-case agnostic**. The current research agent is a reference workload for exercising the harness. The same architecture can later support practical domain agents such as a **Tokenomics Advisor**, **OwnerLens investing agent**, enterprise research assistant, support agent, or another specialized workflow.

---

## Why this project exists

Building an agent that can answer a question is relatively easy.

Building one that can be:

```text
observed
evaluated
debugged
persisted
hosted
improved
measured economically
```

is much harder.

This repository focuses on the second problem.

The project explores the complete engineering path:

```text
Prototype
   ↓
Understand behavior
   ↓
Add tools
   ↓
Trace
   ↓
Evaluate
   ↓
Add persistence
   ↓
Add memory
   ↓
Add Skills / subagents
   ↓
Host
   ↓
Measure improvement
   ↓
Measure economics
   ↓
Operate as a production-oriented agent system
```

A major design principle throughout the repository is:

> **Understand a capability in a notebook first, then productionize it into reusable code.**

---

## Architecture

At a high level:

```text
                         USER / CLIENT
                              │
                              ▼
                    Responses Protocol
                              │
                              ▼
                    Microsoft Foundry
                     Hosted Agent Runtime
                              │
                              ▼
                 LangGraph / Deep Agents
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
      Model                Tools                Skills
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                              ▼
                    Agent execution loop
                              │
             ┌────────────────┴────────────────┐
             │                                 │
             ▼                                 ▼
      AsyncPostgresSaver                AsyncPostgresStore
             │                                 │
          thread_id                           user_id
             │                                 │
   thread / checkpoint state        long-term user memory
             │                                 │
             └────────────────┬────────────────┘
                              ▼
                 Azure Database for PostgreSQL
                              │
                              ▼
               offline evaluation / economics
```

The architecture deliberately separates:

```text
Agent intelligence
≠
Framework
≠
Runtime
≠
Platform
≠
Persistence
≠
Evaluation
≠
Economics
```

---

## Core design principles

### 1. Responses is the northbound protocol

The Hosted Agent exposes a **Responses-compatible** interface to clients.

The protocol is intentionally separate from the internal orchestration framework.

```text
Client
  ↓
Responses protocol
  ↓
Hosted Agent
  ↓
LangGraph / Deep Agents
```

---

### 2. LangGraph / Deep Agents own orchestration

The project uses Deep Agents / LangGraph for:

- agent execution
- tool orchestration
- thread state
- interrupts / HITL
- Skills
- subagents
- long-term Store integration

The project does not rewrite the runtime in another agent framework simply because the agent is hosted on Microsoft Foundry.

The hosted builder currently enables checkpointing, Store-backed memory, and Skills. Native HITL is supported by the builder and tests, but client-driven approval/resume is not yet wired into the Responses handler. Custom subagent specs are exercised from notebook 13 rather than configured in the hosted builder.

---

### 3. Thread state and long-term memory are separate

Two identifiers solve different problems:

```text
thread_id
→ which conversation / execution?

user_id
→ whose long-term memory?
```

Short-term state:

```text
AsyncPostgresSaver
      ↓
thread_id
      ↓
messages
graph state
checkpoints
interrupts
```

Long-term memory:

```text
AsyncPostgresStore
      ↓
user_id + namespace
      ↓
preferences
durable memories
cross-thread context
```

Never collapse `thread_id` and `user_id` into the same concept.

---

### 4. Trace first, then evaluate

Tracing answers:

> What happened?

Evaluation answers:

> Was it good?

Agent improvement requires both.

```text
Trace
  ↓
Failure taxonomy
  ↓
Hypothesis
  ↓
Targeted evaluation
  ↓
Small change
  ↓
Baseline vs candidate
  ↓
Keep / Revert / Investigate
```

---

### 5. Optimize wasted work, not useful intelligence

The project treats token consumption as only the first layer of economics.

```text
Tokens
  ↓
Agentic Work
  ↓
Useful Progress / Information Gain
  ↓
Quality
  ↓
Task Outcome
  ↓
Business Value
```

A cheaper agent is not necessarily better.

The goal is:

> **Use the minimum sufficient agentic work required to achieve the desired outcome.**

---

## Major capabilities

### Agent runtime

The base research agent is built with:

- Deep Agents
- LangGraph
- Foundry-hosted language models
- built-in / external tools
- structured project configuration

The agent builder is intentionally small and reusable so other use cases can be substituted later.

---

### Tool integration

The current research agent includes a Microsoft Foundry Web Search integration through `langchain-azure-ai`.

> **Important:** `WebSearchTool` is currently a preview capability and is not recommended as a production dependency. It may be replaced in a future version of this project.

The harness is designed so tool implementations can be replaced without redesigning the entire agent.

---

### Streaming

The project supports streaming through:

```text
Deep Agent / LangGraph
      ↓
Responses streaming
      ↓
Hosted Agent SSE
      ↓
client
```

Streaming is treated separately from:

- tracing
- concurrency
- persistence
- durability
- background processing

`TextResponse` receives an asynchronous text iterator. A direct Responses client must send `"stream": true` to receive visible incremental events.

---

### Tracing and observability

Azure OpenTelemetry / Application Insights tracing helpers are available to inspect agent execution. Tracing is opt-in and is not currently attached by the default Hosted Agent builder.

Tracing helps answer questions such as:

- how many model calls occurred?
- which tools were used?
- how many searches happened?
- were retries triggered?
- how long did the run take?
- how did execution differ between baseline and candidate?

Tracing is operational evidence, not quality evaluation.

---

### Evaluation

The project includes reusable evaluation primitives for:

- deterministic checks
- citation-like content checks
- trajectory features
- usage aggregation
- rubric evaluation
- LLM-as-judge
- behavioral summaries

Evaluation is intentionally layered:

```text
deterministic checks
+
trajectory evaluation
+
rubric quality
```

Different agent types require different success criteria.

---

### Hosted Agent deployment

The agent is deployable to Microsoft Foundry as a Hosted Agent.

The repository declares Responses protocol version `2.0.0` in `azure.yaml`. The current `azd ai agent` extension used to run, invoke, and inspect the agent is itself a preview extension.

Key concepts:

```text
Agent
→ logical agent definition

Version
→ deployed implementation/configuration

Endpoint
→ invocation surface

Session
→ hosted runtime sandbox/workspace
```

Hosted Agent sessions are not the same thing as LangGraph threads or long-term memory.

---

### Persistence

The Hosted Agent uses Azure PostgreSQL for both:

```text
AsyncPostgresSaver
→ thread / checkpoint state

AsyncPostgresStore
→ long-term memory
```

A shared async connection pool is initialized once per Hosted Agent process.

Authentication uses Microsoft Entra ID and refresh-aware PostgreSQL connection creation.

The production runtime no longer depends on SQLite.

SQLite helpers are retained only where useful for earlier notebooks and learning scenarios.

---

### Long-term memory

Long-term memory is explicit and user-scoped.

Typical durable memories include:

- stable research preferences
- durable user preferences
- long-lived project context
- explicitly remembered instructions

The Store infrastructure does not decide what should be remembered.

Memory policy and retrieval policy remain application concerns.

The handler accepts `metadata.user_id`, but currently falls back to a fixed single-tester identity when it is absent. Binding memory ownership to authenticated application identity is still required before multi-user production use.

---

### Skills

Skills represent reusable procedures:

```text
Tool
→ primitive action

Skill
→ how to perform a class of task

Memory
→ what the agent knows
```

Skills are progressively disclosed instead of permanently bloating the system prompt.

Example research Skills include:

- technology research
- architecture comparison
- evidence synthesis

The hosted builder loads root `skills/*/SKILL.md` files through `FilesystemBackend` when that directory is available.

---

### Context management

The project explores how context should be assembled and managed across:

```text
system instructions
memory
Skills
conversation history
summaries
files
tool schemas
```

A useful mental model is:

```text
L1 — active prompt/context
L2 — compact summaries
L3 — recoverable history/artifacts
```

The goal is not simply smaller context.

The goal is preserving useful information while removing repeated or low-value context.

---

### Subagents

Subagents are treated as:

> specialization + context partitioning

not as a default requirement for every task.

They can improve:

- specialization
- task decomposition
- context isolation

but may increase:

- total tokens
- latency
- coordination overhead
- duplicated work

Subagents are therefore evaluated economically, not adopted automatically.

The repository currently provides reusable specs under `subagents/` and notebook experiments. Those custom specs are not wired into `build_research_agent()` or the hosted request path.

---

## Reusable Agent Improvement Framework

The repository includes a reusable offline framework for answering:

> **“I changed my agent. Did it actually get better?”**

The offline framework is implemented under:

```text
improvement/
├── models.py
├── datasets.py
├── runner.py
├── diagnosis.py
├── comparison.py
├── reporting.py
└── experiment_log.py
```

The flow is:

```text
Evaluation dataset
      ↓
Run baseline
      ↓
Run candidate
      ↓
Compare quality + trajectory + performance
      ↓
Diagnose regressions
      ↓
Render report
      ↓
KEEP / REVERT / INVESTIGATE
      ↓
Persist compact experiment JSON
```

Experiment summaries are stored under:

```text
artifacts/experiments/
```

The framework deliberately avoids a single opaque “agent score.”

Instead it preserves interpretable deltas such as:

```text
Δ quality
Δ success
Δ tokens
Δ latency
Δ searches
Δ tool calls
Δ subagent calls
```

---

## Trend analysis

Accumulated experiment logs can be analyzed to answer:

- Are quality deltas improving over time?
- Are tokens / latency / searches trending down?
- Which failure categories recur?
- Which change types most often result in KEEP vs REVERT?
- Are held-out regressions decreasing?
- Which task complexities benefit from deeper orchestration?

Repeated failures can eventually become permanent regression cases.

This creates a feedback loop:

```text
Experiment history
      ↓
Repeated failure pattern
      ↓
Engineering insight
      ↓
Candidate regression case
      ↓
Stronger evaluation dataset
```

---

## Agent Economics

The offline Agent Economics framework asks a different question:

> **“Was the improvement worth the work and cost?”**

The core ladder is:

```text
Tokens
  ↓
Agentic Work
  ↓
Useful Progress
  ↓
Quality
  ↓
Task Outcome
  ↓
Business Value
```

The economics package analyzes:

- tokens
- model calls
- searches
- tool calls
- subagent calls
- latency
- quality
- task success
- direct cost
- human review / rework cost
- failure cost
- business value when supplied

Key concepts include:

- cost per successful task
- effective task cost
- human rework economics
- value frontier
- Pareto efficiency
- marginal returns
- diminishing returns
- task-complexity-aware architecture comparison

Example insight:

```text
Simple tasks
→ baseline + search may be sufficient

Medium tasks
→ Deep Agent + Skills may provide better value

Complex tasks
→ selective subagents may become worthwhile
```

These conclusions are not hard-coded. They must come from experiment data.

The included economics datasets are synthetic examples. Production conclusions require measured runs with real cost, quality, and outcome inputs.

Economics analysis summaries can be persisted under:

```text
artifacts/economics/
```

---

## Notebook-first learning journey

The project was developed incrementally through a series of notebooks.

The current notebook sequence is listed below. Titles reproduce each notebook's displayed heading; notebook 07 currently starts at its goal section without a top-level title.

| File | Displayed title |
|------|-----------------|
| `01_deep_agent_baseline.ipynb` | 01 - Deep Agent Baseline on Microsoft Foundry |
| `02_deep_agent_web_search.ipynb` | 02 - Deep Agent with Microsoft Foundry Web Search |
| `03_deep_agent_tracing.ipynb` | 03 - Deep Agent Tracing with Microsoft Foundry |
| `04_1_deep_agent_evaluation_foundations.ipynb` | 04.1 - Evaluating a Deep Research Agent (Foundations) |
| `04_2_deep_agent_value_frontier.ipynb` | 04.2 - Deep Agent Value Frontier (Rigorous Comparison) |
| `05_responses_vs_agent_owned_state.ipynb` | 05 - Responses vs Agent-Owned State |
| `06_streaming.ipynb` | 06 - Streaming |
| `07_hosted_sessions_and_workspace.ipynb` | No top-level title |
| `08_langgraph_threads_and_sqlite.ipynb` | 08 - LangGraph Threads and SQLite Checkpointing |
| `09.1_durable_execution_and_interrupts.ipynb` | 09 - Durable Execution and Interrupts |
| `09.2_deep_agent_native_durability_and_interrupts.ipynb` | 09.2 - Native Deep Agent Durability and Interrupts |
| `10_memory_for_research_deep_agent.ipynb` | Notebook 10 - Memory for the Research Deep Agent |
| `11_skills_for_research_deep_agent.ipynb` | Notebook 11 - Skills for the Research Deep Agent |
| `12_middleware_and_context_management.ipynb` | Notebook 12 - Middleware and Context Management for the Research Deep Agent |
| `13_subagents_for_research_deep_agent.ipynb` | Notebook 13 - Subagents for the Research Deep Agent |
| `14_trace_eval_driven_improvement.ipynb` | Notebook 14 - Trace and Eval Driven Improvement |
| `15_agent_economics_token_to_value.ipynb` | Notebook 15 - Agent Economics: Tokens to Work to Quality to Outcome to Value |
| `16_postgres_persistence_and_semantic_memory.ipynb` | 16 - PostgreSQL Persistence, Long-Term Memory, and Optional pgvector |

The notebook-first pattern is:

```text
Learn
  ↓
Inspect APIs
  ↓
Run manually
  ↓
Understand failure modes
  ↓
Productionize into src/
  ↓
Add focused tests
```

---

## Repository structure

A simplified view:

```text
.
├── src/
│   └── deep_agents_foundry/
│       ├── agent.py
│       ├── config.py
│       ├── content.py
│       ├── errors.py
│       ├── evaluation.py
│       ├── hosting.py
│       ├── memory.py
│       ├── model.py
│       ├── paths.py
│       ├── persistence.py
│       ├── skills.py
│       ├── streaming.py
│       ├── telemetry.py
│       ├── tools.py
│       │
│       ├── improvement/
│       │   ├── models.py
│       │   ├── datasets.py
│       │   ├── runner.py
│       │   ├── diagnosis.py
│       │   ├── comparison.py
│       │   ├── reporting.py
│       │   └── experiment_log.py
│       │
│       └── economics/
│           ├── adapters.py
│           ├── datasets.py
│           ├── models.py
│           ├── metrics.py
│           ├── comparison.py
│           ├── frontier.py
│           ├── reporting.py
│           ├── economics_log.py
│           └── run_agent_economics.py
│
├── notebooks/
├── skills/
├── subagents/
├── scripts/
├── tests/
├── docs/
├── artifacts/
│   ├── experiments/
│   └── economics/
│
├── azure.yaml
├── pyproject.toml
└── README.md
```

The actual repository should always be treated as the source of truth if this structure changes.

---

## Getting started

### Prerequisites

Typical development prerequisites:

- Python 3.12 or later (the hosted runtime is configured for Python 3.13)
- `uv`
- Azure CLI
- Azure Developer CLI (`azd`)
- Foundry agents extension for `azd` (currently preview)
- Microsoft Entra access to the required Azure resources
- Foundry project
- deployed model
- Application Insights
- Azure Database for PostgreSQL

Depending on which notebook or feature you run, additional Azure resources may be required.

---

### Install dependencies

From the repository root:

```powershell
uv sync
```

---

### Environment variables

The project uses `.env` for non-secret configuration.

Representative variables include:

```text
AZURE_AI_PROJECT_ENDPOINT=...
AZURE_AI_MODEL_DEPLOYMENT_NAME=...
APPLICATIONINSIGHTS_CONNECTION_STRING=...

POSTGRES_HOST=<server>.postgres.database.azure.com
POSTGRES_DATABASE=deepagents
POSTGRES_USER=<entra-postgres-principal>
POSTGRES_SSLMODE=require
```

Tracing content recording is typically controlled separately, for example:

```text
ENABLE_TRACE_CONTENT_RECORDING=false
```

Optional hosted-development overrides include:

```text
DEEP_AGENTS_DEFAULT_USER_ID=<single-tester-id>
DEEP_AGENTS_SKILLS_DIR=<path-to-skills-directory>
```

No PostgreSQL password or Entra access token should be stored in `.env`.

Authentication is performed using Microsoft Entra ID.

`AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` in `.env.example` support optional notebook experiments; the production package does not currently consume them.

For `azd ai agent run` and deployment, values referenced by `azure.yaml` come from the active `azd` environment. They can differ from values in the root `.env`; inspect them with `azd env get-values`.

---

## Run tests

Run the complete suite:

```powershell
uv run pytest
```

Run a focused test file:

```powershell
uv run pytest tests/test_persistence.py -v
```

The project intentionally keeps most tests deterministic and network-free.

Live Azure / Hosted Agent validation is performed separately.

---

## Run the Hosted Agent locally

Authenticate first:

```powershell
az login
azd auth login
```

Then:

```powershell
azd ai agent run
```

The local Hosted Agent uses the Responses protocol.

In another terminal, a basic smoke test can be run with:

```powershell
azd ai agent invoke --local "Say hello in one sentence."
```

The CLI reuses its session and conversation by default. To explicitly exercise application-owned identity routing, send a structured Responses request containing stable `metadata.thread_id` values across turns and distinct `metadata.user_id` values for memory-isolation tests. The current handler does not consume the CLI's `--user-identity` header.

---

## Deploy to Microsoft Foundry

Deploy using:

```powershell
azd deploy
```

Then inspect the deployed Hosted Agent:

```powershell
azd ai agent show
```

Invoke remotely:

```powershell
azd ai agent invoke "Say hello in one sentence."
```

Follow Hosted Agent logs:

```powershell
azd ai agent monitor --follow
```

---

## PostgreSQL persistence

The Hosted Agent uses one async PostgreSQL connection pool per process.

Conceptually:

```text
Hosted process
    ↓
PostgresPersistence
    ↓
AsyncConnectionPool
   ├── AsyncPostgresSaver
   └── AsyncPostgresStore
```

Authentication:

```text
Managed Identity / DefaultAzureCredential
      ↓
Entra PostgreSQL token
      ↓
refresh-aware connection creation
      ↓
async pool
```

`DefaultAzureCredential` is used independently for the Foundry model and PostgreSQL. For local runs, `POSTGRES_USER` must name a PostgreSQL role mapped to the signed-in developer identity (commonly the Azure CLI user's UPN). For deployment, it must match a PostgreSQL role created for the Hosted Agent's managed identity.

Schema setup runs once when the persistent agent is initialized lazily on the first hosted request.

Persistence failure is fail-fast.

There is no silent fallback to SQLite in the Hosted Agent production path.

---

## Deferred pgvector semantic memory

Notebook 16 explores a possible future semantic-memory path using pgvector. The production package does not configure embeddings, a vector index, or semantic Store retrieval.

Conceptually:

```text
PostgresStore
    ↓
structured namespace retrieval

optional:
PostgresStore + embeddings + pgvector
    ↓
semantic retrieval
```

The project currently treats semantic memory as deferred rather than required.

Long-term memory does not require a vector database.

---

## Security and identity

Two identities remain intentionally separate:

```text
thread_id
→ conversation identity

user_id
→ long-term memory owner
```

In a real multi-user application:

```text
user authenticates
      ↓
trusted application / platform identity
      ↓
user_id
      ↓
ResearchContext(user_id=...)
```

The browser or model should never be trusted to choose another user's memory identity. The current metadata-based single-tester seam must be replaced or validated at a trusted application boundary for multi-user deployment.

---

## Current limitations

### Web Search is preview

The current Foundry `WebSearchTool` is preview/experimental.

It may change and is not recommended as a production dependency without accepting preview constraints.

The project may replace it with another production-suitable retrieval/search implementation.

---

### Current use case is intentionally generic

The research agent primarily exists to exercise the harness.

A future version may specialize the same architecture into something more useful, such as:

- Tokenomics Advisor
- OwnerLens Deep Agent
- enterprise architecture research agent
- support agent
- specialized analysis assistant

---

### Hosted HITL resume is deferred

The agent builder and tests support native Deep Agents interrupts. The Hosted Agent handler can report that a run paused, but it does not yet accept and apply a client approval decision to resume that checkpoint.

### Semantic memory is deferred

pgvector has been explored in notebook 16 as a possible semantic-retrieval layer, but it is not implemented in the production package. Structured PostgreSQL Store retrieval remains sufficient for the current memory tools.

---

### UI is intentionally deferred

A ChatGPT-style frontend with:

- login
- conversation sidebar
- multi-user chat
- saved conversation history
- economics dashboards
- improvement dashboards

is a possible future extension, but is not required to demonstrate the agent harness.

---

## Future directions

Possible next steps include:

```text
production-grade replacement for preview Web Search
domain-specific agent specialization
Tokenomics Advisor
OwnerLens Deep Agent
semantic long-term memory
multi-user application UI
economics dashboard
improvement / regression dashboard
adaptive agentic budgets
complexity-aware routing
```

A likely long-term direction is to use experiment and economics evidence to determine when different agentic capabilities are worth activating.

Example:

```text
simple
→ light architecture

medium
→ Deep Agent + Skills

complex
→ deeper orchestration + selective subagents
```

Only evidence should justify those routing decisions.

---

## What this project demonstrates

The repository is intended to answer a practical question:

> **What does it take to move an AI agent from a demo into an engineered, observable, persistent, improvable, and economically measurable system?**

The answer is not one framework or one model.

It is the combination of:

```text
Agent design
+
Orchestration
+
Tooling
+
Observability
+
Evaluation
+
Persistence
+
Memory
+
Context engineering
+
Hosting
+
Improvement discipline
+
Agent Economics
```

That combined system is the real **agent harness**.

---

## Final mental model

```text
BUILD
  ↓
TRACE
  ↓
EVALUATE
  ↓
HOST
  ↓
PERSIST
  ↓
REMEMBER
  ↓
IMPROVE
  ↓
MEASURE ECONOMICS
  ↓
OPERATE
```

The goal is not merely to build a more capable agent.

The goal is to build an agent system that can be:

> **understood, trusted, improved, and economically justified.**
