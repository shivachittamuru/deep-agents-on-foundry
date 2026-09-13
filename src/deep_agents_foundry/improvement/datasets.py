"""Built-in core research dataset with DEV / HELD-OUT subsets (P8C).

Compact on purpose (~6-12 cases). Covers a representative spread of behaviors so
a change can be judged without a giant benchmark. Add future regression cases by
appending an `EvaluationCase` with an appropriate subset tag.
"""

from __future__ import annotations

from .models import EvaluationCase

DEV = "dev"
HELD_OUT = "held_out"


_CORE_CASES: tuple[EvaluationCase, ...] = (
    EvaluationCase(
        id="simple_definition",
        prompt="What are Microsoft Foundry Hosted Agents?",
        complexity="simple",
        expected={"needs_web": True, "max_searches": 2, "should_delegate": False},
        tags=(DEV,),
        protects_against="Over-searching or delegating on a simple factual lookup.",
    ),
    EvaluationCase(
        id="medium_architecture",
        prompt=(
            "Explain Microsoft Foundry Hosted Agents architecture, "
            "state/session boundaries, and identity model."
        ),
        complexity="medium",
        expected={"needs_web": True, "max_searches": 4},
        tags=(DEV,),
        protects_against="Shallow architecture research without enough investigation.",
    ),
    EvaluationCase(
        id="tool_negative",
        prompt=(
            "Explain the difference between a tool and middleware in one paragraph."
        ),
        complexity="simple",
        expected={"needs_web": False, "max_searches": 0, "should_delegate": False},
        tags=(DEV,),
        protects_against="Unnecessary web search on a self-contained conceptual task.",
    ),
    EvaluationCase(
        id="skill_routing",
        prompt=(
            "Research LangGraph architecture and explain its most important "
            "design trade-offs."
        ),
        complexity="medium",
        expected={"needs_web": True, "max_searches": 4, "expected_skill": "technology-research"},
        tags=(DEV,),
        protects_against="Failing to route a technology-research task to its skill.",
    ),
    EvaluationCase(
        id="memory_preference",
        prompt=(
            "Remember that I prefer concise answers with bullet-point citations, "
            "then summarize what Microsoft Foundry Agent Service provides."
        ),
        complexity="simple",
        expected={"needs_web": True, "max_searches": 2, "should_delegate": False},
        tags=(DEV,),
        protects_against="Ignoring a durable user preference or over-working a simple ask.",
    ),
    EvaluationCase(
        id="simple_no_overagent",
        prompt="In two sentences, what is retrieval-augmented generation?",
        complexity="simple",
        expected={"needs_web": False, "max_searches": 0, "should_delegate": False},
        tags=(HELD_OUT,),
        protects_against="A simple task drifting into tool use or delegation.",
    ),
    EvaluationCase(
        id="complex_comparison",
        prompt=(
            "Compare Microsoft Foundry Hosted Agents with a custom AKS-hosted "
            "LangGraph agent for enterprise workloads. Cover architecture, identity, "
            "state ownership, scaling, observability, reliability, and lock-in."
        ),
        complexity="complex",
        expected={"needs_web": True, "max_searches": 8},
        tags=(HELD_OUT,),
        protects_against="Weak synthesis or missing dimensions on a comparison task.",
    ),
    EvaluationCase(
        id="subagent_identity",
        prompt=(
            "Research Hosted Agent authentication, managed identity, RBAC, "
            "credential flow, and important security boundaries."
        ),
        complexity="complex",
        expected={
            "needs_web": True,
            "max_searches": 8,
            "should_delegate": True,
            "expected_subagent": "identity-researcher",
        },
        tags=(HELD_OUT,),
        protects_against="Failing to delegate a deep identity/security investigation.",
    ),
)


def core_research_dataset() -> list[EvaluationCase]:
    """Return the full built-in core research dataset (fresh list each call)."""
    return list(_CORE_CASES)


def dev_cases() -> list[EvaluationCase]:
    """Cases to inspect and iterate on frequently."""
    return [case for case in _CORE_CASES if DEV in case.tags]


def held_out_cases() -> list[EvaluationCase]:
    """Cases run less often to confirm a change generalizes."""
    return [case for case in _CORE_CASES if HELD_OUT in case.tags]
