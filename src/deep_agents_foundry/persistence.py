"""LangGraph thread/memory persistence.

Two persistence tiers:

- SQLite (``build_*_sqlite_checkpointer``): local/development and notebooks only.
- PostgreSQL (``PostgresPersistence``): production Hosted Agent path — an async
  connection pool backing both an ``AsyncPostgresSaver`` (short-term thread /
  checkpoint state) and an ``AsyncPostgresStore`` (long-term user memory), kept
  logically separate, authenticated with Entra ID.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite
from azure.identity.aio import DefaultAzureCredential
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import PostgresSettings, load_postgres_settings
from .errors import ConfigurationError, PersistenceError

_IN_MEMORY = ":memory:"

# Entra token scope for Azure Database for PostgreSQL.
POSTGRES_TOKEN_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"

# Recycle pooled connections before the ~60-minute Entra token would expire, so
# every new connection re-authenticates with a fresh token.
_DEFAULT_MAX_LIFETIME = 3000.0


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


class PostgresPersistence:
    """Owns the async Postgres pool, checkpointer, and store for the process.

    One shared connection pool backs both the ``AsyncPostgresSaver`` (short-term
    thread/checkpoint state, keyed by ``thread_id``) and the ``AsyncPostgresStore``
    (long-term user memory, keyed by ``user_id``); the two remain logically
    separate. Entra auth is refresh-aware — a fresh token is fetched for each new
    pooled connection and connections are recycled before token expiry.
    """

    def __init__(
        self,
        settings: PostgresSettings | None = None,
        *,
        credential=None,
        min_size: int = 1,
        max_size: int = 10,
        max_lifetime: float = _DEFAULT_MAX_LIFETIME,
    ):
        self._settings = settings or load_postgres_settings()
        self._credential = credential if credential is not None else DefaultAzureCredential()
        self._owns_credential = credential is None
        self._min_size = min_size
        self._max_size = max_size
        self._max_lifetime = max_lifetime
        self._pool = None
        self.checkpointer = None
        self.store = None

    def _conninfo(self) -> str:
        s = self._settings
        return (
            f"host={s.host} port=5432 dbname={s.database} "
            f"user={s.user} sslmode={s.sslmode}"
        )

    async def _connection_kwargs(self) -> dict:
        """Fresh per-connection kwargs; the Entra token is used as the password."""
        token = await self._credential.get_token(POSTGRES_TOKEN_SCOPE)
        return {
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "password": token.token,
        }

    async def open(self) -> None:
        """Open the pool and run Saver/Store schema setup once (idempotent)."""
        if self._pool is not None:
            return

        try:
            pool = AsyncConnectionPool(
                self._conninfo(),
                min_size=self._min_size,
                max_size=self._max_size,
                kwargs=self._connection_kwargs,
                max_lifetime=self._max_lifetime,
                open=False,
            )
            await pool.open(wait=True)
        except Exception as exc:
            raise PersistenceError(
                "Failed to open the PostgreSQL connection pool."
            ) from exc

        self._pool = pool
        self.checkpointer = AsyncPostgresSaver(pool)
        self.store = AsyncPostgresStore(pool)

        try:
            await self.checkpointer.setup()
            await self.store.setup()
        except Exception as exc:
            await self.close()
            raise PersistenceError(
                "Failed to run PostgreSQL schema setup."
            ) from exc

    async def close(self) -> None:
        """Close the pool (and owned credential) cleanly on shutdown."""
        pool, self._pool = self._pool, None
        self.checkpointer = None
        self.store = None
        if pool is not None:
            await pool.close()
        if self._owns_credential and self._credential is not None:
            await self._credential.close()
            self._credential = None
