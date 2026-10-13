from fastapi import FastAPI

from backend.app.api.routes import router
from backend.app.demo import router as demo_router

app = FastAPI(title="FinFlowML API", version="0.1.0")
app.include_router(router)
app.include_router(demo_router)
