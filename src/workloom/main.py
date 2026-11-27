"""FastAPI application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from workloom import __version__
from workloom.api.v1 import router as api_router
from workloom.api.v1.webhooks import register_bot_commands
from workloom.core.config import get_settings
from workloom.core.database import close_db
from workloom.core.logging import configure_logging
from workloom.modules import module_registry
from workloom.modules.callcenter.config import callcenter_config
from workloom.modules.dashboard.config import dashboard_config
from workloom.modules.documents.vector_store import FileVectorStore
from workloom.modules.hr.config import hr_config
from workloom.modules.hr.retention import setup_hr_retention_scheduler
from workloom.modules.marketing.config import marketing_config
from workloom.modules.media.vector_store import MediaTranscriptionVectorStore


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup - register department modules
    module_registry.register(dashboard_config)
    module_registry.register(callcenter_config)
    module_registry.register(marketing_config)
    module_registry.register(hr_config)

    # Ensure Qdrant collections
    settings = get_settings()
    await FileVectorStore(settings).ensure_collection()
    await MediaTranscriptionVectorStore(settings).ensure_collection()

    # Ensure HR directories exist (config-driven, no hard-coded paths)
    Path(settings.hr_upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.hr_render_dir).mkdir(parents=True, exist_ok=True)

    # SQL schema is owned by Alembic (`alembic upgrade head` in CD).
    # Do NOT create tables here — it would bypass the migration chain and
    # leave alembic_version out of sync with the real schema.

    # Register Telegram bot commands (/start, /new, /products, /contact)
    await register_bot_commands()

    # Start APScheduler for HR retention cleanup
    scheduler = AsyncIOScheduler(timezone="UTC")
    setup_hr_retention_scheduler(scheduler)
    scheduler.start()

    yield

    # Shutdown
    scheduler.shutdown()
    await close_db()


# Configure logging before anything logs (must run at import, before the app).
configure_logging()

settings = get_settings()

app = FastAPI(
    title="Workloom Platform",
    description="Modular enterprise AI & knowledge operations platform",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "name": "Workloom Platform",
        "version": __version__,
        "docs": "/docs",
    }
