"""Polling sources for new posts. Used by the ARQ worker (app.workers.jobs)."""

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sources import FetchedPost, FetchError, SourceAdapter, pollable_keys
from app.models import Post, Source
from app.services import audit_service

logger = logging.getLogger(__name__)

# Lets a source with a 15-minute interval be picked up by the minute-15 cron tick, not minute 16.
_SLACK_SECONDS = 30


async def due_source_ids(db: AsyncSession) -> Sequence[uuid.UUID]:
    """Active, pollable sources whose interval has elapsed since their last check."""
    next_check = (
        Source.last_checked_at
        + func.make_interval(0, 0, 0, 0, 0, Source.poll_interval_minutes)
        - func.make_interval(0, 0, 0, 0, 0, 0, _SLACK_SECONDS)
    )
    result = await db.execute(
        select(Source.id).where(
            Source.is_active.is_(True),
            Source.adapter.in_(pollable_keys()),
            or_(Source.last_checked_at.is_(None), next_check <= func.now()),
        )
    )
    return result.scalars().all()


async def insert_posts(
    db: AsyncSession, source_id: uuid.UUID, posts: list[FetchedPost]
) -> list[uuid.UUID]:
    """Insert posts, skipping any already stored for this source. Returns ids of new posts."""
    if not posts:
        return []
    rows = [
        {
            "id": uuid.uuid4(),
            "source_id": source_id,
            "platform_post_id": p.platform_post_id,
            "url": p.url,
            "text": p.text,
            "thumbnail_url": p.thumbnail_url,
            "published_at": p.published_at,
        }
        for p in {p.platform_post_id: p for p in posts}.values()  # dedupe within the batch too
    ]
    stmt = (
        pg_insert(Post)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["source_id", "platform_post_id"])
        .returning(Post.id)
    )
    return list((await db.execute(stmt)).scalars().all())


async def poll_source(db: AsyncSession, source: Source, adapter: SourceAdapter) -> list[uuid.UUID]:
    """Fetch new posts for one source and store them. Returns ids of newly inserted posts.

    A failed fetch still advances last_checked_at, so a broken feed is retried on its normal
    interval rather than every minute.
    """
    since = source.last_checked_at
    source.last_checked_at = datetime.now(UTC)
    try:
        fetched = await adapter.fetch_new_posts(source, since)
    except FetchError as e:
        logger.warning("Polling source %s failed: %s", source.id, e)
        audit_service.record(
            db,
            actor=None,
            action="source.poll_failed",
            entity_type="source",
            entity_id=source.id,
            payload={"error": str(e)[:500]},
        )
        await db.commit()
        return []

    new_ids = await insert_posts(db, source.id, fetched)
    if new_ids:
        audit_service.record(
            db,
            actor=None,
            action="source.polled",
            entity_type="source",
            entity_id=source.id,
            payload={"fetched": len(fetched), "new_posts": len(new_ids)},
        )
    await db.commit()
    return new_ids
