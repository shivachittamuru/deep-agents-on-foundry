"""Shared text extraction for Foundry adapter messages and streaming chunks.

The Azure/Foundry adapter exposes generated text through structured content
blocks, not reliably through a plain string `.content`. This helper normalizes
both final messages and streaming chunks to plain text.
"""

from __future__ import annotations


def _text_from_blocks(blocks) -> str:
    return "".join(
        block["text"]
        for block in blocks
        if isinstance(block, dict)
        and block.get("type") == "text"
        and block.get("text")
    )


def content_text(message) -> str:
    """Extract plain text from a message or streaming chunk.

    Prefers normalized `content_blocks` (present on streaming chunks), then falls
    back to `.content` as a string or list of typed blocks.
    """
    if isinstance(message, str):
        return message
    if isinstance(message, list):
        return _text_from_blocks(message)

    blocks = getattr(message, "content_blocks", None)
    if blocks:
        return _text_from_blocks(blocks)

    content = getattr(message, "content", None)

    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return _text_from_blocks(content)

    return str(content)
