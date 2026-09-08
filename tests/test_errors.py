"""Tests for construction-boundary error translation (no live calls)."""

from __future__ import annotations

import pytest

from deep_agents_foundry import agent as agent_module
from deep_agents_foundry import tools as tools_module
from deep_agents_foundry.errors import (
    AgentInitializationError,
    ModelInitializationError,
    ToolInitializationError,
)


def test_build_web_search_tool_wraps_constructor_failure(monkeypatch):
    original = RuntimeError("tool boom")

    def failing_tool():
        raise original

    monkeypatch.setattr(tools_module, "WebSearchTool", failing_tool)

    with pytest.raises(ToolInitializationError) as excinfo:
        tools_module.build_web_search_tool()

    assert excinfo.value.__cause__ is original


def test_build_research_agent_wraps_create_deep_agent_failure(monkeypatch):
    original = RuntimeError("agent boom")

    monkeypatch.setattr(agent_module, "build_model", lambda: object())
    monkeypatch.setattr(agent_module, "build_web_search_tool", lambda: object())

    def failing_create(**kwargs):
        raise original

    monkeypatch.setattr(agent_module, "create_deep_agent", failing_create)

    with pytest.raises(AgentInitializationError) as excinfo:
        agent_module.build_research_agent()

    assert excinfo.value.__cause__ is original


def test_build_research_agent_does_not_rewrap_model_error(monkeypatch):
    original = ModelInitializationError("model failed")

    def failing_build_model():
        raise original

    monkeypatch.setattr(agent_module, "build_model", failing_build_model)
    # create_deep_agent must never be reached if the model fails first.
    monkeypatch.setattr(
        agent_module,
        "create_deep_agent",
        lambda **kwargs: pytest.fail("create_deep_agent should not run"),
    )

    with pytest.raises(ModelInitializationError) as excinfo:
        agent_module.build_research_agent()

    assert excinfo.value is original


def test_build_research_agent_does_not_rewrap_tool_error(monkeypatch):
    original = ToolInitializationError("tool failed")

    monkeypatch.setattr(agent_module, "build_model", lambda: object())

    def failing_build_tool():
        raise original

    monkeypatch.setattr(agent_module, "build_web_search_tool", failing_build_tool)
    monkeypatch.setattr(
        agent_module,
        "create_deep_agent",
        lambda **kwargs: pytest.fail("create_deep_agent should not run"),
    )

    with pytest.raises(ToolInitializationError) as excinfo:
        agent_module.build_research_agent()

    assert excinfo.value is original
