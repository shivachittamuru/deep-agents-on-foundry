"""Tests for text streaming (fake agent, no live calls)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from deep_agents_foundry.streaming import astream_research_text, stream_research_text


def chunk(blocks):
    return SimpleNamespace(content_blocks=blocks)


def text_block(text):
    return {"type": "text", "text": text}


class FakeAgent:
    def __init__(self, parts):
        self._parts = parts
        self.calls = []

    def stream(self, payload, config=None, *, stream_mode=None, version=None):
        self.calls.append(
            {
                "payload": payload,
                "config": config,
                "stream_mode": stream_mode,
                "version": version,
            }
        )
        yield from self._parts


def test_stream_research_text_dict_envelope():
    agent = FakeAgent(
        [
            {"type": "messages", "data": (chunk([text_block("Hello ")]), {})},
            {"type": "updates", "data": {"model": {}}},
            {"type": "messages", "data": (chunk([text_block("world")]), {})},
            {"type": "messages", "data": (chunk([{"type": "tool_call"}]), {})},
        ]
    )

    deltas = list(stream_research_text(agent, "q"))

    assert deltas == ["Hello ", "world"]
    assert "".join(deltas) == "Hello world"


def test_stream_research_text_uses_expected_stream_arguments():
    agent = FakeAgent([])

    list(stream_research_text(agent, "explain X"))

    call = agent.calls[0]
    assert call["payload"] == {
        "messages": [{"role": "user", "content": "explain X"}]
    }
    assert call["stream_mode"] == "messages"
    assert call["version"] == "v2"


def test_stream_research_text_forwards_config():
    agent = FakeAgent([])
    config = {"configurable": {"thread_id": "t-1"}}

    list(stream_research_text(agent, "q", config=config))

    assert agent.calls[0]["config"] == config


def test_stream_research_text_tolerates_tuple_envelope():
    agent = FakeAgent([(chunk([text_block("Hi")]), {})])

    assert list(stream_research_text(agent, "q")) == ["Hi"]


def test_stream_research_text_skips_empty_text():
    agent = FakeAgent(
        [
            {"type": "messages", "data": (chunk([]), {})},
            {"type": "messages", "data": (chunk([text_block("only")]), {})},
        ]
    )

    assert list(stream_research_text(agent, "q")) == ["only"]


class AsyncFakeAgent:
    def __init__(self, parts):
        self._parts = parts
        self.calls = []

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
        for part in self._parts:
            yield part


async def _collect(async_iter):
    return [item async for item in async_iter]


def test_astream_research_text_yields_text_in_order():
    agent = AsyncFakeAgent(
        [
            {"type": "messages", "data": (chunk([text_block("Hello ")]), {})},
            {"type": "messages", "data": (chunk([text_block("world")]), {})},
        ]
    )

    deltas = asyncio.run(_collect(astream_research_text(agent, "q")))

    assert deltas == ["Hello ", "world"]


def test_astream_research_text_ignores_non_text_and_empty_blocks():
    agent = AsyncFakeAgent(
        [
            {"type": "messages", "data": (chunk([{"type": "tool_call"}]), {})},
            {"type": "messages", "data": (chunk([]), {})},
            {"type": "messages", "data": (chunk([text_block("kept")]), {})},
        ]
    )

    deltas = asyncio.run(_collect(astream_research_text(agent, "q")))

    assert deltas == ["kept"]


def test_astream_research_text_uses_expected_arguments_and_forwards_config():
    agent = AsyncFakeAgent([])
    config = {"configurable": {"thread_id": "t-1"}}

    asyncio.run(_collect(astream_research_text(agent, "explain X", config=config)))

    call = agent.calls[0]
    assert call["payload"] == {
        "messages": [{"role": "user", "content": "explain X"}]
    }
    assert call["stream_mode"] == "messages"
    assert call["version"] == "v2"
    assert call["config"] == config
