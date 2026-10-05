"""FastAPI application for Hermes CLI web interface."""

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(
    title="Hermes Agent Web Interface",
    description="Web UI for interacting with Hermes CLI",
    version="0.1.0",
)

# Mount static files and templates
BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Track active streaming sessions
active_sessions: dict[str, dict] = {}

# Default command prefix
HERMES_CMD = os.environ.get("HERMES_CMD", "hermes")
HERMES_ARGS = os.environ.get("HERMES_ARGS", "").split()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main web interface."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    try:
        result = subprocess.run(
            [HERMES_CMD, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        hermes_version = result.stdout.strip() if result.returncode == 0 else "unavailable"
    except Exception as e:
        hermes_version = f"error: {e}"

    return {
        "status": "healthy",
        "hermes": hermes_version,
        "hermes_cmd": HERMES_CMD,
        "active_sessions": len([s for s in active_sessions.values() if s.get("running")]),
    }


@app.post("/api/command")
async def execute_command(request: Request):
    """Execute a single Hermes CLI command (non-interactive, one-shot)."""
    body = await request.json()
    prompt = body.get("prompt", "").strip()

    if not prompt:
        return JSONResponse(status_code=400, content={"error": "Prompt is required"})

    # Build command: hermes -z "prompt" with optional extra args
    cmd = [HERMES_CMD] + HERMES_ARGS + ["-z", prompt]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate(timeout=120)

        return {
            "exit_code": process.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "prompt": prompt,
        }
    except asyncio.TimeoutExpired:
        process.kill()
        return JSONResponse(
            status_code=504,
            content={"error": "Command timed out after 120 seconds"},
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/stream")
async def stream_command(request: Request):
    """Execute a command with real-time output streaming via Server-Sent Events."""
    body = await request.json()
    prompt = body.get("prompt", "").strip()

    if not prompt:
        return JSONResponse(status_code=400, content={"error": "Prompt is required"})

    session_id = f"stream_{int(time.time())}_{os.urandom(4).hex()}"

    cmd = [HERMES_CMD] + HERMES_ARGS + ["-z", prompt]

    async def event_stream():
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            active_sessions[session_id] = {"running": True, "process": process}

            # Send stdout in real-time
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if text:
                    yield f"data: {json.dumps({'type': 'chunk', 'data': text})}\n\n"

            # Wait for process to finish
            await process.wait()

            # Send final status
            status = "success" if process.returncode == 0 else "error"
            yield f"data: {json.dumps({'type': 'status', 'status': status, 'exit_code': process.returncode})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            if session_id in active_sessions:
                active_sessions[session_id]["running"] = False

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/sessions")
async def list_sessions():
    """List active streaming sessions."""
    sessions = []
    for sid, info in active_sessions.items():
        sessions.append({
            "id": sid,
            "running": info.get("running", False),
        })
    return {"sessions": sessions}


@app.get("/api/sessions/kill/{session_id}")
async def kill_session(session_id: str):
    """Kill an active streaming session."""
    if session_id in active_sessions:
        process = active_sessions[session_id].get("process")
        if process:
            process.terminate()
        active_sessions[session_id]["running"] = False
        return {"status": "killed"}
    return JSONResponse(status_code=404, content={"error": "Session not found"})


@app.get("/api/info")
async def get_hermes_info():
    """Get detailed Hermes information."""
    info = {}

    # Get version
    try:
        result = subprocess.run(
            [HERMES_CMD, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        info["version"] = result.stdout.strip()
    except Exception:
        pass

    # Get available commands
    try:
        result = subprocess.run(
            [HERMES_CMD, "--help"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            # Extract commands from help text
            lines = result.stdout.split("\n")
            commands = []
            in_commands = False
            for line in lines:
                if "positional arguments:" in line:
                    in_commands = True
                    continue
                if in_commands and line.strip().startswith("<command>"):
                    continue
                if in_commands and line.strip() == "...":
                    break
                if in_commands and line.strip():
                    cmd = line.strip().split()[0] if line.strip() else None
                    if cmd and not cmd.startswith("-"):
                        commands.append(cmd)
            info["commands"] = commands
    except Exception:
        pass

    return info


if __name__ == "__main__":
    uvicorn.run(
        "hermes_web.app:app",
        host="0.0.0.0",
        port=9119,
        log_level="info",
    )