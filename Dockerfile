# Hermes Web — Podman container
# Base: python:3.14-slim (matches compiled packages in site-packages/)
#
# Online build:  podman build -t hermes-web .
# Offline build: podman build --no-cache -t hermes-web .  (use with pre-saved site-packages/)
#
# For offline builds, pre-pull the base image when online:
#   podman pull python:3.14-slim

FROM python:3.14-slim

WORKDIR /app

# Copy Python packages first (biggest layer, changes least often)
COPY site-packages/ /usr/local/lib/python3.14/site-packages/

# Copy application code
COPY backend/main.py .
COPY frontend/ ./frontend/

# Environment
ENV PORT=8000
ENV HERMES_API_URL=http://host.containers.internal:8642

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/health')" || exit 1

CMD ["python", "main.py"]