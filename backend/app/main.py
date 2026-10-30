import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.session import engine
from app.llm.client import LLMError, LLMNotConfiguredError, LLMRefusalError
from app.services.errors import ServiceError

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title="News Comment Assistant", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.exception_handler(ServiceError)
async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(LLMError)
async def llm_error_handler(_: Request, exc: LLMError) -> JSONResponse:
    if isinstance(exc, LLMNotConfiguredError):
        status_code = 503
    elif isinstance(exc, LLMRefusalError):
        status_code = 422
    else:
        status_code = 502
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


@app.get("/health", tags=["health"])
async def health() -> JSONResponse:
    checks: dict[str, str] = {}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.exception("Health check: database unavailable")
        checks["database"] = "error"
    try:
        redis = Redis.from_url(settings.redis_url)
        try:
            await redis.ping()
        finally:
            await redis.aclose()
        checks["redis"] = "ok"
    except Exception:
        logger.exception("Health check: redis unavailable")
        checks["redis"] = "error"

    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )
