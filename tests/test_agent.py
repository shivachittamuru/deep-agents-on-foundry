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


def test_build_research_agent_omits_checkpointer_by_default(monkeypatch):
    captured = {}

    monkeypatch.setattr(agent_module, "build_model", lambda: object())
    monkeypatch.setattr(agent_module, "build_web_search_tool", lambda: object())
    monkeypatch.setattr(
        agent_module,
        "create_deep_agent",
        lambda **kwargs: captured.update(kwargs) or object(),
    )

    agent_module.build_research_agent()

    assert "checkpointer" not in captured
    assert "interrupt_on" not in captured


def test_build_research_agent_forwards_checkpointer(monkeypatch):
    captured = {}
    sentinel_checkpointer = object()

    monkeypatch.setattr(agent_module, "build_model", lambda: object())
    monkeypatch.setattr(agent_module, "build_web_search_tool", lambda: object())
    monkeypatch.setattr(
        agent_module,
        "create_deep_agent",
        lambda **kwargs: captured.update(kwargs) or object(),
    )

    agent_module.build_research_agent(checkpointer=sentinel_checkpointer)

    assert captured["checkpointer"] is sentinel_checkpointer


def test_build_research_agent_forwards_interrupt_on(monkeypatch):
    captured = {}
    interrupt_config = {"web_search": True}

    monkeypatch.setattr(agent_module, "build_model", lambda: object())
    monkeypatch.setattr(agent_module, "build_web_search_tool", lambda: object())
    monkeypatch.setattr(
        agent_module,
        "create_deep_agent",
        lambda **kwargs: captured.update(kwargs) or object(),
    )

    agent_module.build_research_agent(interrupt_on=interrupt_config)

    assert captured["interrupt_on"] is interrupt_config


def test_research_instructions_capture_notebook_behavior():
    instructions = agent_module.RESEARCH_INSTRUCTIONS

    assert "expert research assistant" in instructions
    assert "Use web search" in instructions
    assert "citations" in instructions
