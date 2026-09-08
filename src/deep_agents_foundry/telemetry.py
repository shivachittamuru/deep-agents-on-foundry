"""Application Insights / OpenTelemetry tracing for the research agent.

Promotes the tracing behavior proven in notebook 03. Tracing is kept fully
separate from agent construction.
"""

from __future__ import annotations

from langchain_azure_ai.callbacks.tracers import AzureAIOpenTelemetryTracer

from .agent import build_research_agent
from .config import TracingSettings, load_tracing_settings

DEFAULT_AGENT_ID = "deep-agents-foundry-research"


def build_azure_tracer(
    settings: TracingSettings | None = None,
    *,
    agent_id: str | None = DEFAULT_AGENT_ID,
) -> AzureAIOpenTelemetryTracer:
    """Build the `AzureAIOpenTelemetryTracer` from notebook 03."""
    settings = settings or load_tracing_settings()

    kwargs = {
        "connection_string": settings.connection_string,
        "enable_content_recording": settings.enable_content_recording,
    }
    if agent_id is not None:
        kwargs["agent_id"] = agent_id

    return AzureAIOpenTelemetryTracer(**kwargs)


def attach_tracing(agent, tracer):
    """Attach a tracer to an existing agent via LangGraph's callback config."""
    return agent.with_config({"callbacks": [tracer]})


def build_traced_research_agent(
    settings: TracingSettings | None = None,
    *,
    agent_id: str | None = DEFAULT_AGENT_ID,
):
    """Compose the existing research agent with an Application Insights tracer."""
    agent = build_research_agent()
    tracer = build_azure_tracer(settings, agent_id=agent_id)
    return attach_tracing(agent, tracer)
