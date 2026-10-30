from fastapi import APIRouter

from app.api.v1.routes import auth, drafts, posts, sources, templates

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(sources.router)
api_router.include_router(templates.router)
api_router.include_router(posts.router)
api_router.include_router(drafts.router)
