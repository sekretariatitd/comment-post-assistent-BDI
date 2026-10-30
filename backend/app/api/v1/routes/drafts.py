import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Draft, DraftStatus, User
from app.schemas.draft import DraftOut

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
