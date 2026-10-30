import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User


async def list_activity(
    db: AsyncSession,
    *,
    action_prefix: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[AuditLog, str | None]], int]:
    filters = []
    if action_prefix:
        filters.append(AuditLog.action.startswith(action_prefix))
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)
    if entity_id:
        filters.append(AuditLog.entity_id == entity_id)
    if actor_id:
        filters.append(AuditLog.actor_id == actor_id)

    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    rows = await db.execute(
        select(AuditLog, User.email)
        .outerjoin(User, User.id == AuditLog.actor_id)
        .where(*filters)
        .order_by(AuditLog.created_at.desc(), AuditLog.id)
        .limit(limit)
        .offset(offset)
    )
    return [(log, email) for log, email in rows.all()], total
