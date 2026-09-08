"""Research Deep Agent on Microsoft Foundry — public API."""

from __future__ import annotations

from .agent import RESEARCH_INSTRUCTIONS, build_research_agent
from .config import Settings, TracingSettings, load_settings, load_tracing_settings
from .model import build_model
from .telemetry import (
    attach_tracing,
    build_azure_tracer,
    build_traced_research_agent,
)
from .tools import build_web_search_tool

__all__ = [
    "build_research_agent",
    "RESEARCH_INSTRUCTIONS",
    "Settings",
    "load_settings",
    "build_model",
    "build_web_search_tool",
    "TracingSettings",
    "load_tracing_settings",
    "build_azure_tracer",
    "attach_tracing",
    "build_traced_research_agent",
]
