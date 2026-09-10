"""Tests for the Hosted Agent handler (mocked SDK/agent, no live calls)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest import mock

from deep_agents_foundry import hosting
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

    async def astream(self, payload, config=None, *, stream_mode=None, version=None):
        self.calls.append(
            {
                "payload": payload,
                "config": config,
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
    def __init__(self, input_text):
        self._input_text = input_text
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


def test_create_host_registers_handler_without_eager_agent_build(monkeypatch):
    calls = {"checkpointer": 0, "agent": 0}
    registered = {}

    monkeypatch.setattr(
        hosting,
        "build_async_sqlite_checkpointer",
        lambda path: calls.__setitem__("checkpointer", calls["checkpointer"] + 1),
    )
    monkeypatch.setattr(
        hosting,
        "build_research_agent",
        lambda **kwargs: calls.__setitem__("agent", calls["agent"] + 1),
    )

    class FakeHost:
        def response_handler(self, fn):
            registered["fn"] = fn
            return fn

    monkeypatch.setattr(hosting, "ResponsesAgentServerHost", FakeHost)

    app = hosting.create_host()

    assert isinstance(app, FakeHost)
    assert "fn" in registered
    # The agent/checkpointer are built lazily (need an event loop), not eagerly.
    assert calls == {"checkpointer": 0, "agent": 0}


def test_get_agent_builds_once(monkeypatch):
    monkeypatch.setattr(hosting, "_agent_singleton", None)
    calls = {"checkpointer": 0, "agent": 0}
    captured = {}

    def fake_checkpointer(path):
        calls["checkpointer"] += 1
        return "CHECKPOINTER"

    def fake_build_agent(*, checkpointer=None):
        calls["agent"] += 1
        captured["checkpointer"] = checkpointer
        return "AGENT"

    monkeypatch.setattr(hosting, "build_async_sqlite_checkpointer", fake_checkpointer)
    monkeypatch.setattr(hosting, "build_research_agent", fake_build_agent)

    async def run():
        return await hosting._get_agent(), await hosting._get_agent()

    first, second = asyncio.run(run())

    assert first == "AGENT"
    assert second == "AGENT"
    # Built exactly once across multiple requests; persistent, with the checkpointer.
    assert calls == {"checkpointer": 1, "agent": 1}
    assert captured["checkpointer"] == "CHECKPOINTER"


def test_resolve_thread_id_from_metadata():
    request = {"metadata": {"thread_id": "app-thread-42"}}

    assert hosting._resolve_thread_id(request) == "app-thread-42"


def test_resolve_thread_id_falls_back_when_missing_or_blank():
    assert hosting._resolve_thread_id({}) == hosting.DEFAULT_THREAD_ID
    assert hosting._resolve_thread_id({"metadata": {}}) == hosting.DEFAULT_THREAD_ID
    assert (
        hosting._resolve_thread_id({"metadata": {"thread_id": "  "}})
        == hosting.DEFAULT_THREAD_ID
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
