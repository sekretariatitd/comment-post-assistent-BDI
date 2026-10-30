import asyncio
import hashlib
import html
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import feedparser
import httpx

from app.adapters.sources.base import FetchedPost, FetchError
from app.models import Source

USER_AGENT = "NewsCommentAssistant/0.1 (+RSS reader)"
MAX_FEED_BYTES = 5 * 1024 * 1024
FIRST_POLL_LIMIT = 20  # on the first poll, only take the newest entries (no huge backfill)
MAX_PER_POLL = 50
# Entries dated slightly before the last check can still appear late in a feed.
SINCE_GRACE = timedelta(hours=1)
MAX_TEXT = 10_000

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"[ \t\r\f\v]+")


class RssAdapter:
    key = "rss"
    can_poll = True

    async def fetch_new_posts(self, source: Source, since: datetime | None) -> list[FetchedPost]:
        content = await download(source.url_or_handle)
        return await asyncio.to_thread(parse_feed, content, since)


async def download(url: str) -> bytes:
    try:
        async with httpx.AsyncClient(
            timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise FetchError(f"Feed returned HTTP {e.response.status_code}") from None
    except httpx.HTTPError as e:
        raise FetchError(f"Couldn't download feed: {type(e).__name__}") from None
    if len(resp.content) > MAX_FEED_BYTES:
        raise FetchError("Feed is larger than 5 MB")
    return resp.content


def parse_feed(content: bytes, since: datetime | None) -> list[FetchedPost]:
    feed = feedparser.parse(content)
    if not feed.entries:
        if feed.get("bozo"):
            raise FetchError("Response is not a valid RSS/Atom feed")
        return []

    posts = [p for p in (_to_post(e) for e in feed.entries) if p is not None]
    oldest = datetime.min.replace(tzinfo=UTC)
    posts.sort(key=lambda p: p.published_at or oldest, reverse=True)

    if since is None:
        return posts[:FIRST_POLL_LIMIT]
    cutoff = since - SINCE_GRACE
    return [p for p in posts if p.published_at is None or p.published_at > cutoff][:MAX_PER_POLL]


def _to_post(entry: Any) -> FetchedPost | None:
    link = (entry.get("link") or "").strip()
    if not link.startswith(("http://", "https://")) or len(link) > 2000:
        return None

    title = _clean(entry.get("title", ""))
    summary = _clean(entry.get("summary", ""))
    text = title if not summary or summary == title else f"{title}\n\n{summary}"
    if not text:
        return None

    post_id = (entry.get("id") or link).strip()
    if len(post_id) > 500:
        post_id = "sha256:" + hashlib.sha256(post_id.encode()).hexdigest()

    return FetchedPost(
        platform_post_id=post_id,
        url=link,
        text=text[:MAX_TEXT],
        thumbnail_url=_thumbnail(entry),
        published_at=_published(entry),
    )


def _clean(value: str) -> str:
    text = html.unescape(_TAG.sub(" ", value))
    lines = (_SPACE.sub(" ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def _published(entry: Any) -> datetime | None:
    parsed: time.struct_time | None = entry.get("published_parsed") or entry.get("updated_parsed")
    return datetime(*parsed[:6], tzinfo=UTC) if parsed else None


def _thumbnail(entry: Any) -> str | None:
    candidates = [m.get("url") for m in entry.get("media_thumbnail", [])]
    candidates += [
        m.get("url") for m in entry.get("media_content", []) if "image" in m.get("type", "image")
    ]
    candidates += [
        link.get("href")
        for link in entry.get("links", [])
        if link.get("rel") == "enclosure" and link.get("type", "").startswith("image/")
    ]
    for url in candidates:
        if url and url.startswith(("http://", "https://")) and len(url) <= 2000:
            return url
    return None
