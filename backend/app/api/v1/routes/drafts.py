import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.publishers import ManualPublisher
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Draft, DraftStatus, User
from app.schemas.draft import DraftEdit, DraftOut
from app.services import review_service

router = APIRouter(prefix="/drafts", tags=["drafts"])


@router.get("", response_model=list[DraftOut])
async def list_drafts(
    status: DraftStatus | None = None,
    post_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Draft]:
    query = select(Draft).order_by(Draft.created_at.desc(), Draft.id).limit(limit)
    if status is not None:
        query = query.where(Draft.status == status)
    if post_id is not None:
        query = query.where(Draft.post_id == post_id)
    return list((await db.execute(query)).scalars().all())


@router.patch("/{draft_id}", response_model=DraftOut)
async def edit_draft(
    draft_id: uuid.UUID,
    body: DraftEdit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Draft:
    return await review_service.edit(db, user, draft_id, body.text)


@router.post("/{draft_id}/approve", response_model=DraftOut)
async def approve_draft(
    draft_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> Draft:
    return await review_service.approve(db, user, draft_id)


@router.post("/{draft_id}/reject", response_model=DraftOut)
async def reject_draft(
    draft_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> Draft:
    return await review_service.reject(db, user, draft_id)


@router.post("/{draft_id}/mark-published", response_model=DraftOut)
async def mark_published(
    draft_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> Draft:
    """A reviewer posted the approved comment by hand; record it (manual publisher)."""
    return await review_service.publish(db, draft_id, ManualPublisher(), actor=user)
