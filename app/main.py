from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:  # Verify the database connection on startup.
        await conn.run_sync(lambda _: None)
    yield


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
