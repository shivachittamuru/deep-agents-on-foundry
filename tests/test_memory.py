"""Tests for long-term user memory (InMemoryStore + fake models, no live calls)."""

from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.store.memory import InMemoryStore

from deep_agents_foundry import agent as agent_module
from deep_agents_foundry.agent import RESEARCH_INSTRUCTIONS, build_research_agent
from deep_agents_foundry.errors import ConfigurationError
from deep_agents_foundry.memory import (
    MEMORY_POLICY,
    ResearchContext,
    preferences_namespace,
    recall_research_preferences,
    remember_research_preference,
)
from deep_agents_foundry.persistence import thread_config


class _FakeToolCallingModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


@tool
def _noop_search(query: str) -> str:
    """Test-only stand-in for web search."""
    return "no-op"


def _patch(monkeypatch, messages):
    monkeypatch.setattr(
        agent_module,
        "build_model",
        lambda: _FakeToolCallingModel(messages=iter(messages)),
    )
    monkeypatch.setattr(agent_module, "build_web_search_tool", lambda: _noop_search)


def _remember_msgs(preference):
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "remember_research_preference",
                    "args": {"preference": preference},
                    "id": "call_1",
                }
            ],
        ),
        AIMessage(content="Noted."),
    ]


def _recall_msgs():
    return [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "recall_research_preferences", "args": {}, "id": "call_1"}
            ],
        ),
        AIMessage(content="Here are your preferences."),
    ]


def _recall_tool_output(result):
    for message in result["messages"]:
        if (
            isinstance(message, ToolMessage)
            and message.name == "recall_research_preferences"
        ):
            return str(message.content)
    return None


# --- 1. ResearchContext validation -----------------------------------------


def test_research_context_valid():
    assert ResearchContext(user_id="user-a").user_id == "user-a"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_research_context_rejects_blank(value):
    with pytest.raises(ConfigurationError):
        ResearchContext(user_id=value)


# --- 2. Namespace isolation -------------------------------------------------


def test_preferences_namespace_shape_and_isolation():
    assert preferences_namespace("user-a") == (
        "users",
        "user-a",
        "research_preferences",
    )
    assert preferences_namespace("user-a") != preferences_namespace("user-b")


@pytest.mark.parametrize("value", ["", "   "])
def test_preferences_namespace_rejects_blank(value):
    with pytest.raises(ConfigurationError):
        preferences_namespace(value)


def test_remember_tool_does_not_expose_user_id_to_llm():
    # The LLM may only supply `preference`; user_id comes from runtime context.
    assert "preference" in remember_research_preference.args
    assert "user_id" not in remember_research_preference.args
    assert "user_id" not in recall_research_preferences.args


# --- 3 & 4. Explicit write goes only to the user's namespace ----------------


def test_explicit_write_saves_only_under_user_namespace(monkeypatch):
    store = InMemoryStore()
    _patch(monkeypatch, _remember_msgs("always cite primary sources"))

    agent = build_research_agent(store=store)
    agent.invoke(
        {"messages": [{"role": "user", "content": "remember: cite primary sources"}]},
        context=ResearchContext(user_id="user-a"),
    )

    saved = [i.value["preference"] for i in store.search(preferences_namespace("user-a"))]
    assert saved == ["always cite primary sources"]
    # Nothing leaks into another user's namespace.
    assert store.search(preferences_namespace("user-b")) == []


# --- 5. Cross-thread recall for the same user -------------------------------


def test_cross_thread_recall_same_user(monkeypatch):
    store = InMemoryStore()
    context = ResearchContext(user_id="user-a")

    _patch(monkeypatch, _remember_msgs("prefer concise executive summaries"))
    writer = build_research_agent(store=store)
    writer.invoke(
        {"messages": [{"role": "user", "content": "remember this"}]},
        context=context,
        config=thread_config("thread-1"),
    )

    # A different conversation/thread; same user + same store.
    _patch(monkeypatch, _recall_msgs())
    reader = build_research_agent(store=store)
    result = reader.invoke(
        {"messages": [{"role": "user", "content": "what are my preferences?"}]},
        context=context,
        config=thread_config("thread-2"),
    )

    assert "prefer concise executive summaries" in _recall_tool_output(result)


# --- 6. User isolation ------------------------------------------------------


def test_preferences_are_isolated_between_users(monkeypatch):
    store = InMemoryStore()

    _patch(monkeypatch, _remember_msgs("use IEEE citation style"))
    build_research_agent(store=store).invoke(
        {"messages": [{"role": "user", "content": "remember"}]},
        context=ResearchContext(user_id="user-a"),
        config=thread_config("thread-1"),
    )

    # A different user cannot see user-a's preference.
    _patch(monkeypatch, _recall_msgs())
    other = build_research_agent(store=store).invoke(
        {"messages": [{"role": "user", "content": "my prefs?"}]},
        context=ResearchContext(user_id="user-b"),
        config=thread_config("thread-9"),
    )
    assert _recall_tool_output(other) == "No saved research preferences."

    # user-a from yet another thread still can.
    _patch(monkeypatch, _recall_msgs())
    again = build_research_agent(store=store).invoke(
        {"messages": [{"role": "user", "content": "my prefs?"}]},
        context=ResearchContext(user_id="user-a"),
        config=thread_config("thread-3"),
    )
    assert "use IEEE citation style" in _recall_tool_output(again)


# --- 7. No accidental memory creation ---------------------------------------


def test_ordinary_research_does_not_write_memory(monkeypatch):
    store = InMemoryStore()
    _patch(monkeypatch, [AIMessage(content="Here is a normal research answer.")])

    build_research_agent(store=store).invoke(
        {"messages": [{"role": "user", "content": "what is a Hosted Agent?"}]},
        context=ResearchContext(user_id="user-a"),
    )

    assert store.search(preferences_namespace("user-a")) == []


# --- 8. Builder backward compatibility (no Store) ---------------------------


def test_builder_without_store_is_unchanged(monkeypatch):
    captured = {}
    monkeypatch.setattr(agent_module, "build_model", lambda: "MODEL")
    monkeypatch.setattr(agent_module, "build_web_search_tool", lambda: "WEB_SEARCH")
    monkeypatch.setattr(
        agent_module,
        "create_deep_agent",
        lambda **kwargs: captured.update(kwargs) or object(),
    )

    build_research_agent()

    assert captured["tools"] == ["WEB_SEARCH"]
    assert captured["system_prompt"] == RESEARCH_INSTRUCTIONS
    assert "store" not in captured
    assert "context_schema" not in captured


# --- 9. Builder with Store --------------------------------------------------


def test_builder_with_store_wires_memory(monkeypatch):
    captured = {}
    sentinel_store = InMemoryStore()
    monkeypatch.setattr(agent_module, "build_model", lambda: "MODEL")
    monkeypatch.setattr(agent_module, "build_web_search_tool", lambda: "WEB_SEARCH")
    monkeypatch.setattr(
        agent_module,
        "create_deep_agent",
        lambda **kwargs: captured.update(kwargs) or object(),
    )

    build_research_agent(store=sentinel_store)

    assert captured["store"] is sentinel_store
    assert captured["context_schema"] is ResearchContext
    # Existing web search remains, plus the two memory tools.
    assert captured["tools"][0] == "WEB_SEARCH"
    assert remember_research_preference in captured["tools"]
    assert recall_research_preferences in captured["tools"]
    assert MEMORY_POLICY in captured["system_prompt"]
    assert captured["system_prompt"].startswith(RESEARCH_INSTRUCTIONS)
