from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sources import FetchedPost, FetchError
from app.adapters.sources.rss import FIRST_POLL_LIMIT, parse_feed
from app.main import app
from app.models import AuditLog, Platform, Post, Source
from app.services import ingest_service
from app.workers.queue import get_queue


def _rss(items: list[dict[str, str]]) -> bytes:
    body = "".join(f"""<item>
          <title>{i["title"]}</title>
          <link>{i["link"]}</link>
          {f'<guid>{i["guid"]}</guid>' if "guid" in i else ""}
          <description>{i.get("description", "")}</description>
          <pubDate>{i["date"]}</pubDate>
          {i.get("extra", "")}
        </item>""" for i in items)
    return f"""<?xml version="1.0"?>
      <rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
        <channel><title>Test</title>{body}</channel>
      </rss>""".encode()


def _date(hours_ago: float) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours_ago)).strftime("%a, %d %b %Y %H:%M:%S +0000")


def test_parse_feed_extracts_fields() -> None:
    feed = _rss(
        [
            {
                "title": "Council &amp; mayor agree budget",
                "link": "https://news.example/a",
                "guid": "guid-a",
                "description": "&lt;p&gt;The &lt;b&gt;new&lt;/b&gt; budget passed.&lt;/p&gt;",
                "date": _date(1),
                "extra": '<media:thumbnail url="https://img.example/a.jpg"/>',
            },
            {"title": "No guid", "link": "https://news.example/b", "date": _date(2)},
        ]
    )
    posts = parse_feed(feed, since=None)
    assert [p.platform_post_id for p in posts] == ["guid-a", "https://news.example/b"]
    first = posts[0]
    assert first.text == "Council & mayor agree budget\n\nThe new budget passed."
    assert first.thumbnail_url == "https://img.example/a.jpg"
    assert first.published_at is not None and first.published_at.tzinfo is not None


def test_first_poll_takes_only_newest_entries() -> None:
    items = [
        {"title": f"Item {n}", "link": f"https://news.example/{n}", "date": _date(n)}
        for n in range(FIRST_POLL_LIMIT + 10)
    ]
    posts = parse_feed(_rss(items), since=None)
    assert len(posts) == FIRST_POLL_LIMIT
    assert posts[0].url == "https://news.example/0"  # newest first


def test_later_polls_skip_entries_older_than_last_check() -> None:
    items = [
        {"title": "new", "link": "https://news.example/new", "date": _date(0.5)},
        {"title": "old", "link": "https://news.example/old", "date": _date(30)},
    ]
    posts = parse_feed(_rss(items), since=datetime.now(UTC) - timedelta(hours=2))
    assert [p.url for p in posts] == ["https://news.example/new"]


def test_invalid_feed_raises() -> None:
    with pytest.raises(FetchError):
        parse_feed(b"<html><body>not a feed", since=None)


async def _source(db: AsyncSession, **overrides: Any) -> Source:
    values = {
        "platform": Platform.rss,
        "display_name": "Feed",
        "url_or_handle": "https://news.example/rss",
        "adapter": "rss",
    } | overrides
    source = Source(**values)
    db.add(source)
    await db.flush()
    return source


class FakeAdapter:
    key = "rss"
    can_poll = True

    def __init__(self, posts: list[FetchedPost] | Exception) -> None:
        self.posts = posts
        self.since: list[datetime | None] = []

    async def fetch_new_posts(self, source: Source, since: datetime | None) -> list[FetchedPost]:
        self.since.append(since)
        if isinstance(self.posts, Exception):
            raise self.posts
        return self.posts


POSTS = [
    FetchedPost(platform_post_id="1", url="https://news.example/1", text="one"),
    FetchedPost(platform_post_id="2", url="https://news.example/2", text="two"),
]


async def test_poll_inserts_new_posts_without_duplicates(db_session: AsyncSession) -> None:
    source = await _source(db_session)
    adapter = FakeAdapter(POSTS + [POSTS[0]])  # duplicate inside one batch too

    first = await ingest_service.poll_source(db_session, source, adapter)
    assert len(first) == 2
    assert source.last_checked_at is not None

    second = await ingest_service.poll_source(db_session, source, adapter)
    assert second == []
    assert adapter.since[1] is not None  # second poll passes the previous check time

    count = len((await db_session.execute(select(Post))).scalars().all())
    assert count == 2
    actions = [a.action for a in (await db_session.execute(select(AuditLog))).scalars()]
    assert actions == ["source.polled"]  # no audit row when nothing new


