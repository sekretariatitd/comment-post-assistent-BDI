import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models import Platform


class PostingAccountUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    is_active: bool = True
    # Not needed for manual publishing. Encrypted at rest; never returned by the API.
    credentials: str | None = Field(default=None, max_length=10_000)


class PostingAccountOut(BaseModel):
    id: uuid.UUID
    platform: Platform
    display_name: str
    is_active: bool
    has_credentials: bool
    updated_at: datetime
