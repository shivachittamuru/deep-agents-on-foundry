"""Long-term, cross-thread user memory for stable research preferences (P8A).

Backed by a LangGraph Store and kept logically separate from the checkpointer
(which owns per-thread conversation/graph state). Memory formation is explicit:
only the tools below write, and only for durable preferences the user asks to be
remembered. No automatic extraction, inference, or semantic retrieval.

Identity boundary:
- thread_id  -> which conversation (checkpointer)
- user_id    -> whose long-term memory (this module / Store)
- namespace  -> what category of memory
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime

from .errors import ConfigurationError

# Category segment of the user-scoped namespace.
_PREFERENCES_CATEGORY = "research_preferences"


@dataclass
class ResearchContext:
    """Trusted per-invocation runtime context.

    `user_id` identifies whose long-term memory to use. It is supplied by the
    application at invoke time (`agent.invoke(..., context=ResearchContext(...))`)
    and is never provided by the LLM.
    """

    user_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, str) or not self.user_id.strip():
            raise ConfigurationError("user_id must be a non-empty string.")


def preferences_namespace(user_id: str) -> tuple[str, str, str]:
    """Build the user-scoped research-preferences namespace."""
    if not isinstance(user_id, str) or not user_id.strip():
        raise ConfigurationError("user_id must be a non-empty string.")
    return ("users", user_id, _PREFERENCES_CATEGORY)


def _optional_user_id(runtime: ToolRuntime) -> str | None:
    """Read the trusted user_id from runtime context, or None if absent.

    Returns None (rather than raising) when no user identity was provided, so the
    memory tools can degrade gracefully instead of crashing a hosted run.
    """
    context = getattr(runtime, "context", None)
    user_id = getattr(context, "user_id", None)
    if isinstance(user_id, str) and user_id.strip():
        return user_id
    return None


# Returned by the memory tools when a request carries no user identity.
_MEMORY_UNAVAILABLE_MESSAGE = (
    "Long-term memory is unavailable for this request because no user identity "
    "was provided. Proceeding without stored preferences."
)


MEMORY_POLICY = """

## Long-term memory policy

You have two memory tools: `remember_research_preference` and
`recall_research_preferences`. Use them conservatively.

Call `remember_research_preference` ONLY when the user explicitly asks you to
remember something, or clearly states a stable, durable preference about how
research should be conducted or presented (for example: preferred citation
style, research depth, tone, or output format).

Do NOT store: current web facts, news, prices, rankings, current product/API or
model capabilities, transient findings, arbitrary tool output, ordinary
conversation details, or preferences inferred from a single one-off request.

ALWAYS call `recall_research_preferences` FIRST — before you answer — whenever the
user asks what you remember or know about them, references their saved
preferences, or when durable preferences could shape the response. These
preferences persist across conversations, so never answer such questions from the
current conversation alone. If a tool reports that memory is unavailable, continue
normally without stored preferences.
"""


@tool
def remember_research_preference(preference: str, runtime: ToolRuntime) -> str:
    """Save a stable, explicitly stated research preference for the current user.

    Use only for durable preferences the user explicitly wants remembered (e.g.
    citation style, depth, output format) — never transient facts or findings.
    """
    user_id = _optional_user_id(runtime)
    if user_id is None:
        return _MEMORY_UNAVAILABLE_MESSAGE

    runtime.store.put(
        preferences_namespace(user_id), uuid4().hex, {"preference": preference}
    )
    return f"Saved research preference: {preference}"


@tool
def recall_research_preferences(runtime: ToolRuntime) -> str:
    """Return the current user's saved durable research preferences."""
    user_id = _optional_user_id(runtime)
    if user_id is None:
        return _MEMORY_UNAVAILABLE_MESSAGE

    preferences = [
        item.value.get("preference", "")
        for item in runtime.store.search(preferences_namespace(user_id))
    ]
    if not preferences:
        return "No saved research preferences."
    return "; ".join(preferences)


MEMORY_TOOLS = [remember_research_preference, recall_research_preferences]
