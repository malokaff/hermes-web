"""
Hermes Web — Backend proxy.
Connects the web UI to the Hermes API server running on the host.

Env vars:
  HERMES_API_URL   — base URL of the Hermes API server (default: http://host.containers.internal:8642)
  HERMES_API_KEY   — API_SERVER_KEY from ~/.hermes/.env
  PORT             — listen port (default: 8000)
  CORS_ORIGINS     — comma-separated allowed origins (default: http://localhost:8000,http://localhost:3000)
"""

import os
import json
import time
import uuid
import httpx
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ── Config ──────────────────────────────────────────────────────────────────
HERMES_API_URL = os.getenv("HERMES_API_URL", "http://host.containers.internal:8642")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")
PORT = int(os.getenv("PORT", "8000"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://localhost:3000").split(",") if o.strip()]

HERMES_BASE = f"{HERMES_API_URL}/v1"

# ── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(title="Hermes Web Proxy", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Helpers ─────────────────────────────────────────────────────────────────
def _headers(authorization: str | None = None) -> dict:
    h = {"Content-Type": "application/json"}
    if HERMES_API_KEY:
        h["Authorization"] = f"Bearer {HERMES_API_KEY}"
    if authorization and authorization.startswith("Bearer "):
        h["Authorization"] = authorization
    return h

async def _stream_hermes(url: str, body: dict):
    """Yield raw SSE lines from the Hermes API."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=body, headers=_headers()) as r:
            async for line in r.aiter_lines():
                if line.startswith(":"):
                    continue  # skip keepalive comments
                if line.strip():
                    yield f"{line}\n"

# ── Proxied endpoints ──────────────────────────────────────────────────────
@app.get("/v1/health")
async def health():
    return {"status": "ok", "hermes_url": HERMES_BASE}

@app.get("/v1/models")
async def models(authorization: str | None = Header(None)):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{HERMES_BASE}/models", headers=_headers(authorization))
        return JSONResponse(content=r.json())

@app.post("/v1/chat/completions")
async def chat_completions(request: Request, authorization: str | None = Header(None)):
    body = await request.json()
    stream = body.get("stream", False)
    url = f"{HERMES_BASE}/chat/completions"

    if stream:
        return StreamingResponse(
            _stream_hermes(url, body),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    else:
        async with httpx.AsyncClient(timeout=300.0) as client:
            r = await client.post(url, json=body, headers=_headers(authorization))
            return JSONResponse(content=r.json())

@app.post("/v1/responses")
async def responses(request: Request, authorization: str | None = Header(None)):
    body = await request.json()
    stream = body.get("stream", False)
    url = f"{HERMES_BASE}/responses"

    if stream:
        return StreamingResponse(
            _stream_hermes(url, body),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    else:
        async with httpx.AsyncClient(timeout=300.0) as client:
            r = await client.post(url, json=body, headers=_headers(authorization))
            return JSONResponse(content=r.json())

# ── Management endpoints (Hermes REST, not OpenAI-compat) ───────────────────
@app.get("/api/health")
async def hermes_health():
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{HERMES_API_URL}/health", timeout=5)
            return r.json()
    except Exception as e:
        return JSONResponse(content={"status": "error", "detail": str(e)}, status_code=502)

@app.get("/api/sessions")
async def list_sessions(authorization: str | None = Header(None),
                        limit: int = 50, offset: int = 0):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{HERMES_API_URL}/api/sessions",
                params={"limit": limit, "offset": offset},
                headers=_headers(authorization),
                timeout=10,
            )
            r.raise_for_status()
            return r.json()
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=502)

@app.get("/api/sessions/{session_id}/messages")
async def session_messages(session_id: str, authorization: str | None = Header(None),
                           include_compacted: bool = False):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{HERMES_API_URL}/api/sessions/{session_id}/messages",
                params={"include_compacted": include_compacted},
                headers=_headers(authorization),
                timeout=10,
            )
            r.raise_for_status()
            return r.json()
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=502)

# ── Serve frontend ──────────────────────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

# ── CLI runner ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)