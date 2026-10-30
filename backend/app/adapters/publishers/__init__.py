from app.adapters.publishers.automated import AutomatedPublisher
from app.adapters.publishers.base import Publisher, PublishResult
from app.adapters.publishers.manual import ManualPublisher
from app.core.config import get_settings


def get_publisher() -> Publisher:
    """The publisher background jobs use. Manual unless ENABLE_AUTOMATED_PUBLISHING is on."""
    if get_settings().enable_automated_publishing:
        return AutomatedPublisher()
    return ManualPublisher()


__all__ = ["AutomatedPublisher", "ManualPublisher", "PublishResult", "Publisher", "get_publisher"]
