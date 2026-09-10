"""Tests for LangGraph SQLite persistence helpers (no Azure/model calls)."""

from __future__ import annotations

from typing import TypedDict

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from deep_agents_foundry.errors import ConfigurationError
from deep_agents_foundry.persistence import (
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
