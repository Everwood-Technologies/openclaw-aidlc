"""Cache State Engine — FastAPI app (read-only Redis browser)."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from redis import RedisError

from . import redis_client as rc

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="Cache State Engine",
    description="Local visibility console for AIDLC Redis state (read-only).",
    version="0.1.0",
)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="SPA not found")
    return FileResponse(index_path)


@app.get("/api/health")
def api_health() -> dict:
    return rc.health()


@app.get("/api/keys")
def api_keys(
    pattern: str = Query(default="aidlc:*", min_length=1, max_length=256),
    count: int | None = Query(default=None, ge=1, le=5000),
) -> dict:
    try:
        keys = rc.scan_keys(pattern=pattern, limit=count)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail=f"Redis error: {exc}") from exc
    return {"pattern": pattern, "count": len(keys), "keys": keys}


@app.get("/api/keys/{key:path}")
def api_key_detail(key: str) -> dict:
    try:
        detail = rc.get_value(key)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail=f"Redis error: {exc}") from exc
    if not detail.get("exists"):
        raise HTTPException(status_code=404, detail=f"Key not found: {key}")
    return detail


@app.get("/api/sessions")
def api_sessions() -> dict:
    try:
        sessions = rc.list_sessions()
    except RedisError as exc:
        raise HTTPException(status_code=503, detail=f"Redis error: {exc}") from exc
    return {"count": len(sessions), "sessions": sessions}


def run() -> None:
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8787"))
    uvicorn.run("app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
