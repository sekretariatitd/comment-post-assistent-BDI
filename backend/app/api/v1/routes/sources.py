import uuid

from arq import ArqRedis
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sources import get_adapter
from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models import Source, User
from app.schemas.source import PollQueued, SourceCreate, SourceOut, SourceUpdate
from app.services import source_service
from app.services.errors import ConflictError
from app.workers.queue import get_queue, poll_job_id

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceOut])
async def list_sources(
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
) -> list[Source]:
    return list(await source_service.list_sources(db))


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: SourceCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)
) -> Source:
    return await source_service.create_source(db, user, body)


@router.get("/{source_id}", response_model=SourceOut)
async def get_source(
    source_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
) -> Source:
    return await source_service.get_source(db, source_id)


@router.patch("/{source_id}", response_model=SourceOut)
async def update_source(
    source_id: uuid.UUID,
    body: SourceUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> Source:
    return await source_service.update_source(db, user, source_id, body)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)
) -> None:
    await source_service.delete_source(db, user, source_id)


@router.post(
    "/{source_id}/poll-now", response_model=PollQueued, status_code=status.HTTP_202_ACCEPTED
)
async def poll_now(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_queue),
    _: User = Depends(get_current_user),
) -> PollQueued:
    source = await source_service.get_source(db, source_id)
    if not get_adapter(source.adapter).can_poll:
        raise ConflictError(
            f"'{source.adapter}' sources can't be fetched automatically. Add posts by hand instead."
        )
    job = await queue.enqueue_job("poll_source", str(source.id), _job_id=poll_job_id(source.id))
    # None means a poll for this source is already queued, which is fine.
    return PollQueued(queued=job is not None)
