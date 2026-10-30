import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, str_enum
from app.models.enums import UserRole


class User(TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(sa.String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(sa.String(255))
    role: Mapped[UserRole] = mapped_column(
        str_enum(UserRole, "user_role"), default=UserRole.reviewer
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa.true())
