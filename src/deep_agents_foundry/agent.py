"""Construct the research Deep Agent from notebooks 01-02."""

from __future__ import annotations

from deepagents import create_deep_agent

from .errors import AgentInitializationError
from .memory import MEMORY_POLICY, MEMORY_TOOLS, ResearchContext
from .model import build_model
from .skills import build_skills_backend
from .tools import build_web_search_tool

RESEARCH_INSTRUCTIONS = """
You are an expert research assistant.

Your job is to research questions thoroughly and produce concise,
evidence-grounded answers.

## Research behavior

- Use web search whenever current or externally verifiable information is needed.
- Prefer authoritative and primary sources when possible.
- Search more than once when the first search does not fully answer the question.
- Distinguish established facts from interpretation.
- Include source citations in your final answer when web research was used.

You also have the standard Deep Agents capabilities for planning,
filesystem-based context management, and subagent delegation.
"""


def build_research_agent(
    *, checkpointer=None, interrupt_on=None, store=None, skills=None
):
    """Build the research Deep Agent: Foundry model + web search + instructions.

    Architecture for open-ended research:
    - Deep Agents owns dynamic reasoning/orchestration (the primary agent layer).
    - the LangGraph checkpointer owns durable thread state (see `persistence.py`).
    - native Deep Agents HITL (`interrupt_on`) handles tool/action approval.
    - an injected `store` enables cross-thread, user-scoped long-term memory
      (see `memory.py`); `user_id` comes from a trusted `ResearchContext` passed
      at invoke time, never from the LLM.
    - `skills` (source paths, e.g. `["."]`) enables progressive-disclosure
      procedural knowledge loaded from disk (see `skills.py`); the skills
      middleware injects its own routing prompt, so the base prompt is unchanged.

    Use an outer LangGraph workflow only for a truly fixed business process, not
    for general research. Stateless, non-interrupting, memoryless, and
    skill-less by default.

    `interrupt_on` maps tool names to the native Deep Agents HITL config
    (`bool` or `InterruptOnConfig`); it requires a `checkpointer` at runtime to
    persist the paused state.
    """
    model = build_model()
    tools = [build_web_search_tool()]
    system_prompt = RESEARCH_INSTRUCTIONS

    if store is not None:
        tools = tools + MEMORY_TOOLS
        system_prompt = RESEARCH_INSTRUCTIONS + MEMORY_POLICY

    kwargs = {
        "model": model,
        "tools": tools,
        "system_prompt": system_prompt,
    }
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer
    if interrupt_on is not None:
        kwargs["interrupt_on"] = interrupt_on
    if store is not None:
        kwargs["store"] = store
        kwargs["context_schema"] = ResearchContext
    if skills is not None:
        kwargs["skills"] = skills
        kwargs["backend"] = build_skills_backend()

    try:
        return create_deep_agent(**kwargs)
    except Exception as exc:
        raise AgentInitializationError(
            "Failed to construct the research Deep Agent."
        ) from exc
