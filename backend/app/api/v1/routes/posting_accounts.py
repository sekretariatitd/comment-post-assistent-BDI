from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models import Platform, PostingAccount, User
from app.schemas.posting_account import PostingAccountOut, PostingAccountUpdate
from app.services import posting_account_service

router = APIRouter(prefix="/posting-accounts", tags=["posting accounts"])


def _out(account: PostingAccount) -> PostingAccountOut:
    # Never include the credentials themselves, encrypted or not.
    return PostingAccountOut(
        id=account.id,
        platform=account.platform,
        display_name=account.display_name,
        is_active=account.is_active,
        has_credentials=account.encrypted_credentials is not None,
        updated_at=account.updated_at,
    )


@router.get("", response_model=list[PostingAccountOut])
async def list_accounts(
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
) -> list[PostingAccountOut]:
    return [_out(a) for a in await posting_account_service.list_accounts(db)]


@router.put("/{platform}", response_model=PostingAccountOut)
async def upsert_account(
    platform: Platform,
    body: PostingAccountUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> PostingAccountOut:
    return _out(await posting_account_service.upsert(db, user, platform, body))
