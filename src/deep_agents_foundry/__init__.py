"""Research Deep Agent on Microsoft Foundry — public API."""

from __future__ import annotations

from .agent import RESEARCH_INSTRUCTIONS, build_research_agent
from .config import Settings, load_settings
from .model import build_model
from .tools import build_web_search_tool

__all__ = [
    "build_research_agent",
    "RESEARCH_INSTRUCTIONS",
    "Settings",
    "load_settings",
    "build_model",
    "build_web_search_tool",
]
