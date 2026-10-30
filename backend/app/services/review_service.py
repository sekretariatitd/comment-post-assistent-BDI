"""Human review and publishing of drafts. Every state change writes an audit row.

Draft lifecycle: pending -> approved -> published, or pending/approved -> rejected.
An approved draft that is edited goes back to pending and needs approving again, so the
text that gets published is always text a reviewer approved.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.publishers import Publisher
from app.core.config import get_settings
from app.models import (
    Draft,
    DraftStatus,
    Post,
    PostingAccount,
    PromptTemplate,
    Source,
    User,
)
from app.services import audit_service, events
from app.services.errors import (
    ConflictError,
    InvalidInputError,
    NotFoundError,
    RateLimitedError,
)


async def get_draft(db: AsyncSession, draft_id: uuid.UUID) -> Draft:
    draft = await db.get(Draft, draft_id)
    if draft is None:
        raise NotFoundError("Draft not found")
    return draft


def final_text(draft: Draft) -> str:
    return draft.edited_text or draft.text


def _require(draft: Draft, *allowed: DraftStatus, action: str) -> None:
    if draft.status not in allowed:
        raise ConflictError(f"Can't {action} a draft that is {draft.status.value}.")


async def _changed(
    db: AsyncSession, draft: Draft, actor: User | None, action: str, **extra
) -> Draft:
    audit_service.record(
        db,
        actor=actor,
        action=action,
        entity_type="draft",
        entity_id=draft.id,
        payload={"post_id": str(draft.post_id), "status": draft.status.value, **extra},
    )
    await db.commit()
    await events.publish(
        "draft.updated", draft_id=draft.id, post_id=draft.post_id, status=draft.status.value
    )
    return draft


async def edit(db: AsyncSession, actor: User, draft_id: uuid.UUID, text: str) -> Draft:
    draft = await get_draft(db, draft_id)
    _require(draft, DraftStatus.pending, DraftStatus.approved, action="edit")
    text = text.strip()
    if not text:
        raise InvalidInputError("The comment can't be empty.")
    template = await db.get(PromptTemplate, draft.template_id)
    if template and len(text) > template.max_length:
        raise InvalidInputError(f"The comment is longer than {template.max_length} characters.")

    needs_reapproval = draft.status == DraftStatus.approved
    draft.edited_text = None if text == draft.text else text
    if needs_reapproval:
        draft.status = DraftStatus.pending
        draft.reviewer_id = None
        draft.reviewed_at = None
    return await _changed(db, draft, actor, "draft.edited", needs_reapproval=needs_reapproval)


async def approve(db: AsyncSession, actor: User, draft_id: uuid.UUID) -> Draft:
    draft = await get_draft(db, draft_id)
    _require(draft, DraftStatus.pending, action="approve")
    draft.status = DraftStatus.approved
    draft.reviewer_id = actor.id
    draft.reviewed_at = datetime.now(UTC)
    return await _changed(db, draft, actor, "draft.approved", text=final_text(draft))


async def reject(db: AsyncSession, actor: User, draft_id: uuid.UUID) -> Draft:
    draft = await get_draft(db, draft_id)
    _require(draft, DraftStatus.pending, DraftStatus.approved, action="reject")
    draft.status = DraftStatus.rejected
    draft.reviewer_id = actor.id
    draft.reviewed_at = datetime.now(UTC)
    return await _changed(db, draft, actor, "draft.rejected")


async def published_last_hour(db: AsyncSession, platform: object) -> int:
    since = datetime.now(UTC) - timedelta(hours=1)
    return (
        await db.scalar(
            select(func.count())
            .select_from(Draft)
            .join(Post, Post.id == Draft.post_id)
            .join(Source, Source.id == Post.source_id)
            .where(
                Draft.status == DraftStatus.published,
                Draft.published_at >= since,
                Source.platform == platform,
            )
        )
        or 0
    )


async def publish(
    db: AsyncSession, draft_id: uuid.UUID, publisher: Publisher, actor: User | None = None
) -> Draft:
    """Publish an approved draft through `publisher`. Guardrails enforced here, server-side:
    the draft must be approved with a recorded reviewer, the platform must have an active
    posting account, and the per-platform hourly limit must not be exceeded."""
    draft = await get_draft(db, draft_id)
    if draft.status != DraftStatus.approved or draft.reviewer_id is None:
        raise ConflictError("Only drafts approved by a reviewer can be published.")

    post = await db.get(Post, draft.post_id)
    source = await db.get(Source, post.source_id) if post else None
    if post is None or source is None:
        raise NotFoundError("The draft's post no longer exists.")

    account = await db.scalar(
        select(PostingAccount).where(PostingAccount.platform == source.platform)
    )
    if account is None or not account.is_active:
        raise ConflictError(
            f"Set up an active posting account for {source.platform.value} in Settings first."
        )

    limit = get_settings().max_comments_per_hour
    if await published_last_hour(db, source.platform) >= limit:
        raise RateLimitedError(
            f"Limit reached: {limit} comments per hour on {source.platform.value}. Try later."
        )

    try:
        result = await publisher.publish(draft, post, account)
    except Exception as e:  # any publisher failure is recorded on the draft
        draft.status = DraftStatus.failed
        draft.error = str(e)[:2000] or type(e).__name__
        await _changed(db, draft, actor, "draft.publish_failed", publisher=publisher.key)
        raise ConflictError(f"Publishing failed: {draft.error}") from None

    draft.status = DraftStatus.published
    draft.published_at = datetime.now(UTC)
    draft.error = None
    return await _changed(
        db,
        draft,
        actor,
        "draft.published",
        publisher=publisher.key,
        platform=source.platform.value,
        account=account.display_name,
        external_id=result.external_id,
        text=final_text(draft),
    )
