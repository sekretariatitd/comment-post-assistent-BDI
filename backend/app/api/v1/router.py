from fastapi import APIRouter

from app.api.v1.routes import (
    activity,
    auth,
    drafts,
    posting_accounts,
    posts,
    sources,
    templates,
    ws,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(sources.router)
api_router.include_router(templates.router)
api_router.include_router(posts.router)
api_router.include_router(drafts.router)
api_router.include_router(activity.router)
api_router.include_router(posting_accounts.router)
api_router.include_router(ws.router)
