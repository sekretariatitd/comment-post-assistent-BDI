import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sources import ADAPTERS
from app.models import Platform, PromptTemplate, Source, User
from app.schemas.source import SourceCreate, SourceUpdate
from app.services import audit_service
from app.services.errors import InvalidInputError, NotFoundError

# Adapter used to fetch posts for each platform unless one is given explicitly.
DEFAULT_ADAPTERS: dict[Platform, str] = {
    Platform.rss: "rss",
    Platform.manual: "manual",
    Platform.facebook: "meta_graph",
    # TODO: no TikTok fetcher yet (see app.adapters.sources); posts are added by hand.
    Platform.tiktok: "manual",
}
KNOWN_ADAPTERS = frozenset(ADAPTERS)

NULLABLE_FIELDS = {"prompt_template_id"}


async def list_sources(db: AsyncSession) -> Sequence[Source]:
    result = await db.execute(select(Source).order_by(Source.display_name))
    return result.scalars().all()


async def get_source(db: AsyncSession, source_id: uuid.UUID) -> Source:
    source = await db.get(Source, source_id)
    if source is None:
        raise NotFoundError("Source not found")
    return source


async def _check_template(db: AsyncSession, template_id: uuid.UUID | None) -> None:
    if template_id is not None and await db.get(PromptTemplate, template_id) is None:
        raise InvalidInputError("Template does not exist")


def _check_values(values: dict[str, Any]) -> None:
    adapter = values.get("adapter")
    if adapter is not None and adapter not in KNOWN_ADAPTERS:
        raise InvalidInputError(f"Unknown adapter '{adapter}'")
    url = values.get("url_or_handle")
    if values.get("platform") == Platform.rss and url is not None:
        if not url.startswith(("http://", "https://")):
            raise InvalidInputError("RSS sources need a feed URL starting with http:// or https://")


async def create_source(db: AsyncSession, actor: User, body: SourceCreate) -> Source:
    values = body.model_dump()
    values["adapter"] = values["adapter"] or DEFAULT_ADAPTERS[body.platform]
    _check_values(values)
    await _check_template(db, body.prompt_template_id)

    source = Source(**values)
    db.add(source)
    await db.flush()
    audit_service.record(
        db,
        actor=actor,
        action="source.created",
        entity_type="source",
        entity_id=source.id,
        payload={"display_name": source.display_name, "platform": source.platform.value},
    )
    await db.commit()
    return source


async def update_source(
    db: AsyncSession, actor: User, source_id: uuid.UUID, body: SourceUpdate
) -> Source:
    source = await get_source(db, source_id)
    requested = body.model_dump(exclude_unset=True)
    if nulls := [k for k, v in requested.items() if v is None and k not in NULLABLE_FIELDS]:
        raise InvalidInputError(f"Fields cannot be null: {', '.join(sorted(nulls))}")

    # Switching platform without naming an adapter switches to that platform's default adapter.
    if "platform" in requested and "adapter" not in requested:
        requested["adapter"] = DEFAULT_ADAPTERS[requested["platform"]]
    _check_values({"platform": source.platform, "url_or_handle": source.url_or_handle} | requested)
    if "prompt_template_id" in requested:
        await _check_template(db, requested["prompt_template_id"])

    changed = {k: v for k, v in requested.items() if getattr(source, k) != v}
    if not changed:
        return source
    for key, value in changed.items():
        setattr(source, key, value)

    audit_service.record(
        db,
        actor=actor,
        action="source.updated",
        entity_type="source",
        entity_id=source.id,
        payload={"changed": sorted(changed)},
    )
    await db.commit()
    return source


async def delete_source(db: AsyncSession, actor: User, source_id: uuid.UUID) -> None:
    source = await get_source(db, source_id)
    await db.delete(source)
    audit_service.record(
        db,
        actor=actor,
        action="source.deleted",
        entity_type="source",
        entity_id=source_id,
        payload={"display_name": source.display_name},
    )
    await db.commit()
