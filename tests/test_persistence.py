"""Tests for LangGraph persistence helpers (no Azure/network/model calls)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TypedDict

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from deep_agents_foundry import persistence as persistence_module
from deep_agents_foundry.config import PostgresSettings
from deep_agents_foundry.errors import ConfigurationError, PersistenceError
from deep_agents_foundry.persistence import (
    PostgresPersistence,
    build_async_sqlite_checkpointer,
    build_sqlite_checkpointer,
    thread_config,
)


def test_build_sqlite_checkpointer_returns_sqlite_saver(tmp_path):
    checkpointer = build_sqlite_checkpointer(tmp_path / "cp.db")

    assert isinstance(checkpointer, SqliteSaver)


def test_build_sqlite_checkpointer_creates_parent_directory(tmp_path):
    db_path = tmp_path / "nested" / "dir" / "cp.db"

    build_sqlite_checkpointer(db_path)

    assert db_path.parent.is_dir()


def test_thread_config_exact_shape():
    assert thread_config("research-123") == {
        "configurable": {"thread_id": "research-123"}
    }


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_thread_config_rejects_blank(value):
    with pytest.raises(ConfigurationError):
        thread_config(value)


def _counter_graph(checkpointer):
    class State(TypedDict):
        value: int

    def bump(state: State):
        return {"value": state["value"] + 1}

    builder = StateGraph(State)
    builder.add_node("bump", bump)
    builder.add_edge(START, "bump")
    builder.add_edge("bump", END)

    return builder.compile(checkpointer=checkpointer)


def test_state_persists_and_threads_are_isolated(tmp_path):
    checkpointer = build_sqlite_checkpointer(tmp_path / "threads.db")
    graph = _counter_graph(checkpointer)

    thread_a = thread_config("thread-a")
    thread_b = thread_config("thread-b")

    graph.invoke({"value": 0}, config=thread_a)
    graph.invoke({"value": 100}, config=thread_b)

    # State written under one thread can be read back.
    assert graph.get_state(thread_a).values["value"] == 1
    # A different thread_id remains isolated.
    assert graph.get_state(thread_b).values["value"] == 101


def test_build_async_sqlite_checkpointer_returns_async_saver(tmp_path):
    async def run():
        return build_async_sqlite_checkpointer(tmp_path / "async.db")

    checkpointer = asyncio.run(run())

    assert isinstance(checkpointer, AsyncSqliteSaver)


def test_async_state_persists_and_threads_are_isolated(tmp_path):
    async def run():
        checkpointer = build_async_sqlite_checkpointer(tmp_path / "async.db")
        graph = _counter_graph(checkpointer)
        thread_a = thread_config("thread-a")
        thread_b = thread_config("thread-b")

        await graph.ainvoke({"value": 0}, config=thread_a)
        await graph.ainvoke({"value": 100}, config=thread_b)

        state_a = await graph.aget_state(thread_a)
        state_b = await graph.aget_state(thread_b)
        await checkpointer.conn.close()
        return state_a.values["value"], state_b.values["value"]

    value_a, value_b = asyncio.run(run())

    assert value_a == 1
    assert value_b == 101


# --- PostgreSQL persistence lifecycle (mocked pool/saver/store/credential) ---


class _FakePool:
    def __init__(self, conninfo, **kwargs):
        self.conninfo = conninfo
        self.kwargs = kwargs
        self.opened = False
        self.closed = False

    async def open(self, wait=True):
        self.opened = True

    async def close(self):
        self.closed = True


class _FakeSaver:
    def __init__(self, conn):
        self.conn = conn
        self.setup_calls = 0

    async def setup(self):
        self.setup_calls += 1


class _FakeStore:
    def __init__(self, conn):
        self.conn = conn
        self.setup_calls = 0

    async def setup(self):
        self.setup_calls += 1


class _FakeCredential:
    def __init__(self):
        self.token_calls = 0
        self.closed = False

    async def get_token(self, scope):
        self.token_calls += 1
        return SimpleNamespace(token="fake-token")

    async def close(self):
        self.closed = True


def _settings():
    return PostgresSettings(host="h", database="d", user="u", sslmode="require")


def _patch_pg(monkeypatch):
    pools = []

    def fake_pool_cls(conninfo, **kwargs):
        pool = _FakePool(conninfo, **kwargs)
        pools.append(pool)
        return pool

    monkeypatch.setattr(persistence_module, "AsyncConnectionPool", fake_pool_cls)
    monkeypatch.setattr(persistence_module, "AsyncPostgresSaver", _FakeSaver)
    monkeypatch.setattr(persistence_module, "AsyncPostgresStore", _FakeStore)
    return pools


def test_postgres_persistence_opens_once_and_wires_shared_pool(monkeypatch):
    pools = _patch_pg(monkeypatch)
    credential = _FakeCredential()
    persistence = PostgresPersistence(_settings(), credential=credential)

    asyncio.run(persistence.open())
    asyncio.run(persistence.open())  # idempotent: no second pool

    assert len(pools) == 1
    assert pools[0].opened is True
    assert isinstance(persistence.checkpointer, _FakeSaver)
    assert isinstance(persistence.store, _FakeStore)
    # Schema setup runs once for each; one shared pool backs both.
    assert persistence.checkpointer.setup_calls == 1
    assert persistence.store.setup_calls == 1
    assert persistence.checkpointer.conn is persistence.store.conn is pools[0]


def test_postgres_persistence_connection_kwargs_use_entra_token(monkeypatch):
    _patch_pg(monkeypatch)
    credential = _FakeCredential()
    persistence = PostgresPersistence(_settings(), credential=credential)

    kwargs = asyncio.run(persistence._connection_kwargs())

    assert kwargs["password"] == "fake-token"
    assert kwargs["autocommit"] is True
    assert kwargs["prepare_threshold"] == 0
    assert credential.token_calls == 1


def test_postgres_persistence_close_closes_pool(monkeypatch):
    pools = _patch_pg(monkeypatch)
    credential = _FakeCredential()
    persistence = PostgresPersistence(_settings(), credential=credential)

    asyncio.run(persistence.open())
    asyncio.run(persistence.close())

    assert pools[0].closed is True
    assert persistence.checkpointer is None
    assert persistence.store is None
    # An injected credential is owned by the caller and not closed here.
    assert credential.closed is False


def test_postgres_persistence_setup_failure_raises_and_cleans_up(monkeypatch):
    pools = _patch_pg(monkeypatch)

    class _FailingStore(_FakeStore):
        async def setup(self):
            raise RuntimeError("schema boom")

    monkeypatch.setattr(persistence_module, "AsyncPostgresStore", _FailingStore)
    persistence = PostgresPersistence(_settings(), credential=_FakeCredential())

    with pytest.raises(PersistenceError):
        asyncio.run(persistence.open())

    # Pool was closed during cleanup so nothing leaks.
    assert pools[0].closed is True


def test_postgres_persistence_pool_open_failure_raises(monkeypatch):
    class _FailingPool(_FakePool):
        async def open(self, wait=True):
            raise RuntimeError("network boom")

    monkeypatch.setattr(
        persistence_module,
        "AsyncConnectionPool",
        lambda conninfo, **kwargs: _FailingPool(conninfo, **kwargs),
    )
    persistence = PostgresPersistence(_settings(), credential=_FakeCredential())

    with pytest.raises(PersistenceError):
        asyncio.run(persistence.open())
