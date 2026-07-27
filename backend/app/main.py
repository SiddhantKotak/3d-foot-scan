"""FastAPI entrypoint.

Builds the LangGraph RunManager once at startup (compiles the graph + opens the
SQLite checkpointer) and mounts the scan / review / webhook routers.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .api import routes_review, routes_scan, routes_webhook
from .graph.runner import RunManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.runs = RunManager()          # compiles graph + SQLite checkpointer
    yield


app = FastAPI(title="Foot Scan -> Insole PoC", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(routes_scan.router)
app.include_router(routes_review.router)
app.include_router(routes_webhook.router)


@app.get("/api/health")
async def health() -> dict:
    s = get_settings()
    return {"ok": True, "kiri_live": s.kiri_live, "claude_live": s.claude_live}
