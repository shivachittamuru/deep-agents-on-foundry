"""Tests for the Hosted Agent handler (mocked SDK/agent, no live calls)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest import mock

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.store.memory import InMemoryStore

from deep_agents_foundry import agent as agent_module
from deep_agents_foundry import hosting
from deep_agents_foundry.agent import build_research_agent
from deep_agents_foundry.memory import ResearchContext, preferences_namespace
from deep_agents_foundry.persistence import thread_config


class _RecordingTextResponse:
    """Stand-in for the SDK TextResponse that records the text it was given."""

    def __init__(self, context, request, *, text):
        self.context = context
        self.request = request
        self.text = text


class _FakeAgent:
    """Fake agent exposing async `astream` and sync `get_state`."""

    def __init__(self, parts, next_state=()):
        self.parts = parts
        self.calls = []
        self.aget_state_calls = []
        self._next = next_state

    async def astream(self, payload, config=None, *, context=None, stream_mode=None, version=None):
        self.calls.append(
            {
                "payload": payload,
                "config": config,
                "context": context,
                "stream_mode": stream_mode,
                "version": version,
            }
        )
        for part in self.parts:
            yield part

    async def aget_state(self, config):
        self.aget_state_calls.append(config)
        return SimpleNamespace(next=self._next)


class _FakeContext:
    def __init__(self, input_text, conversation_chain_id="conv-1"):
        self._input_text = input_text
        self.conversation_chain_id = conversation_chain_id
        self.get_history = mock.Mock()  # must never be called

    async def get_input_text(self):
        return self._input_text


def _text_part(text):
    chunk = SimpleNamespace(content_blocks=[{"type": "text", "text": text}])
    return {"type": "messages", "data": (chunk, {})}


async def _collect_text(source):
    if isinstance(source, str):
        return source
    return "".join([chunk async for chunk in source])


def _run_collect(agent, request, context):
    async def _go():
        response = await hosting._handle_response(agent, request, context)
        return response, await _collect_text(response.text)

    return asyncio.run(_go())


class _FakePersistence:
    """Fake PostgresPersistence recording open/close and exposing saver/store."""

    def __init__(self):
        self.opened = 0
        self.closed = 0
        self.checkpointer = "PG_CHECKPOINTER"
        self.store = "PG_STORE"

    async def open(self):
        self.opened += 1

    async def close(self):
        self.closed += 1


def test_create_host_registers_handlers_without_eager_build(monkeypatch):
    built = {"agent": 0, "persistence": 0}
    registered = {}

    monkeypatch.setattr(
        hosting,
        "build_research_agent",
        lambda **kwargs: built.__setitem__("agent", built["agent"] + 1),
    )

    class _CountingPersistence(_FakePersistence):
        def __init__(self):
            super().__init__()
            built["persistence"] += 1

    monkeypatch.setattr(hosting, "PostgresPersistence", _CountingPersistence)

    class FakeHost:
        def response_handler(self, fn):
            registered["response"] = fn
            return fn

        def shutdown_handler(self, fn):
            registered["shutdown"] = fn
            return fn

    monkeypatch.setattr(hosting, "ResponsesAgentServerHost", FakeHost)

    app = hosting.create_host()

    assert isinstance(app, FakeHost)
    assert "response" in registered
    assert "shutdown" in registered
    # Nothing is built eagerly (persistence needs a running event loop).
    assert built == {"agent": 0, "persistence": 0}


def test_get_agent_builds_persistence_and_agent_once(monkeypatch):
    monkeypatch.setattr(hosting, "_agent_singleton", None)
    monkeypatch.setattr(hosting, "_persistence", None)
    instances = []

    def make_persistence():
        persistence = _FakePersistence()
        instances.append(persistence)
        return persistence

    captured = {}

    def fake_build_agent(*, checkpointer=None, store=None, skills=None):
        captured.update(checkpointer=checkpointer, store=store, skills=skills)
        return "AGENT"

    monkeypatch.setattr(hosting, "PostgresPersistence", make_persistence)
    monkeypatch.setattr(hosting, "build_research_agent", fake_build_agent)

    async def run():
        return await hosting._get_agent(), await hosting._get_agent()

    first, second = asyncio.run(run())

    assert first == "AGENT"
    assert second == "AGENT"
    # Persistence built and opened exactly once across requests.
    assert len(instances) == 1
    assert instances[0].opened == 1
    # AsyncPostgresSaver + AsyncPostgresStore + Skills wired into the agent.
    assert captured["checkpointer"] == "PG_CHECKPOINTER"
    assert captured["store"] == "PG_STORE"
    assert captured["skills"] == hosting.DEFAULT_SKILL_SOURCES


def test_close_persistence_closes_pool_and_resets(monkeypatch):
    persistence = _FakePersistence()
    monkeypatch.setattr(hosting, "_persistence", persistence)
    monkeypatch.setattr(hosting, "_agent_singleton", "AGENT")

    asyncio.run(hosting._close_persistence())

    assert persistence.closed == 1
    assert hosting._persistence is None
    assert hosting._agent_singleton is None


def test_resolve_thread_id_from_metadata():
    request = {"metadata": {"thread_id": "app-thread-42"}}

    assert hosting._resolve_thread_id(request, _FakeContext("q")) == "app-thread-42"


def test_resolve_thread_id_falls_back_to_conversation_chain():
    context = _FakeContext("q", conversation_chain_id="abc123")

    assert hosting._resolve_thread_id({}, context) == "thread-abc123"
    assert (
        hosting._resolve_thread_id({"metadata": {"thread_id": "  "}}, context)
        == "thread-abc123"
    )


def test_handle_response_streams_text_and_passes_thread_config(monkeypatch):
    monkeypatch.setattr(hosting, "TextResponse", _RecordingTextResponse)
    agent = _FakeAgent([_text_part("Hello "), _text_part("world")])
    request = {"metadata": {"thread_id": "T1"}}

    _, text = _run_collect(agent, request, _FakeContext("what is X?"))

    assert agent.calls[0]["config"] == thread_config("T1")
    assert agent.calls[0]["payload"] == {
        "messages": [{"role": "user", "content": "what is X?"}]
    }
    assert text == "Hello world"


def test_handle_response_uses_content_text_extraction(monkeypatch):
    monkeypatch.setattr(hosting, "TextResponse", _RecordingTextResponse)
    part = {
        "type": "messages",
        "data": (
            SimpleNamespace(
                content_blocks=[{"type": "text", "text": "X"}, {"type": "tool_call"}]
            ),
            {},
        ),
    }
    agent = _FakeAgent([part])

    _, text = _run_collect(agent, {"metadata": {"thread_id": "T1"}}, _FakeContext("q"))

    assert text == "X"


def test_same_thread_id_routes_to_same_thread(monkeypatch):
    monkeypatch.setattr(hosting, "TextResponse", _RecordingTextResponse)
    agent = _FakeAgent([_text_part("ok")])
    request = {"metadata": {"thread_id": "same"}}

    _run_collect(agent, request, _FakeContext("first"))
    _run_collect(agent, request, _FakeContext("second"))

    assert agent.calls[0]["config"] == agent.calls[1]["config"] == thread_config("same")


def test_different_thread_ids_remain_distinct(monkeypatch):
    monkeypatch.setattr(hosting, "TextResponse", _RecordingTextResponse)
    agent = _FakeAgent([_text_part("ok")])

    _run_collect(agent, {"metadata": {"thread_id": "A"}}, _FakeContext("x"))
    _run_collect(agent, {"metadata": {"thread_id": "B"}}, _FakeContext("y"))

    assert agent.calls[0]["config"] == thread_config("A")
    assert agent.calls[1]["config"] == thread_config("B")
    assert agent.calls[0]["config"] != agent.calls[1]["config"]


def test_handle_response_does_not_hydrate_responses_history(monkeypatch):
    monkeypatch.setattr(hosting, "TextResponse", _RecordingTextResponse)
    agent = _FakeAgent([_text_part("ok")])
    context = _FakeContext("q")

    _run_collect(agent, {"metadata": {"thread_id": "T1"}}, context)

    context.get_history.assert_not_called()


def test_empty_input_short_circuits(monkeypatch):
    monkeypatch.setattr(hosting, "TextResponse", _RecordingTextResponse)
    agent = _FakeAgent([_text_part("unused")])

    response, text = _run_collect(
        agent, {"metadata": {"thread_id": "T1"}}, _FakeContext("   ")
    )

    assert text == hosting._EMPTY_INPUT_MESSAGE
    assert agent.calls == []  # agent not streamed on empty input
    assert agent.aget_state_calls == []


def test_native_interrupt_surfaces_approval_without_losing_checkpoint(monkeypatch):
    monkeypatch.setattr(hosting, "TextResponse", _RecordingTextResponse)
    # No text is produced; the run pauses on a native interrupt (state.next set).
    agent = _FakeAgent([], next_state=("HumanInTheLoopMiddleware.after_model",))
    config = thread_config("T1")

    _, text = _run_collect(agent, {"metadata": {"thread_id": "T1"}}, _FakeContext("go"))

    assert text == hosting._APPROVAL_REQUIRED_MESSAGE
    # The checkpoint was inspected (not discarded) under the same thread.
    assert agent.aget_state_calls == [config]


# --- P8B.5: user_id / memory identity ---------------------------------------


def test_resolve_user_id_from_metadata():
    request = {"metadata": {"user_id": "user-a", "thread_id": "t1"}}

    assert hosting._resolve_user_id(request) == "user-a"


def test_resolve_user_id_missing_or_blank_uses_default(monkeypatch):
    monkeypatch.delenv(hosting.DEFAULT_USER_ID_ENV, raising=False)
    assert hosting._resolve_user_id({}) == hosting.DEFAULT_USER_ID
    assert hosting._resolve_user_id({"metadata": {}}) == hosting.DEFAULT_USER_ID
    assert (
        hosting._resolve_user_id({"metadata": {"user_id": "   "}})
        == hosting.DEFAULT_USER_ID
    )


def test_handle_response_passes_research_context_with_user_id(monkeypatch):
    monkeypatch.setattr(hosting, "TextResponse", _RecordingTextResponse)
    agent = _FakeAgent([_text_part("ok")])
    request = {"metadata": {"thread_id": "t1", "user_id": "user-a"}}

    _run_collect(agent, request, _FakeContext("hello"))

    # thread_id and user_id stay separate identities.
    assert agent.calls[0]["config"] == thread_config("t1")
    assert agent.calls[0]["context"].user_id == "user-a"


def test_handle_response_without_user_id_uses_default_context(monkeypatch):
    monkeypatch.setattr(hosting, "TextResponse", _RecordingTextResponse)
    monkeypatch.delenv(hosting.DEFAULT_USER_ID_ENV, raising=False)
    agent = _FakeAgent([_text_part("ok")])

    _run_collect(agent, {"metadata": {"thread_id": "t1"}}, _FakeContext("hello"))

    assert agent.calls[0]["context"].user_id == hosting.DEFAULT_USER_ID


def test_skills_are_discoverable_from_hosted_runtime():
    from deep_agents_foundry.skills import list_available_skills, skills_available

    assert skills_available() is True
    names = {s.get("name") for s in list_available_skills()}
    assert "technology-research" in names


# --- P8B.5: hosted metadata.user_id drives long-term memory -----------------


class _FakeToolCallingModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


@tool
def _noop_search(query: str) -> str:
    """Test-only stand-in for web search."""
    return "no-op"


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


def test_hosted_user_id_routes_memory_and_isolates_users(monkeypatch):
    # Exercises metadata.user_id -> ResearchContext -> user-scoped Store memory.
    # Uses invoke (not the streaming handler) because a fake tool-calling model
    # cannot stream tool-call turns; the real Foundry model streams them fine.
    store = InMemoryStore()

    def patch_model(preference):
        monkeypatch.setattr(
            agent_module,
            "build_model",
            lambda: _FakeToolCallingModel(messages=iter(_remember_msgs(preference))),
        )
        monkeypatch.setattr(agent_module, "build_web_search_tool", lambda: _noop_search)

    request_a = {"metadata": {"user_id": "user-a", "thread_id": "t1"}}
    user_id = hosting._resolve_user_id(request_a)

    patch_model("cite primary sources")
    build_research_agent(store=store).invoke(
        {"messages": [{"role": "user", "content": "remember"}]},
        context=ResearchContext(user_id=user_id),
        config=thread_config(hosting._resolve_thread_id(request_a, _FakeContext("x"))),
    )

    assert [
        i.value["preference"]
        for i in store.search(preferences_namespace("user-a"))
    ] == ["cite primary sources"]
    # Another user cannot see it.
    assert store.search(preferences_namespace("user-b")) == []

    # Same user, a different thread, same process Store -> shared memory.
    patch_model("prefer concise summaries")
    build_research_agent(store=store).invoke(
        {"messages": [{"role": "user", "content": "remember"}]},
        context=ResearchContext(user_id="user-a"),
        config=thread_config("t2"),
    )
    assert len(store.search(preferences_namespace("user-a"))) == 2
