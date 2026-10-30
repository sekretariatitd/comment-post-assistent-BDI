import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, str_enum
from app.models.enums import Platform


class PostingAccount(TimestampMixin, Base):
    """Our single official account per platform. No multi-account rotation."""

    __tablename__ = "posting_accounts"

    platform: Mapped[Platform] = mapped_column(
        str_enum(Platform, "posting_account_platform"), unique=True
    )
    display_name: Mapped[str] = mapped_column(sa.String(200))
    # Fernet ciphertext (see app.core.crypto). Never returned by the API or logged.
    encrypted_credentials: Mapped[str | None] = mapped_column(sa.Text)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa.true())
