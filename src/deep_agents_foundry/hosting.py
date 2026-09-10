"""Foundry Hosted Agent handler backed by one persistent Deep Agent (SQLite).

Durability lives in LangGraph checkpoints keyed by an application-level
`thread_id`. Foundry `session_id`/conversation identity is intentionally NOT used
as the permanent thread id, and Responses conversation history is never hydrated
into LangGraph (`context.get_history()` is deliberately not called).

SQLite is development-only persistence for this learning project.
"""

import asyncio
import os
import tempfile
from pathlib import Path

from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponsesAgentServerHost,
    TextResponse,
)

from .agent import build_research_agent
from .persistence import build_async_sqlite_checkpointer, thread_config
from .streaming import astream_research_text

# Client-supplied metadata key that carries the durable application thread id.
THREAD_ID_METADATA_KEY = "thread_id"

# Fallback when no thread_id is supplied: a single shared dev thread. This keeps
# multi-turn continuity working locally; clients should send
# metadata["thread_id"] to isolate distinct threads.
DEFAULT_THREAD_ID = "default"

# Env var pointing at the dev SQLite database (created once per process).
SQLITE_PATH_ENV = "DEEP_AGENTS_SQLITE_PATH"

# Default under the OS temp dir: the hosted container's app directory is
# read-only, so a relative path there fails with "readonly database". Temp
# storage is ephemeral (threads reset on restart); set DEEP_AGENTS_SQLITE_PATH to
# a writable persistent volume to keep threads across restarts.
DEFAULT_SQLITE_PATH = str(
    Path(tempfile.gettempdir()) / "deep_agents_foundry" / "hosted_agent.db"
)

_APPROVAL_REQUIRED_MESSAGE = (
    "This action requires approval before it can continue. The run has been "
    "paused and its state saved under this thread; it can be resumed once "
    "client-driven approval is wired up."
)

_EMPTY_INPUT_MESSAGE = "Please provide a research question."


def _sqlite_path() -> str:
    return os.environ.get(SQLITE_PATH_ENV, DEFAULT_SQLITE_PATH)


# Built lazily on first request: AsyncSqliteSaver binds to the running event loop
# at construction, which is not available when create_host() runs.
_agent_singleton = None
_agent_lock = asyncio.Lock()


async def _get_agent():
    """Return the process-wide persistent Deep Agent, building it once."""
    global _agent_singleton
    if _agent_singleton is None:
        async with _agent_lock:
            if _agent_singleton is None:
                checkpointer = build_async_sqlite_checkpointer(Path(_sqlite_path()))
                _agent_singleton = build_research_agent(checkpointer=checkpointer)
    return _agent_singleton


def _resolve_thread_id(request: CreateResponse) -> str:
    """Resolve the durable LangGraph thread id from client-supplied metadata."""
    metadata = request.get("metadata") or {}
    thread_id = metadata.get(THREAD_ID_METADATA_KEY)

    if isinstance(thread_id, str) and thread_id.strip():
        return thread_id
    return DEFAULT_THREAD_ID


async def _stream_turn(agent, user_input: str, config):
    """Stream answer text deltas, then surface a native interrupt if the run paused."""
    async for delta in astream_research_text(agent, user_input, config=config):
        yield delta

    # A native interrupt leaves pending work in the checkpoint (state.next non-empty).
    # Surface a concise approval note without discarding the checkpoint. The default
    # host has no interrupt_on, so this is a no-op there.
    state = await agent.aget_state(config)
    if getattr(state, "next", None):
        yield _APPROVAL_REQUIRED_MESSAGE


async def _handle_response(
    agent,
    request: CreateResponse,
    context: ResponseContext,
) -> TextResponse:
    """Run one Responses turn against the persistent Deep Agent, streaming output."""
    user_input = (await context.get_input_text()) or ""

    if not user_input.strip():
        return TextResponse(context, request, text=_EMPTY_INPUT_MESSAGE)

    thread_id = _resolve_thread_id(request)
    config = thread_config(thread_id)

    # TextResponse natively streams an AsyncIterable[str]. Only the new turn is
    # sent; LangGraph restores prior state from the checkpoint under this
    # thread_id (no Responses history replay).
    return TextResponse(
        context, request, text=_stream_turn(agent, user_input, config)
    )


def create_host() -> ResponsesAgentServerHost:
    """Build the Hosted Agent host; the Deep Agent is built lazily per process."""
    app = ResponsesAgentServerHost()

    @app.response_handler
    async def handler(
        request: CreateResponse,
        context: ResponseContext,
        _cancellation_signal: asyncio.Event,
    ):
        agent = await _get_agent()
        return await _handle_response(agent, request, context)

    return app