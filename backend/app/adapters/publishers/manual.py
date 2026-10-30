from app.adapters.publishers.base import PublishResult
from app.models import Draft, Post, PostingAccount


class ManualPublisher:
    """A person copies the approved comment, posts it from our account, then clicks
    "Mark as published". By the time this runs the comment is already live; nothing to send."""

    key = "manual"

    async def publish(self, draft: Draft, post: Post, account: PostingAccount) -> PublishResult:
        return PublishResult()