async def test_failed_poll_is_audited_and_advances_check_time(db_session: AsyncSession) -> None:
    source = await _source(db_session)
    new = await ingest_service.poll_source(db_session, source, FakeAdapter(FetchError("HTTP 500")))
    assert new == []
    assert source.last_checked_at is not None
    audit = (await db_session.execute(select(AuditLog))).scalar_one()
    assert audit.action == "source.poll_failed"
    assert audit.payload == {"error": "HTTP 500"}
    assert audit.actor_id is None


async def test_due_sources(db_session: AsyncSession) -> None:
    now = datetime.now(UTC)
    never = await _source(db_session, display_name="never checked")
    overdue = await _source(db_session, last_checked_at=now - timedelta(minutes=20))
    await _source(db_session, last_checked_at=now)  # just checked
    await _source(db_session, is_active=False)
    await _source(db_session, adapter="manual", platform=Platform.manual)
    await _source(db_session, adapter="meta_graph", platform=Platform.facebook)

    due = set(await ingest_service.due_source_ids(db_session))
    assert due == {never.id, overdue.id}


class FakeQueue:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[Any, ...], str]] = []

    async def enqueue_job(self, name: str, *args: Any, _job_id: str) -> object | None:
        if any(job_id == _job_id for *_, job_id in self.jobs):
            return None
        self.jobs.append((name, args, _job_id))
        return object()


async def _create_source(client: AsyncClient, headers: dict[str, str], **body: Any) -> dict:
    payload = {"platform": "rss", "display_name": "F", "url_or_handle": "https://n.example/rss"}
    resp = await client.post("/api/v1/sources", json=payload | body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_poll_now(client: AsyncClient, admin_headers, reviewer_headers) -> None:
    queue = FakeQueue()
    app.dependency_overrides[get_queue] = lambda: queue
    rss = await _create_source(client, admin_headers)
    fb = await _create_source(
        client, admin_headers, platform="facebook", url_or_handle="https://facebook.com/page"
    )

    resp = await client.post(f"/api/v1/sources/{rss['id']}/poll-now", headers=reviewer_headers)
    assert resp.status_code == 202 and resp.json() == {"queued": True}
    again = await client.post(f"/api/v1/sources/{rss['id']}/poll-now", headers=reviewer_headers)
    assert again.json() == {"queued": False}
    assert queue.jobs == [("poll_source", (rss["id"],), f"poll_source:{rss['id']}")]

    blocked = await client.post(f"/api/v1/sources/{fb['id']}/poll-now", headers=reviewer_headers)
    assert blocked.status_code == 409


async def test_manual_posts_and_listing(
    client: AsyncClient, admin_headers, reviewer_headers
) -> None:
    fb = await _create_source(
        client, admin_headers, platform="facebook", url_or_handle="https://facebook.com/page"
    )
    other = await _create_source(client, admin_headers)
    body = {
        "source_id": fb["id"],
        "url": "https://www.Facebook.com/page/posts/123#comments",
        "text": "  Post text  ",
    }

    created = await client.post("/api/v1/posts", json=body, headers=reviewer_headers)
    assert created.status_code == 201, created.text
    post = created.json()
    assert post["url"] == "https://www.facebook.com/page/posts/123"
    assert post["text"] == "Post text"
    assert post["status"] == "new"

    dup = await client.post("/api/v1/posts", json=body, headers=reviewer_headers)
    assert dup.status_code == 409

    bad = await client.post(
        "/api/v1/posts", json=body | {"url": "ftp://x.example/1"}, headers=reviewer_headers
    )
    assert bad.status_code == 422

    await client.post(
        "/api/v1/posts",
        json={"source_id": other["id"], "url": "https://n.example/2", "text": "other"},
        headers=reviewer_headers,
    )

    everything = (await client.get("/api/v1/posts", headers=reviewer_headers)).json()
    assert everything["total"] == 2
    filtered = (
        await client.get(f"/api/v1/posts?source_id={fb['id']}&status=new", headers=reviewer_headers)
    ).json()
    assert [p["id"] for p in filtered["items"]] == [post["id"]]
    skipped = (await client.get("/api/v1/posts?status=skipped", headers=reviewer_headers)).json()
    assert skipped["total"] == 0

    one = await client.get(f"/api/v1/posts/{post['id']}", headers=reviewer_headers)
    assert one.json()["id"] == post["id"]
