"""Foundry Hosted Agent handler backed by one persistent Deep Agent (PostgreSQL).

Durability lives in LangGraph checkpoints keyed by an application-level
`thread_id`. Foundry `session_id`/conversation identity is intentionally NOT used
as the permanent thread id, and Responses conversation history is never hydrated
into LangGraph (`context.get_history()` is deliberately not called).

Persistence is Azure Database for PostgreSQL (Entra-authenticated): an
`AsyncPostgresSaver` for thread/checkpoint state and an `AsyncPostgresStore` for
long-term user memory, both backed by one process-wide connection pool.
"""

import asyncio
import os

from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponsesAgentServerHost,
    TextResponse,
)

from .agent import build_research_agent
from .memory import ResearchContext
from .persistence import PostgresPersistence, thread_config
from .skills import DEFAULT_SKILL_SOURCES, skills_available
from .streaming import astream_research_text

# Client-supplied metadata keys.
THREAD_ID_METADATA_KEY = "thread_id"
USER_ID_METADATA_KEY = "user_id"

# Prefix for thread ids derived from the Foundry conversation chain.
THREAD_ID_PREFIX = "thread-"

# Last-resort thread id if no conversation chain id is available.
DEFAULT_THREAD_ID = "default"

# Single-tester convenience: when a request carries no user_id, long-term memory
# uses this default identity so it works locally without client metadata. This is
# a temporary testing seam, NOT production (Entra) identity; override via env.
DEFAULT_USER_ID_ENV = "DEEP_AGENTS_DEFAULT_USER_ID"
DEFAULT_USER_ID = "user_id_1_shiva"

_APPROVAL_REQUIRED_MESSAGE = (
    "This action requires approval before it can continue. The run has been "
    "paused and its state saved under this thread; it can be resumed once "
    "client-driven approval is wired up."
)

_EMPTY_INPUT_MESSAGE = "Please provide a research question."


# Built lazily on first request: the async Postgres pool and AsyncPostgresSaver
# bind to the running event loop, which is not available when create_host() runs.
_persistence = None
_agent_singleton = None
_agent_lock = asyncio.Lock()


async def _get_agent():
    """Return the process-wide persistent Deep Agent, building it once.

    Initializes PostgreSQL persistence once per process (pool + schema setup),
    then wires the AsyncPostgresSaver (per-thread conversation state), the
    AsyncPostgresStore (long-term user memory), and Skills (procedural knowledge).
    """
    global _persistence, _agent_singleton
    if _agent_singleton is None:
        async with _agent_lock:
            if _agent_singleton is None:
                persistence = PostgresPersistence()
                await persistence.open()  # pool + Saver/Store + schema setup once
                skills = DEFAULT_SKILL_SOURCES if skills_available() else None
                _agent_singleton = build_research_agent(
                    checkpointer=persistence.checkpointer,
                    store=persistence.store,
                    skills=skills,
                )
                _persistence = persistence
    return _agent_singleton


async def _close_persistence() -> None:
    """Close the PostgreSQL pool on shutdown."""
    global _persistence, _agent_singleton
    persistence, _persistence = _persistence, None
    _agent_singleton = None
    if persistence is not None:
        await persistence.close()


def _resolve_thread_id(request: CreateResponse, context: ResponseContext) -> str:
    """Resolve the LangGraph thread id (conversation/checkpoint identity).

    The application-owned `metadata["thread_id"]` wins. Otherwise a stable thread
    is derived from the Foundry conversation chain id, so each new conversation
    gets its own thread (continuity within it, isolation across it) without the
    client having to supply one.
    """
    metadata = request.get("metadata") or {}
    thread_id = metadata.get(THREAD_ID_METADATA_KEY)
    if isinstance(thread_id, str) and thread_id.strip():
        return thread_id

    chain_id = getattr(context, "conversation_chain_id", None)
    if isinstance(chain_id, str) and chain_id.strip():
        return f"{THREAD_ID_PREFIX}{chain_id}"
    return DEFAULT_THREAD_ID


def _resolve_user_id(request: CreateResponse) -> str | None:
    """Resolve the long-term-memory user id from client-supplied metadata.

    Falls back to a single-tester default so local memory works without client
    metadata. Temporary application identity seam — never derived from message
    content, and not production Entra identity.
    """
    metadata = request.get("metadata") or {}
    user_id = metadata.get(USER_ID_METADATA_KEY)

    if isinstance(user_id, str) and user_id.strip():
        return user_id
    return os.environ.get(DEFAULT_USER_ID_ENV, DEFAULT_USER_ID)


async def _stream_turn(agent, user_input: str, config, research_context):
    """Stream answer text deltas, then surface a native interrupt if the run paused."""
    async for delta in astream_research_text(
        agent, user_input, config=config, context=research_context
    ):
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

    # thread_id -> conversation/checkpoint identity; user_id -> memory identity.
    config = thread_config(_resolve_thread_id(request, context))
    user_id = _resolve_user_id(request)
    research_context = ResearchContext(user_id=user_id) if user_id else None

    # TextResponse natively streams an AsyncIterable[str]. Only the new turn is
    # sent; LangGraph restores prior state from the checkpoint under this
    # thread_id (no Responses history replay).
    return TextResponse(
        context,
        request,
        text=_stream_turn(agent, user_input, config, research_context),
    )


def create_host() -> ResponsesAgentServerHost:
    """Build the Hosted Agent host; persistence + agent are built lazily per process."""
    app = ResponsesAgentServerHost()

    @app.response_handler
    async def handler(
        request: CreateResponse,
        context: ResponseContext,
        _cancellation_signal: asyncio.Event,
    ):
        agent = await _get_agent()
        return await _handle_response(agent, request, context)

    @app.shutdown_handler
    async def _shutdown():
        await _close_persistence()

    return app