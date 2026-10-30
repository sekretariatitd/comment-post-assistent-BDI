import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, str_enum
from app.models.enums import Platform, SourceStance


class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    platform: Mapped[Platform] = mapped_column(str_enum(Platform, "source_platform"))
    display_name: Mapped[str] = mapped_column(sa.String(200))
    url_or_handle: Mapped[str] = mapped_column(sa.String(2000))
    # Key of the SourceAdapter used to fetch posts (e.g. "rss", "manual").
    adapter: Mapped[str] = mapped_column(sa.String(50))
    prompt_template_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("prompt_templates.id", ondelete="RESTRICT")
    )
    # Tells the AI whether to back or criticise this author, whichever template is used.
    stance: Mapped[SourceStance] = mapped_column(
        str_enum(SourceStance, "source_stance"),
        default=SourceStance.neutral,
        server_default=SourceStance.neutral.value,
    )
    poll_interval_minutes: Mapped[int] = mapped_column(default=15, server_default="15")
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa.true())
    last_checked_at: Mapped[datetime | None]
