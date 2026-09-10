"""Durable Deep Agent state + native HITL tests (deterministic, no live calls).

These exercise the real `create_deep_agent` LangGraph runtime, SQLite
checkpointer, and native Human-in-the-Loop middleware. Only the model and tool
are faked so no Azure/Foundry/model calls occur. No Foundry Responses history is
involved — durability comes entirely from LangGraph checkpoints.
"""

from __future__ import annotations

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command

from deep_agents_foundry import agent as agent_module
from deep_agents_foundry.agent import build_research_agent
from deep_agents_foundry.persistence import build_sqlite_checkpointer, thread_config


class _FakeToolCallingModel(GenericFakeChatModel):
    """Fake chat model that returns queued messages and accepts tool binding."""

    def bind_tools(self, tools, **kwargs):
        return self


@tool
def _echo(text: str) -> str:
    """Echo text back (test-only tool, not part of the production toolset)."""
    return f"ECHO: {text}"


def _patch_agent(monkeypatch, messages):
    """Inject a fresh fake model (per build) and the harmless echo tool."""
    monkeypatch.setattr(
        agent_module,
        "build_model",
        lambda: _FakeToolCallingModel(messages=iter(messages)),
    )
    monkeypatch.setattr(agent_module, "build_web_search_tool", lambda: _echo)


def _message_count(agent, config) -> int:
    return len(agent.get_state(config).values["messages"])


def test_same_thread_restores_prior_state(tmp_path, monkeypatch):
    _patch_agent(monkeypatch, [AIMessage(content="first"), AIMessage(content="second")])

    checkpointer = build_sqlite_checkpointer(tmp_path / "threads.db")
    agent = build_research_agent(checkpointer=checkpointer)
    config = thread_config("thread-1")

    agent.invoke({"messages": [{"role": "user", "content": "hello"}]}, config=config)
    after_first = _message_count(agent, config)

    agent.invoke({"messages": [{"role": "user", "content": "again"}]}, config=config)
    after_second = _message_count(agent, config)

    assert after_first == 2
    assert after_second == 4  # prior turn was restored and extended


def test_different_thread_is_isolated(tmp_path, monkeypatch):
    _patch_agent(monkeypatch, [AIMessage(content="answer")])

    checkpointer = build_sqlite_checkpointer(tmp_path / "threads.db")
    agent = build_research_agent(checkpointer=checkpointer)

    agent.invoke(
        {"messages": [{"role": "user", "content": "hello"}]},
        config=thread_config("thread-1"),
    )

    other = agent.get_state(thread_config("thread-2")).values
    assert not other.get("messages")


def test_state_survives_agent_reconstruction(tmp_path, monkeypatch):
    db_path = tmp_path / "recon.db"
    config = thread_config("thread-X")

    # First agent instance writes state, then is discarded.
    _patch_agent(monkeypatch, [AIMessage(content="first")])
    agent_a = build_research_agent(checkpointer=build_sqlite_checkpointer(db_path))
    agent_a.invoke(
        {"messages": [{"role": "user", "content": "hello"}]}, config=config
    )
    assert _message_count(agent_a, config) == 2
    del agent_a

    # A brand-new agent on the same SQLite DB restores the prior thread state.
    _patch_agent(monkeypatch, [AIMessage(content="second")])
    agent_b = build_research_agent(checkpointer=build_sqlite_checkpointer(db_path))

    assert _message_count(agent_b, config) == 2  # restored from disk, not memory

    agent_b.invoke(
        {"messages": [{"role": "user", "content": "again"}]}, config=config
    )
    assert _message_count(agent_b, config) == 4


def _echo_then_done():
    return [
        AIMessage(
            content="",
            tool_calls=[{"name": "_echo", "args": {"text": "hi"}, "id": "call_1"}],
        ),
        AIMessage(content="done"),
    ]


def _echo_tool_messages(messages):
    return [m for m in messages if isinstance(m, ToolMessage) and m.content == "ECHO: hi"]


def test_native_hitl_interrupts_before_tool(tmp_path, monkeypatch):
    _patch_agent(monkeypatch, _echo_then_done())

    checkpointer = build_sqlite_checkpointer(tmp_path / "hitl.db")
    agent = build_research_agent(
        checkpointer=checkpointer, interrupt_on={"_echo": True}
    )
    config = thread_config("hitl-1")

    result = agent.invoke(
        {"messages": [{"role": "user", "content": "please echo"}]}, config=config
    )

    assert "__interrupt__" in result
    assert agent.get_state(config).next  # paused, work remaining
    # Tool has not executed yet; its result is not in state.
    assert _echo_tool_messages(agent.get_state(config).values["messages"]) == []


def test_native_hitl_resume_runs_tool_exactly_once(tmp_path, monkeypatch):
    _patch_agent(monkeypatch, _echo_then_done())

    checkpointer = build_sqlite_checkpointer(tmp_path / "hitl.db")
    agent = build_research_agent(
        checkpointer=checkpointer, interrupt_on={"_echo": True}
    )
    config = thread_config("hitl-2")

    agent.invoke(
        {"messages": [{"role": "user", "content": "please echo"}]}, config=config
    )

    resumed = agent.invoke(
        Command(resume={"decisions": [{"type": "approve"}]}), config=config
    )

    assert resumed["messages"][-1].content == "done"
    assert agent.get_state(config).next == ()  # completed
    # Resume continues from checkpoint; the tool runs once, not twice.
    assert len(_echo_tool_messages(resumed["messages"])) == 1
