"""Research Deep Agent on Microsoft Foundry — public API."""

from __future__ import annotations

from .agent import RESEARCH_INSTRUCTIONS, build_research_agent
from .config import Settings, TracingSettings, load_settings, load_tracing_settings
from .content import content_text
from .errors import (
    AgentInitializationError,
    ConfigurationError,
    DeepAgentsFoundryError,
    ModelInitializationError,
    ToolInitializationError,
)
from .evaluation import (
    RESEARCH_RUBRIC,
    aggregate_usage,
    build_rubric_prompt,
    deterministic_evaluation,
    evaluate_with_rubric,
    extract_trajectory_features,
    has_citation_like_content,
    parse_judge_json,
    trajectory_summary,
)
from .model import build_model
from .persistence import build_sqlite_checkpointer, thread_config
from .streaming import stream_research_text
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
    "content_text",
    "stream_research_text",
    "build_sqlite_checkpointer",
    "thread_config",
    "TracingSettings",
    "load_tracing_settings",
    "build_azure_tracer",
    "attach_tracing",
    "build_traced_research_agent",
    "RESEARCH_RUBRIC",
    "extract_trajectory_features",
    "aggregate_usage",
    "has_citation_like_content",
    "trajectory_summary",
    "deterministic_evaluation",
    "build_rubric_prompt",
    "parse_judge_json",
    "evaluate_with_rubric",
    "DeepAgentsFoundryError",
    "ConfigurationError",
    "ModelInitializationError",
    "ToolInitializationError",
    "AgentInitializationError",
]
