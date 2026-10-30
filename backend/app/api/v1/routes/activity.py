import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import User
from app.schemas.activity import ActivityOut, ActivityPage, AppSettingsOut
from app.services import activity_service

router = APIRouter(tags=["activity"])


@router.get("/activity", response_model=ActivityPage)
async def list_activity(
    action: str | None = Query(default=None, max_length=100, description="Action prefix"),
    entity_type: str | None = Query(default=None, max_length=50),
    entity_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ActivityPage:
    rows, total = await activity_service.list_activity(
        db,
        action_prefix=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        limit=limit,
        offset=offset,
    )
    items = [
        ActivityOut(
            id=log.id,
            created_at=log.created_at,
            actor_email=email,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            payload=log.payload,
        )
        for log, email in rows
    ]
    return ActivityPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/settings", response_model=AppSettingsOut)
async def app_settings(_: User = Depends(get_current_user)) -> AppSettingsOut:
    s = get_settings()
    return AppSettingsOut(
        relevance_threshold=s.relevance_threshold,
        max_comments_per_hour=s.max_comments_per_hour,
        enable_automated_publishing=s.enable_automated_publishing,
        anthropic_model=s.anthropic_model,
        anthropic_configured=bool(s.anthropic_api_key),
    )
