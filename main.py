import uvicorn # type: ignore
from app.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        # Auto-reload on file changes in development only
        reload=settings.app_env == "development",
        log_level="info",
    )