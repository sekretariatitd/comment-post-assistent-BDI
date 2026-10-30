"""Relevance scoring and comment drafting for stored posts (used by worker jobs and the API)."""

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import LLMClient, LLMError
from app.models import Draft, DraftStatus, Post, PostStatus, PromptTemplate, Source, User
from app.services import audit_service, events, template_service
from app.services.errors import InvalidInputError, NotFoundError

logger = logging.getLogger(__name__)


async def _post_and_source(db: AsyncSession, post_id: uuid.UUID) -> tuple[Post, Source]:
    post = await db.get(Post, post_id)
    if post is None:
        raise NotFoundError("Post not found")
    source = await db.get(Source, post.source_id)
    assert source is not None  # FK
    return post, source


def _skip(post: Post, reason: str) -> None:
    post.status = PostStatus.skipped
    post.relevance_reason = reason


async def score_post(
    db: AsyncSession, post_id: uuid.UUID, llm: LLMClient, threshold: float
) -> bool:
    """Score a new post against its source's template. Returns True when it should be drafted.

    Posts already scored (status other than `new`, or a score set) are left alone.
    """
    post, source = await _post_and_source(db, post_id)
    if post.status != PostStatus.new or post.relevance_score is not None:
        return False

    template = (
        await db.get(PromptTemplate, source.prompt_template_id)
        if source.prompt_template_id
        else None
    )
    if template is None or not template.is_active:
        _skip(post, "The source has no active template, so the post wasn't scored.")
        await db.commit()
        return False

    try:
        result = await template_service.score(
            llm,
            template_service.spec_for(template),
            post.text,
            author=source.display_name,
            stance=source.stance.value,
        )
    except LLMError as e:
        post.relevance_reason = f"Scoring failed: {e}"
        audit_service.record(
            db,
            actor=None,
            action="post.score_failed",
            entity_type="post",
            entity_id=post.id,
            payload={"error": str(e)},
        )
        await db.commit()
        return False

    r = result.value
    post.relevance_score = r.score
    post.relevance_reason = r.reason
    relevant = r.relevant and r.score >= threshold
    if not relevant:
        post.status = PostStatus.skipped
    audit_service.record(
        db,
        actor=None,
        action="post.scored",
        entity_type="post",
        entity_id=post.id,
        payload={
            "score": r.score,
            "relevant": r.relevant,
            "skipped": not relevant,
            "template_id": str(template.id),
            "template_version": template.version,
            "model": result.model,
        },
    )
    await db.commit()
    return relevant


async def draft_comments(
    db: AsyncSession,
    post_id: uuid.UUID,
    llm: LLMClient,
    *,
    template_id: uuid.UUID | None = None,
    actor: User | None = None,
) -> list[Draft]:
    """Generate pending drafts for a post, superseding its earlier pending drafts.

    Uses `template_id` when given (a person choosing a stance), otherwise the source's template.
    Raises LLMError if generation fails; nothing is changed in that case.
    """
    post, source = await _post_and_source(db, post_id)
    template_id = template_id or source.prompt_template_id
    template = await db.get(PromptTemplate, template_id) if template_id else None
    if template is None:
        raise InvalidInputError("Choose a template: this post's source doesn't have one.")

    result = await template_service.draft(
        llm,
        template_service.spec_for(template),
        post.text,
        author=source.display_name,
        stance=source.stance.value,
    )
    texts = [t.strip() for t in result.value.drafts if t.strip()][:3]

    old = await db.execute(
        select(Draft).where(Draft.post_id == post.id, Draft.status == DraftStatus.pending)
    )
    for draft in old.scalars():
        draft.status = DraftStatus.rejected
        audit_service.record(
            db,
            actor=actor,
            action="draft.superseded",
            entity_type="draft",
            entity_id=draft.id,
            payload={"post_id": str(post.id)},
        )

    # Explicit timestamps keep the drafts in generation order (now() is fixed per transaction).
    now = datetime.now(UTC)
    drafts = [
        Draft(
            post_id=post.id,
            template_id=template.id,
            template_version=template.version,
            text=text,
            model_name=result.model,
            created_at=now + timedelta(microseconds=i),
        )
        for i, text in enumerate(texts)
    ]
    db.add_all(drafts)
    await db.flush()
    for draft in drafts:
        audit_service.record(
            db,
            actor=actor,
            action="draft.created",
            entity_type="draft",
            entity_id=draft.id,
            payload={
                "post_id": str(post.id),
                "template_id": str(template.id),
                "template_version": template.version,
                "model": result.model,
            },
        )
    post.status = PostStatus.drafted
    await db.commit()
    for draft in drafts:
        await events.publish("draft.created", draft_id=draft.id, post_id=post.id)
    return drafts


async def drafts_for_posts(
    db: AsyncSession, post_ids: Sequence[uuid.UUID], include_rejected: bool = False
) -> dict[uuid.UUID, list[Draft]]:
    if not post_ids:
        return {}
    query = select(Draft).where(Draft.post_id.in_(post_ids)).order_by(Draft.created_at, Draft.id)
    if not include_rejected:
        query = query.where(Draft.status != DraftStatus.rejected)
    by_post: dict[uuid.UUID, list[Draft]] = {pid: [] for pid in post_ids}
    for draft in (await db.execute(query)).scalars():
        by_post[draft.post_id].append(draft)
    return by_post


async def unscored_post_ids(db: AsyncSession, limit: int = 20) -> list[uuid.UUID]:
    """New posts that were never scored (e.g. stored while the worker was down)."""
    result = await db.execute(
        select(Post.id)
        .where(
            Post.status == PostStatus.new,
            Post.relevance_score.is_(None),
            Post.relevance_reason.is_(None),
        )
        .order_by(Post.created_at)
        .limit(limit)
    )
    return list(result.scalars().all())
