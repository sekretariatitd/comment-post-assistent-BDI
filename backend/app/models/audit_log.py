import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        sa.Index("ix_audit_log_entity", "entity_type", "entity_id"),
        sa.Index("ix_audit_log_created_at", "created_at"),
    )

    # Null when the action was taken by the system (e.g. a background job).
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(sa.String(100))
    entity_type: Mapped[str] = mapped_column(sa.String(50))
    entity_id: Mapped[uuid.UUID | None]
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default="{}")
