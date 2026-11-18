from fastapi import FastAPI
from app.api.routes import health, chat,planner,repository
from app.core.config import settings


app = FastAPI(
    title=settings.APP_NAME,
    description="Autonomous AI Coding Assistant",
    version="0.1.0"
)

app.include_router(health.router)
app.include_router(chat.router, prefix="/api/v1")
app.include_router(planner.router,prefix="/api/v1")
app.include_router(repository.router, prefix="/api/v1")