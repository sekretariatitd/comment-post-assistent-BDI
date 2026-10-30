"""ARQ jobs. publish_draft arrives in Phase 6."""

import logging
import uuid
from typing import Any

from app.adapters.sources import get_adapter
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.llm.client import LLMError, get_llm_client
from app.models import Source
from app.services import audit_service, drafting_service, ingest_service
from app.workers.queue import enqueue_scoring, poll_job_id

logger = logging.getLogger(__name__)


async def enqueue_due_sources(ctx: dict[str, Any]) -> int:
    """Cron (every minute): queue a poll for each source whose interval has elapsed, and
    scoring for any post left unscored. Job ids dedupe against work already queued."""
    async with SessionLocal() as db:
        source_ids = await ingest_service.due_source_ids(db)
        unscored = await drafting_service.unscored_post_ids(db)
    await enqueue_scoring(ctx["redis"], unscored)
    for source_id in source_ids:
        await ctx["redis"].enqueue_job(
            "poll_source", str(source_id), _job_id=poll_job_id(source_id)
        )
    return len(source_ids)


async def poll_source(ctx: dict[str, Any], source_id: str) -> int:
    async with SessionLocal() as db:
        source = await db.get(Source, uuid.UUID(source_id))
        if source is None or not source.is_active:
            return 0
        adapter = get_adapter(source.adapter)
        if not adapter.can_poll:
            return 0
        new_ids = await ingest_service.poll_source(db, source, adapter)
    if new_ids:
        logger.info("Source %s: %d new post(s)", source_id, len(new_ids))
        await enqueue_scoring(ctx["redis"], new_ids)
    return len(new_ids)


async def score_post(ctx: dict[str, Any], post_id: str) -> bool:
    async with SessionLocal() as db:
        relevant = await drafting_service.score_post(
            db, uuid.UUID(post_id), get_llm_client(), get_settings().relevance_threshold
        )
    if relevant:
        await ctx["redis"].enqueue_job(
            "draft_comments", post_id, _job_id=f"draft_comments:{post_id}"
        )
    return relevant


async def draft_comments(ctx: dict[str, Any], post_id: str) -> int:
    async with SessionLocal() as db:
        try:
            drafts = await drafting_service.draft_comments(db, uuid.UUID(post_id), get_llm_client())
        except LLMError as e:
            logger.warning("Drafting post %s failed: %s", post_id, e)
            await db.rollback()
            audit_service.record(
                db,
                actor=None,
                action="post.draft_failed",
                entity_type="post",
                entity_id=uuid.UUID(post_id),
                payload={"error": str(e)},
            )
            await db.commit()
            return 0
    return len(drafts)
