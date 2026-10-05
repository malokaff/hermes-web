# Hermes Web — Podman container
# Multi-stage: Python backend serves both API proxy + static frontend

FROM python:3.12-slim AS builder

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

# Add root CA certs for HTTPS
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /install /usr/local

# Copy backend + frontend
COPY backend/main.py .
COPY frontend/ ./frontend/

# Env vars (can be overridden via --env or docker-compose)
ENV HERMES_API_URL=http://host.containers.internal:8642
ENV PORT=8000

# Expose
EXPOSE 8000

# Run
CMD ["python", "main.py"]