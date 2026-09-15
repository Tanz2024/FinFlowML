from fastapi import FastAPI

from backend.app.api.routes import router

app = FastAPI(title="FinFlowML API", version="0.1.0")
app.include_router(router)
