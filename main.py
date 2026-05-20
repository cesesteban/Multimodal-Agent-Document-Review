import uvicorn
import time
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict
from app.config import settings
from app.api.endpoints import router as api_router

# Initialize FastAPI application with custom title and version
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# In-memory sliding-window rate limit storage
rate_limit_records = defaultdict(list)

@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    """
    Rate limiting middleware checking client IP addresses.
    Restricts requests on the heavy comparison pipeline while letting health checks run unhindered.
    """
    if settings.API_V1_STR + "/compare" in request.url.path:
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Clean up records older than the sliding window settings
        window_start = current_time - settings.RATE_LIMIT_WINDOW_SECONDS
        rate_limit_records[client_ip] = [
            t for t in rate_limit_records[client_ip] if t > window_start
        ]
        
        # Raise HTTP 429 if the request threshold is crossed
        if len(rate_limit_records[client_ip]) >= settings.RATE_LIMIT_REQUESTS:
            return Response(
                content='{"detail": "Too Many Requests: Rate limit exceeded. Please try again later."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json"
            )
            
        rate_limit_records[client_ip].append(current_time)
        
    return await call_next(request)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Injects standard HTTP security headers to prevent common UI vulnerabilities (Clickjacking, XSS, Sniffing).
    """
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    path = request.url.path.rstrip('/')
    if path in ["/docs", "/redoc"] or request.url.path == "/openapi.json":
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://fastapi.tiangolo.com; "
            "connect-src 'self';"
        )
    else:
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none';"
    return response


# Standardize and configure CORS origins from settings
origins = [o.strip() for o in settings.ALLOWED_CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True if "*" not in origins else False, # Safe fallback to avoid FastAPI startup crash
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach API endpoints router under API version prefix
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["Maintenance"])
async def health_check():
    """
    Basic endpoint returning the service status.
    """
    return {"status": "healthy", "version": settings.VERSION}

if __name__ == "__main__":
    # Start ASGI application server on port 8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
