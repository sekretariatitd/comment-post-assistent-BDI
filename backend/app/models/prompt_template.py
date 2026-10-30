import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PromptTemplate(TimestampMixin, Base):
    __tablename__ = "prompt_templates"

    name: Mapped[str] = mapped_column(sa.String(200))
    system_prompt: Mapped[str] = mapped_column(sa.Text)
    tone: Mapped[str] = mapped_column(sa.String(100))
    language: Mapped[str] = mapped_column(sa.String(50))
    max_length: Mapped[int]
    # What to engage with and what to skip.
    relevance_rules: Mapped[str] = mapped_column(sa.Text)
    # Output style switches, enforced on every draft after generation (not just prompted).
    plain_e: Mapped[bool] = mapped_column(default=False, server_default=sa.false())  # ë, ç -> e, c
    no_dashes: Mapped[bool] = mapped_column(default=False, server_default=sa.false())
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa.true())
