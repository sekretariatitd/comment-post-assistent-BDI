"""Extract posts from Facebook web payloads that a person copied from their own browser.

Accepts any of:
- a GraphQL response from www.facebook.com/api/graphql/ (one JSON document, or several
  newline-separated ones as Facebook streams them, optionally prefixed with "for (;;);"),
- the HTML of a Page (posts embedded in <script type="application/json"> blobs).

Story nodes are found by shape rather than by a fixed path, so small changes in Facebook's
response layout don't break parsing.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from app.adapters.sources.base import FetchedPost
from app.adapters.sources.browser_payload import PayloadError, documents, newest_first, walk

MAX_TEXT = 10_000
_IMAGE_KEYS = ("large_share_image", "flexible_height_share_image", "photo_image", "image")

__all__ = ["PayloadError", "parse_payload"]


def parse_payload(raw: str) -> list[FetchedPost]:
    """Return the posts found in `raw`, newest first, one per post_id."""
    found = (_to_post(node) for doc in documents(raw) for node in _story_nodes(doc))
    return newest_first(p for p in found if p is not None)


def _story_nodes(doc: Any) -> Iterator[dict[str, Any]]:
    # A feed story carries its own post_id and creation_time; nested helper objects that
    # repeat the story id carry at most one of them.
    for d in walk(doc):
        if d.get("__typename") == "Story" and d.get("post_id") and d.get("creation_time"):
            yield d


def _first(node: Any, key: str, want: type = str) -> Any:
    for d in walk(node):
        value = d.get(key)
        if isinstance(value, want) and value:
            return value
    return None


def _first_text(node: Any, key: str) -> str | None:
    for d in walk(node):
        value = d.get(key)
        if isinstance(value, dict) and isinstance(value.get("text"), str) and value["text"].strip():
            return value["text"].strip()
    return None


def _image(node: dict[str, Any]) -> str | None:
    attachments = node.get("attachments") or []
    for key in _IMAGE_KEYS:
        for d in walk(attachments):
            value = d.get(key)
            if isinstance(value, dict) and isinstance(value.get("uri"), str):
                uri = value["uri"]
                if uri.startswith("https://") and len(uri) <= 2000:
                    return uri
    return None


def _to_post(node: dict[str, Any]) -> FetchedPost | None:
    post_id = str(node["post_id"])
    message = _first_text(node, "message")
    title = _first_text(node, "title_with_entities")
    description = _first_text(node, "description")
    link = _first(node, "external_url")

    parts = [p for p in (message, title, description) if p]
    if link:
        parts.append(f"Link: {link}")
    if not parts:
        return None  # nothing to comment on (e.g. a bare photo with no caption)

    url = _first(node, "permalink_url") or _first(node, "wwwURL")
    if not isinstance(url, str) or not url.startswith("https://"):
        url = f"https://www.facebook.com/{post_id}"

    created = node.get("creation_time")
    return FetchedPost(
        platform_post_id=post_id,
        url=url[:2000],
        text="\n\n".join(parts)[:MAX_TEXT],
        thumbnail_url=_image(node),
        published_at=datetime.fromtimestamp(created, UTC) if isinstance(created, int) else None,
    )
