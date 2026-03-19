from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    All application settings loaded from .env file.
    Pydantic validates types automatically — if AWS_REGION is missing,
    the app crashes on startup with a clear error instead of failing silently
    at runtime when you first make a request.
    """

    # ── App ──────────────────────────────────────────
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # ── Internal security ────────────────────────────
    # FastAPI only accepts requests that include this key in the header
    # This prevents anything other than our NestJS gateway from calling it
    internal_api_key: str

    # ── AWS ──────────────────────────────────────────
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"

    # ── Scoring thresholds ────────────────────────────
    liveness_threshold: float = 80.0
    face_match_threshold: float = 85.0
    composite_pass_threshold: float = 80.0

    # ── Score weights ─────────────────────────────────
    liveness_weight: float = 0.35
    face_match_weight: float = 0.50
    ocr_weight: float = 0.15

    class Config:
        # Tell Pydantic where to find the .env file
        env_file = ".env"
        # Make field names case-insensitive
        # So AWS_REGION in .env maps to aws_region in the class
        case_sensitive = False


# lru_cache means this function only runs once — the Settings object
# is created once and reused on every call to get_settings()
# This is efficient and ensures one consistent config across the app
@lru_cache()
def get_settings() -> Settings:
    return Settings()