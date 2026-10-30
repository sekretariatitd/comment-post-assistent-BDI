import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import PostStatus
from app.schemas.draft import DraftOut


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    platform_post_id: str
    url: str
    text: str
    thumbnail_url: str | None
    published_at: datetime | None
    fetched_at: datetime
    relevance_score: float | None
    relevance_reason: str | None
    status: PostStatus
    created_at: datetime
    drafts: list[DraftOut] = []


class PostPage(BaseModel):
    items: list[PostOut]
    total: int
    limit: int
    offset: int


class ManualPostCreate(BaseModel):
    source_id: uuid.UUID
    url: str = Field(min_length=8, max_length=2000)
    text: str = Field(min_length=1, max_length=10000)
    published_at: datetime | None = None


class PayloadImport(BaseModel):
    # A Facebook GraphQL response or page HTML copied from the browser's DevTools.
    payload: str = Field(min_length=2, max_length=10_000_000)


class ImportResult(BaseModel):
    found: int
    new: int
    new_post_ids: list[uuid.UUID] = []
