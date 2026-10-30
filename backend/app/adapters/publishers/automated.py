from app.adapters.publishers.base import PublishResult
from app.models import Draft, Post, PostingAccount


class AutomatedPublisher:
    """Interface only. Posting through an official platform API would go here, gated by
    ENABLE_AUTOMATED_PUBLISHING. No browser automation in this build."""

    key = "automated"

    async def publish(self, draft: Draft, post: Post, account: PostingAccount) -> PublishResult:
        raise NotImplementedError("Automated publishing is not implemented in this build.")
