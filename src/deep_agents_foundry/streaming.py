"""Text streaming for the research agent (promoted from notebook 06).

Isolates the version-sensitive LangGraph streaming envelope behind a single
function that yields plain-text deltas.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

from .content import content_text


def _message_chunk(part):
    """Pull the message chunk out of a stream part, tolerating envelope shapes."""
    if isinstance(part, dict):
        if part.get("type") != "messages":
            return None
        data = part.get("data")
    else:
        # Standard LangGraph (message_chunk, metadata) tuple.
        data = part

    if isinstance(data, (tuple, list)) and data:
        return data[0]
    return data


def stream_research_text(agent, user_input: str, *, config=None) -> Iterator[str]:
    """Yield plain-text deltas as the agent streams its response.

    Only text is emitted; agent-step updates and non-text blocks are skipped.
    """
    for part in agent.stream(
        {"messages": [{"role": "user", "content": user_input}]},
        config=config,
        stream_mode="messages",
        version="v2",
    ):
        chunk = _message_chunk(part)
        if chunk is None:
            continue

        text = content_text(chunk)
        if text:
            yield text


async def astream_research_text(
    agent, user_input: str, *, config=None, context=None
) -> AsyncIterator[str]:
    """Async counterpart of `stream_research_text` using `agent.astream(...)`.

    `context` carries the trusted runtime context (e.g. `ResearchContext` for
    long-term memory). Only user-visible text deltas are emitted; agent-step
    updates and non-text blocks are skipped.
    """
    async for part in agent.astream(
        {"messages": [{"role": "user", "content": user_input}]},
        config=config,
        context=context,
        stream_mode="messages",
        version="v2",
    ):
        chunk = _message_chunk(part)
        if chunk is None:
            continue

        text = content_text(chunk)
        if text:
            yield text
