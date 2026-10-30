import enum


class UserRole(enum.StrEnum):
    admin = "admin"
    reviewer = "reviewer"


class Platform(enum.StrEnum):
    tiktok = "tiktok"
    facebook = "facebook"
    rss = "rss"
    manual = "manual"


class PostStatus(enum.StrEnum):
    new = "new"
    skipped = "skipped"
    drafted = "drafted"


class DraftStatus(enum.StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    published = "published"
    failed = "failed"


class SourceStance(enum.StrEnum):
    """Our account's relationship to the author of a source's posts."""

    ally = "ally"
    opponent = "opponent"
    neutral = "neutral"
