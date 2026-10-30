import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models import User, UserRole

# Compared against when the email doesn't exist, so response time doesn't reveal valid emails.
_DUMMY_HASH = hash_password("not-a-real-password")


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(func.lower(User.email) == normalize_email(email)))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    """Return the active user matching the credentials, or None."""
    user = await get_user_by_email(db, email)
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.password_hash) or not user.is_active:
        return None
    return user


async def create_user(
    db: AsyncSession, email: str, password: str, role: UserRole = UserRole.reviewer
) -> User:
    user = User(email=normalize_email(email), password_hash=hash_password(password), role=role)
    db.add(user)
    await db.flush()
    return user
