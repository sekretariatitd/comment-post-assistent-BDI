from dataclasses import dataclass
from typing import Protocol

from app.models import Draft, Post, PostingAccount


@dataclass(frozen=True)
class PublishResult:
    external_id: str | None = None  # the platform's id for the comment, when known


class Publisher(Protocol):
    key: str

    async def publish(self, draft: Draft, post: Post, account: PostingAccount) -> PublishResult:
        """Publish the draft's final text as `account`. Raise on failure."""
        ...
