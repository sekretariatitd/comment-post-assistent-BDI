import uuid

from arq import ArqRedis
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.llm.client import LLMClient, get_llm_client
from app.models import DraftStatus, Post, PostStatus, User
from app.schemas.draft import DraftOut, RegenerateRequest
from app.schemas.post import ImportResult, ManualPostCreate, PayloadImport, PostOut, PostPage
from app.services import drafting_service, post_service
from app.workers.queue import enqueue_scoring, get_queue

router = APIRouter(prefix="/posts", tags=["posts"])


async def _with_drafts(db: AsyncSession, posts: list[Post]) -> list[PostOut]:
    drafts = await drafting_service.drafts_for_posts(db, [p.id for p in posts])
    return [
        PostOut.model_validate(p).model_copy(
            update={"drafts": [DraftOut.model_validate(d) for d in drafts[p.id]]}
        )
        for p in posts
    ]


@router.get("", response_model=PostPage)
async def list_posts(
    status: PostStatus | None = None,
    source_id: uuid.UUID | None = None,
    min_score: float | None = Query(default=None, ge=0, le=1),
    review: DraftStatus | None = Query(
        default=None, description="Posts with a draft in this state"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PostPage:
    items, total = await post_service.list_posts(
        db,
        status=status,
        source_id=source_id,
        min_score=min_score,
        draft_status=review,
        limit=limit,
        offset=offset,
    )
    return PostPage(items=await _with_drafts(db, items), total=total, limit=limit, offset=offset)


@router.post("", response_model=PostOut, status_code=status.HTTP_201_CREATED)
async def add_manual_post(
    body: ManualPostCreate,
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_queue),
    user: User = Depends(get_current_user),
) -> PostOut:
    post = await post_service.add_manual_post(db, user, body)
    await enqueue_scoring(queue, [post.id])
    return (await _with_drafts(db, [post]))[0]


@router.post("/import/{source_id}", response_model=ImportResult)
async def import_posts(
    source_id: uuid.UUID,
    body: PayloadImport,
    db: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_queue),
    user: User = Depends(get_current_user),
) -> ImportResult:
    found, new_ids = await post_service.import_payload(db, user, source_id, body.payload)
    await enqueue_scoring(queue, new_ids)
    return ImportResult(found=found, new=len(new_ids), new_post_ids=new_ids)


@router.get("/{post_id}", response_model=PostOut)
async def get_post(
    post_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
) -> PostOut:
    return (await _with_drafts(db, [await post_service.get_post(db, post_id)]))[0]


@router.post("/{post_id}/regenerate", response_model=PostOut)
async def regenerate(
    post_id: uuid.UUID,
    body: RegenerateRequest,
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
    user: User = Depends(get_current_user),
) -> PostOut:
    """Draft (or redraft) comments now, whatever the relevance score. A person asked for it."""
    await drafting_service.draft_comments(
        db, post_id, llm, template_id=body.template_id, actor=user
    )
    return (await _with_drafts(db, [await post_service.get_post(db, post_id)]))[0]
