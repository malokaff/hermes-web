# Hermes Web

Web interface for the Hermes Gateway API.

## Quick Start

### Prerequisites
- Podman installed
- Python 3.14 (on host for building)
- Hermes Gateway running on port 8642

### Fast restart (recommended)

```bash
# One-time setup (requires network + python:3.14-slim image)
./startup.sh build && ./startup.sh save

# Every restart (works offline)
./startup.sh run
```

The `save` command creates `hermes-web.tar` — copy it to offline machines and use `./startup.sh run` there.

### Full offline (no network, no image)

Run the backend directly on the host using the existing Python 3.14 virtual environment:

```bash
export HERMES_API_URL=http://127.0.0.1:8642
export PORT=8082

/home/bmaze/.hermes/installs/c9c798cecb79743e/environments/d7ec71e8be4e41a9be56d32e7e863a52/venv/bin/python3.14 \
    -m uvicorn main:app --host 0.0.0.0 --port 8082
```

Run from: `/tmp/hermes-web/backend/`

## Manual Podman Commands

### Build
```bash
# Requires python:3.14-slim image (pull if needed)
podman pull python:3.14-slim
podman build -t hermes-web .
```

### Run
```bash
podman run -d \
    --name hermes-web \
    --replace \
    -p 8080:8000 \
    -e HERMES_API_URL=http://host.containers.internal:8642 \
    hermes-web
```

### Save / Load (offline transfer)
```bash
# Save
podman save hermes-web -o hermes-web.tar

# Load on another machine
podman load -i hermes-web.tar
```

## Access

| URL | Description |
|-----|-------------|
| `http://localhost:8080` | Web interface |
| `http://localhost:8080/docs` | Swagger UI |
| `http://localhost:8080/v1/health` | Health check |

## Troubleshooting

### Port already in use
Change the host port:
```bash
podman run -d -p 8081:8000 hermes-web
# or with startup script
HOST_PORT=8081 ./startup.sh run
```

### Container crashes immediately
The `site-packages/` directory must be compiled for Python 3.14. Ensure:
- Base image is `python:3.14-slim`
- `site-packages/` contains Python 3.14 compiled packages

### API not responding
Check `HERMES_API_URL`:
- **Inside container**: `http://host.containers.internal:8642`
- **On host (direct)**: `http://127.0.0.1:8642`

### DNS unreachable (offline build)
The build copies `site-packages/` directly — no network needed. Make sure:
- `site-packages/` exists with all dependencies
- Base image matches the Python version of `site-packages/` (3.14)

## File Structure

```
hermes-web/
├── Dockerfile              # Container build definition (python:3.14-slim)
├── .dockerignore           # Excluded files from build context
├── startup.sh              # Build/run script (fast restart)
├── README.md               # This file
├── backend/
│   ├── main.py             # FastAPI application
│   ├── requirements.txt    # Python dependencies
│   └── frontend/           # Web interface (index.html)
├── frontend/               # Web interface source
│   └── index.html
└── site-packages/          # Pre-installed Python packages (for offline builds)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HERMES_API_URL` | `http://host.containers.internal:8642` | Hermes gateway API endpoint |
| `PORT` | `8000` | Container internal port |
| `HOST_PORT` | `8080` | Host port (startup.sh) |
| `IMAGE_NAME` | `hermes-web` | Podman image name (startup.sh) |
| `CONTAINER_NAME` | `hermes-web` | Podman container name (startup.sh) |