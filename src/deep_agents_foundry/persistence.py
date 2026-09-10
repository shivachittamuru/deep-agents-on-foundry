"""LangGraph thread persistence (promoted from notebook 08).

SQLite is development/local persistence only. It is intentionally simple: a
single connection with no pooling or locking. It is NOT suitable for concurrent
Hosted Agent production workloads — a Postgres checkpointer is the intended
production path (a later slice).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from .errors import ConfigurationError

_IN_MEMORY = ":memory:"


def build_sqlite_checkpointer(db_path: str | Path) -> SqliteSaver:
    """Build a LangGraph SQLite checkpointer for local/development persistence.

    Ensures the parent directory exists for filesystem paths. Uses
    `check_same_thread=False` to match the notebook behavior. Development only;
    not for concurrent production workloads.
    """
    if db_path == _IN_MEMORY:
        target = _IN_MEMORY
    else:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        target = str(path)

    connection = sqlite3.connect(target, check_same_thread=False)
    return SqliteSaver(connection)


def build_async_sqlite_checkpointer(db_path: str | Path) -> AsyncSqliteSaver:
    """Build an async LangGraph SQLite checkpointer for the `astream(...)` path.

    Required because `agent.astream(...)` calls the async checkpointer methods,
    which `SqliteSaver` does not implement. The aiosqlite connection is created
    here but connects lazily on first use inside the running event loop.
    Development only; not for concurrent production workloads.
    """
    if db_path == _IN_MEMORY:
        target = _IN_MEMORY
    else:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        target = str(path)

    return AsyncSqliteSaver(aiosqlite.connect(target))


def thread_config(thread_id: str) -> dict:
    """Build the LangGraph config that binds an invocation to a durable thread."""
    if not isinstance(thread_id, str) or not thread_id.strip():
        raise ConfigurationError("thread_id must be a non-empty string.")

    return {
        "configurable": {
            "thread_id": thread_id,
        }
    }
