"""RunwayRadar API + static frontend server."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import pipeline

app = FastAPI(title="RunwayRadar", version="0.1.0")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "runwayradar"}


@app.get("/api/run")
def run() -> dict:
    return pipeline.run_pipeline()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
