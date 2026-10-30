"""Create the first admin user from ADMIN_EMAIL / ADMIN_PASSWORD. Safe to run repeatedly."""

import asyncio
import logging

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.models import UserRole
from app.services import auth_service

logging.basicConfig(level=logging.INFO, format="%(levelname)s [seed] %(message)s")
logger = logging.getLogger(__name__)


async def seed() -> None:
    settings = get_settings()
    if not settings.admin_email or not settings.admin_password:
        logger.warning("ADMIN_EMAIL / ADMIN_PASSWORD not set; skipping admin seed")
        return

    async with SessionLocal() as db:
        if await auth_service.get_user_by_email(db, settings.admin_email):
            logger.info("Admin %s already exists", settings.admin_email)
            return
        await auth_service.create_user(
            db, settings.admin_email, settings.admin_password, role=UserRole.admin
        )
        await db.commit()
        logger.info("Created admin %s", settings.admin_email)


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
