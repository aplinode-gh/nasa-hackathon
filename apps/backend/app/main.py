"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os

from app.api.router import api_router
from app.db.session import close_pool, init_pool


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Manage application startup/shutdown resources."""
    try:
        await init_pool()
    except Exception:
        # Allow the app to boot even if DB is unavailable at startup.
        pass
    yield
    await close_pool()


app = FastAPI(title="NASA Hackathon Backend", version="0.1.0", lifespan=lifespan)

cors_origins_env = os.getenv("CORS_ORIGINS", "").strip()
cors_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    return {"status": "ok", "service": "backend"}
