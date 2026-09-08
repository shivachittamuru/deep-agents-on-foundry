"""Foundry built-in tools available to the research agent."""

from __future__ import annotations

from langchain_azure_ai.tools.builtin import WebSearchTool

from .errors import ToolInitializationError


def build_web_search_tool() -> WebSearchTool:
    """Provide the Foundry server-side web search tool."""
    try:
        return WebSearchTool()
    except Exception as exc:
        raise ToolInitializationError(
            "Failed to construct the Foundry web search tool."
        ) from exc
