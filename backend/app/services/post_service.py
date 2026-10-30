import uuid
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sources import FetchedPost, facebook_payload, tiktok_payload
from app.adapters.sources.browser_payload import PayloadError
from app.models import Platform, Post, PostStatus, User
from app.schemas.post import ManualPostCreate
from app.services import audit_service, ingest_service, source_service
from app.services.errors import ConflictError, InvalidInputError, NotFoundError


async def list_posts(
    db: AsyncSession,
    *,
    status: PostStatus | None = None,
    source_id: uuid.UUID | None = None,
    min_score: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Post], int]:
    filters = []
    if status is not None:
        filters.append(Post.status == status)
    if source_id is not None:
        filters.append(Post.source_id == source_id)
    if min_score is not None:
        filters.append(Post.relevance_score >= min_score)

    total = await db.scalar(select(func.count()).select_from(Post).where(*filters)) or 0
    newest = func.coalesce(Post.published_at, Post.fetched_at).desc()
    result = await db.execute(
        select(Post).where(*filters).order_by(newest, Post.id).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def get_post(db: AsyncSession, post_id: uuid.UUID) -> Post:
    post = await db.get(Post, post_id)
    if post is None:
        raise NotFoundError("Post not found")
    return post


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise InvalidInputError("Post URL must start with http:// or https://")
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, parts.query, ""))


async def add_manual_post(db: AsyncSession, actor: User, body: ManualPostCreate) -> Post:
    """Add a post by hand (any source: manual, Facebook, TikTok, ...). The URL is its identity."""
    source = await source_service.get_source(db, body.source_id)
    url = normalize_url(body.url)
    post_id = url if len(url) <= 500 else url[:500]

    new_ids = await ingest_service.insert_posts(
        db,
        source.id,
        [
            FetchedPost(
                platform_post_id=post_id,
                url=url,
                text=body.text.strip(),
                published_at=body.published_at,
            )
        ],
    )
    if not new_ids:
        raise ConflictError("This post was already added to this source.")

    audit_service.record(
        db,
        actor=actor,
        action="post.added_manually",
        entity_type="post",
        entity_id=new_ids[0],
        payload={"source_id": str(source.id), "url": url},
    )
    await db.commit()
    return await get_post(db, new_ids[0])


async def import_payload(
    db: AsyncSession, actor: User, source_id: uuid.UUID, payload: str
) -> tuple[int, list[uuid.UUID]]:
    """Store the posts found in a payload copied from the browser. Returns (found, new ids)."""
    source = await source_service.get_source(db, source_id)
    try:
        if source.platform == Platform.tiktok:
            handle = tiktok_payload.handle_from(source.url_or_handle)
            posts = tiktok_payload.parse_payload(payload, default_handle=handle)
        else:
            posts = facebook_payload.parse_payload(payload)
    except PayloadError as e:
        raise InvalidInputError(str(e)) from None
    if not posts:
        raise InvalidInputError("No posts found in what you pasted.")

    new_ids = await ingest_service.insert_posts(db, source.id, posts)
    audit_service.record(
        db,
        actor=actor,
        action="source.imported",
        entity_type="source",
        entity_id=source.id,
        payload={"found": len(posts), "new_posts": len(new_ids)},
    )
    await db.commit()
    return len(posts), new_ids
