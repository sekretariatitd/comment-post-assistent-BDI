"""Extract videos from TikTok web payloads that a person copied from their own browser.

Accepts the Response of a profile's `api/post/item_list/` request ({"itemList": [...]}) or the
HTML of a video page (its __UNIVERSAL_DATA_FOR_REHYDRATION__ JSON). Video items are found by
shape, not by a fixed path.
"""

import re
from datetime import UTC, datetime
from typing import Any

from app.adapters.sources.base import FetchedPost
from app.adapters.sources.browser_payload import PayloadError, documents, newest_first, walk

MAX_TEXT = 10_000
_COVER_KEYS = ("cover", "originCover", "dynamicCover")
_HANDLE = re.compile(r"@([\w.\-]+)")

__all__ = ["PayloadError", "handle_from", "parse_payload"]


def handle_from(url_or_handle: str) -> str | None:
    """'https://www.tiktok.com/@bajram.rexhepi3' or '@bajram.rexhepi3' -> 'bajram.rexhepi3'."""
    match = _HANDLE.search(url_or_handle)
    return match.group(1) if match else None


def parse_payload(raw: str, default_handle: str | None = None) -> list[FetchedPost]:
    """Return the videos found in `raw` that have a caption, newest first."""
    found = (
        _to_post(item, default_handle)
        for doc in documents(raw)
        for item in walk(doc)
        if _is_video_item(item)
    )
    return newest_first(p for p in found if p is not None)


def _is_video_item(d: dict[str, Any]) -> bool:
    video_id = d.get("id")
    return (
        isinstance(video_id, str)
        and video_id.isdigit()
        and "desc" in d
        and "createTime" in d
        and (isinstance(d.get("video"), dict) or isinstance(d.get("author"), dict | str))
    )


def _to_post(item: dict[str, Any], default_handle: str | None) -> FetchedPost | None:
    caption = (item.get("desc") or "").strip()
    if not caption:
        return None  # nothing for the AI to respond to

    author = item.get("author")
    handle = author.get("uniqueId") if isinstance(author, dict) else author
    handle = handle if isinstance(handle, str) and handle else default_handle
    url = (
        f"https://www.tiktok.com/@{handle}/video/{item['id']}"
        if handle
        else f"https://www.tiktok.com/video/{item['id']}"
    )

    created = item.get("createTime")
    if isinstance(created, str) and created.isdigit():
        created = int(created)

    return FetchedPost(
        platform_post_id=item["id"],
        url=url,
        text=caption[:MAX_TEXT],
        thumbnail_url=_cover(item.get("video")),
        published_at=datetime.fromtimestamp(created, UTC) if isinstance(created, int) else None,
    )


def _cover(video: Any) -> str | None:
    if not isinstance(video, dict):
        return None
    for key in _COVER_KEYS:
        uri = video.get(key)
        if isinstance(uri, str) and uri.startswith("https://") and len(uri) <= 2000:
            return uri
    return None
