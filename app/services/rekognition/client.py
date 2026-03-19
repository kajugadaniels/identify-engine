import boto3 # type: ignore
from app.core.config import get_settings


def get_rekognition_client():
    """
    Creates and returns a boto3 Rekognition client.

    Defined as a function so every call gets a fresh reference
    to the latest settings — important when running tests with
    mocked or overridden configs.

    Credentials are always read from .env via get_settings()
    and never hardcoded anywhere in the codebase.
    """
    settings = get_settings()

    return boto3.client(
        "rekognition",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )