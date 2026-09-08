"""Tests for research agent construction (dependencies mocked, no live calls)."""

from __future__ import annotations

from deep_agents_foundry import agent as agent_module


def test_build_research_agent_wires_model_tools_and_prompt(monkeypatch):
    captured = {}
    sentinel_model = object()
    sentinel_tool = object()
    sentinel_agent = object()

    monkeypatch.setattr(agent_module, "build_model", lambda: sentinel_model)
    monkeypatch.setattr(
        agent_module, "build_web_search_tool", lambda: sentinel_tool
    )
    monkeypatch.setattr(
        agent_module,
        "create_deep_agent",
        lambda **kwargs: captured.update(kwargs) or sentinel_agent,
    )

    result = agent_module.build_research_agent()

    assert result is sentinel_agent
    assert captured["model"] is sentinel_model
    assert captured["tools"] == [sentinel_tool]
    assert captured["system_prompt"] == agent_module.RESEARCH_INSTRUCTIONS


def test_research_instructions_capture_notebook_behavior():
    instructions = agent_module.RESEARCH_INSTRUCTIONS

    assert "expert research assistant" in instructions
    assert "Use web search" in instructions
    assert "citations" in instructions
