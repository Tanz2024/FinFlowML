import time
from collections import defaultdict, deque

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.api.routes import router
from backend.app.core.config import settings
from backend.app.database.session import get_db
from backend.app.demo import router as demo_router


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; img-src 'self' blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Small single-process guard; use an edge limiter for multi-replica staging."""

    def __init__(self, app, limit: int = 60):
        super().__init__(app)
        self.limit = limit
        self.requests = defaultdict(deque)

    async def dispatch(self, request, call_next):
        if request.url.path in {"/auth/login", "/predict"} or request.url.path.endswith(("/corrections", "/approve", "/reject")):
            key = f"{request.client.host if request.client else 'unknown'}:{request.url.path}"
            now = time.monotonic()
            bucket = self.requests[key]
            while bucket and bucket[0] <= now - 60:
                bucket.popleft()
            if len(bucket) >= self.limit:
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "rate limit exceeded"}, status_code=429, headers={"Retry-After": "60"})
            bucket.append(now)
        return await call_next(request)


app = FastAPI(title="FinFlowML API", version="0.1.0")
origins = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET", "POST", "PATCH"], allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Correlation-ID"])
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, limit=settings.rate_limit_per_minute)
app.include_router(router)
app.include_router(demo_router)


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", include_in_schema=False)
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready"}
