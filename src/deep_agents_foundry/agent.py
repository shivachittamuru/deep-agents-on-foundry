"""Construct the research Deep Agent from notebooks 01-02."""

from __future__ import annotations

from deepagents import create_deep_agent

from .model import build_model
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


def build_research_agent():
    """Build the research Deep Agent: Foundry model + web search + instructions."""
    model = build_model()
    tools = [build_web_search_tool()]

    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=RESEARCH_INSTRUCTIONS,
    )
