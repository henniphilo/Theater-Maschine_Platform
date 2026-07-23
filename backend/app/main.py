from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.routes.chat import router as chat_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.debate import router as debate_router, tts_router
from app.api.routes.director import router as director_router
from app.api.routes.media import router as media_router
from app.api.routes.inszenierung import router as inszenierung_router
from app.api.routes.productions import router as productions_router
from app.api.routes.script import router as script_router
from app.api.routes.health import router as health_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.director.outputs.avatar_done_listener import (
    start_avatar_done_listener,
    stop_avatar_done_listener,
)

configure_logging()
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if settings.avatar_done_gate_enabled:
        start_avatar_done_listener(
            host=settings.avatar_done_osc_host,
            port=settings.avatar_done_osc_port,
        )
    try:
        yield
    finally:
        stop_avatar_done_listener()


app = FastAPI(title=settings.app_name, debug=settings.app_debug, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(debate_router, prefix="/api/v1")
app.include_router(tts_router, prefix="/api/v1")
app.include_router(director_router, prefix="/api/v1")
app.include_router(script_router, prefix="/api/v1")
app.include_router(inszenierung_router, prefix="/api/v1")
app.include_router(productions_router, prefix="/api/v1")
app.include_router(media_router, prefix="/api/v1")
