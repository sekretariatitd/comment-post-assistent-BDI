import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, str_enum
from app.models.enums import PostStatus


class Post(TimestampMixin, Base):
    __tablename__ = "posts"
    __table_args__ = (sa.UniqueConstraint("source_id", "platform_post_id"),)

    source_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    platform_post_id: Mapped[str] = mapped_column(sa.String(500))
    url: Mapped[str] = mapped_column(sa.String(2000))
    text: Mapped[str] = mapped_column(sa.Text)
    thumbnail_url: Mapped[str | None] = mapped_column(sa.String(2000))
    published_at: Mapped[datetime | None]
    fetched_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())
    relevance_score: Mapped[float | None]
    relevance_reason: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[PostStatus] = mapped_column(
        str_enum(PostStatus, "post_status"),
        default=PostStatus.new,
        server_default=PostStatus.new.value,
        index=True,
    )
