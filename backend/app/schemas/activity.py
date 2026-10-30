import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ActivityOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    actor_email: str | None  # None = done by the system (a background job)
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    payload: dict[str, Any]


class ActivityPage(BaseModel):
    items: list[ActivityOut]
    total: int
    limit: int
    offset: int


class AppSettingsOut(BaseModel):
    relevance_threshold: float
    max_comments_per_hour: int
    enable_automated_publishing: bool
    anthropic_model: str
    anthropic_configured: bool
