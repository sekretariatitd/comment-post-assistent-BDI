"""Shared helpers for payloads a person copied from their own browser's DevTools.

Our server never calls these platforms' internal endpoints; it only parses what was pasted.
"""

import html
import json
import re
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Any

from app.adapters.sources.base import FetchedPost

_JSON_SCRIPT = re.compile(r"<script[^>]*type=\"application/json\"[^>]*>(.*?)</script>", re.S)


class PayloadError(ValueError):
    pass


def documents(raw: str) -> list[Any]:
    """JSON documents in `raw`: one JSON value, newline-separated JSON (streamed responses,
    optionally prefixed with "for (;;);"), or the JSON <script> blobs of an HTML page."""
    text = raw.strip().removeprefix("for (;;);")
    if text.lstrip().startswith("<"):
        blobs = [
            html.unescape(b) if b.lstrip().startswith("&") else b
            for b in _JSON_SCRIPT.findall(text)
        ]
    else:
        try:
            return [json.loads(text)]
        except json.JSONDecodeError:
            blobs = text.splitlines()

    docs = []
    for blob in blobs:
        blob = blob.strip().removeprefix("for (;;);")
        if not blob:
            continue
        try:
            docs.append(json.loads(blob))
        except json.JSONDecodeError:
            continue
    if not docs:
        raise PayloadError("No JSON found. Paste the full Response (or the page HTML).")
    return docs


def walk(obj: Any) -> Iterator[dict[str, Any]]:
    """Every dict nested anywhere inside `obj`."""
    stack = [obj]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            yield current
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)


def newest_first(posts: Iterable[FetchedPost]) -> list[FetchedPost]:
    """One post per platform_post_id, newest first."""
    unique: dict[str, FetchedPost] = {}
    for post in posts:
        unique.setdefault(post.platform_post_id, post)
    oldest = datetime.min.replace(tzinfo=UTC)
    return sorted(unique.values(), key=lambda p: p.published_at or oldest, reverse=True)
