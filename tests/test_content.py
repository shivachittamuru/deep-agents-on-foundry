"""Tests for shared content text extraction (no live calls)."""

from __future__ import annotations

from types import SimpleNamespace

from deep_agents_foundry.content import content_text


def test_content_text_plain_string():
    assert content_text(SimpleNamespace(content="hello")) == "hello"


def test_content_text_from_content_block_list():
    message = SimpleNamespace(
        content=[
            {"type": "text", "text": "X"},
            {"type": "tool_call", "name": "web_search"},
            {"type": "text", "text": "Y"},
        ]
    )

    assert content_text(message) == "XY"


def test_content_text_prefers_content_blocks_for_chunks():
    chunk = SimpleNamespace(
        content_blocks=[{"type": "text", "text": "A"}, {"type": "text", "text": "B"}],
        content="",
    )

    assert content_text(chunk) == "AB"


def test_content_text_ignores_non_text_blocks():
    chunk = SimpleNamespace(
        content_blocks=[{"type": "server_tool_call"}, {"type": "annotation"}]
    )

    assert content_text(chunk) == ""


def test_content_text_none_returns_empty():
    assert content_text(SimpleNamespace(content=None)) == ""


def test_content_text_empty_blocks_fall_back_to_content():
    message = SimpleNamespace(content_blocks=[], content="fallback")

    assert content_text(message) == "fallback"


def test_content_text_non_text_content_coerced():
    assert content_text(SimpleNamespace(content=123)) == "123"


def test_content_text_accepts_raw_string():
    assert content_text("raw") == "raw"
