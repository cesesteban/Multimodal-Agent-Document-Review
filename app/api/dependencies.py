from fastapi import Header, HTTPException, status, Security
from fastapi.security.api_key import APIKeyHeader
from app.config import settings
from typing import Optional

# Setup API Key header extractor from request
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def validate_api_key(api_key: Optional[str] = Security(API_KEY_HEADER)) -> Optional[str]:
    """
    FastAPI security dependency to validate the API Key.
    Checks the incoming header X-API-Key against the configured key.
    If settings.API_KEY is not configured, it acts as a no-op.
    """
    if not settings.API_KEY:
        return None
        
    if not api_key or api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing or invalid API Key in X-API-Key header."
        )
    return api_key

async def get_target_language(accept_language: Optional[str] = Header(None)) -> str:
    """
    FastAPI dependency to parse the Accept-Language header to select the comparison summary output language.
    Defaults to Spanish. English is used if 'en' is detected inside the header.
    """
    if not accept_language:
        return "Spanish"
        
    normalized = accept_language.lower()
    
    # Check if English is requested (e.g. Accept-Language: en-US,en;q=0.5)
    if "en" in normalized:
        return "English"
        
    return "Spanish"
