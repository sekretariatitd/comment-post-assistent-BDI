from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_secret
from app.models import Platform, PostingAccount, User
from app.schemas.posting_account import PostingAccountUpdate
from app.services import audit_service


async def list_accounts(db: AsyncSession) -> list[PostingAccount]:
    result = await db.execute(select(PostingAccount).order_by(PostingAccount.platform))
    return list(result.scalars().all())


async def upsert(
    db: AsyncSession, actor: User, platform: Platform, body: PostingAccountUpdate
) -> PostingAccount:
    """One account per platform (unique constraint). Credentials are encrypted at rest and
    never returned or logged; an empty string clears them, None leaves them unchanged."""
    account = await db.scalar(select(PostingAccount).where(PostingAccount.platform == platform))
    if account is None:
        account = PostingAccount(platform=platform, display_name=body.display_name)
        db.add(account)
    account.display_name = body.display_name
    account.is_active = body.is_active
    credentials_changed = body.credentials is not None
    if credentials_changed:
        account.encrypted_credentials = (
            encrypt_secret(body.credentials) if body.credentials else None
        )
    await db.flush()
    audit_service.record(
        db,
        actor=actor,
        action="posting_account.updated",
        entity_type="posting_account",
        entity_id=account.id,
        payload={
            "platform": platform.value,
            "display_name": account.display_name,
            "is_active": account.is_active,
            "credentials_changed": credentials_changed,
        },
    )
    await db.commit()
    return account
