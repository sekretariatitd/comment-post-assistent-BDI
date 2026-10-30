import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, str_enum
from app.models.enums import DraftStatus


class Draft(TimestampMixin, Base):
    __tablename__ = "drafts"

    post_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("prompt_templates.id", ondelete="RESTRICT")
    )
    template_version: Mapped[int]
    text: Mapped[str] = mapped_column(sa.Text)
    edited_text: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[DraftStatus] = mapped_column(
        str_enum(DraftStatus, "draft_status"),
        default=DraftStatus.pending,
        server_default=DraftStatus.pending.value,
        index=True,
    )
    model_name: Mapped[str] = mapped_column(sa.String(100))
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None]
    published_at: Mapped[datetime | None]
    error: Mapped[str | None] = mapped_column(sa.Text)
