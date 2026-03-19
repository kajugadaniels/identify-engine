from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from app.core.config import get_settings

# Tells FastAPI to look for this header on incoming requests
# The header name our NestJS gateway will send
API_KEY_HEADER = APIKeyHeader(name="X-Internal-API-Key", auto_error=False)


async def verify_internal_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    Dependency injected into every route.
    Checks that the request includes the correct internal API key header.

    Usage in a route:
        @router.post("/verify")
        async def verify(deps = Depends(verify_internal_api_key)):
            ...
    """
    settings = get_settings()

    # If header is missing or wrong — reject immediately with 403
    # We use 403 Forbidden (not 401) because this is not about user auth,
    # it's about service-to-service authorization
    if not api_key or api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing internal API key",
        )

    return api_key