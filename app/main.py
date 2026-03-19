import logging
from fastapi import FastAPI # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from app.core.config import get_settings
from app.api.routes import verification

# Configure logging for the whole app
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    App factory pattern — creates and configures the FastAPI instance.
    Keeping this in a function makes it easy to create test instances later.
    """
    settings = get_settings()

    app = FastAPI(
        title="ID Verification Engine",
        description="Internal AI engine — not publicly accessible",
        version="1.0.0",
        # Disable docs in production — no need to expose internals
        docs_url="/docs" if settings.app_env == "development" else None,
        redoc_url=None,
    )

    # ── CORS ──────────────────────────────────────────
    # Only the NestJS gateway (localhost:3001) can reach this service
    # In production this would be the internal network address
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3001"],
        allow_methods=["POST"],
        allow_headers=["X-Internal-API-Key", "Content-Type"],
    )

    # ── Routes ────────────────────────────────────────
    app.include_router(verification.router, prefix="/api/v1")

    # ── Startup log ───────────────────────────────────
    @app.on_event("startup")
    async def on_startup():
        logger.info(f"ID Verification Engine started in {settings.app_env} mode")
        logger.info(f"Running on http://{settings.app_host}:{settings.app_port}")

    return app


# Create the app instance
app = create_app()