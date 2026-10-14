from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.api.routes import router
from backend.app.demo import router as demo_router


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; img-src 'self' blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
        return response


app = FastAPI(title="FinFlowML API", version="0.1.0")
app.add_middleware(SecurityHeadersMiddleware)
app.include_router(router)
app.include_router(demo_router)
