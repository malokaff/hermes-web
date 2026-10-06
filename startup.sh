#!/usr/bin/env bash
# Hermes Web — Podman startup script
# Usage: ./startup.sh [build|save|load|run|stop|restart|status]
#
# Fast restart workflow:
#   1. (once, online)  ./startup.sh build && ./startup.sh save
#   2. (every time)    ./startup.sh run
#
# Environment variables:
#   HERMES_API_URL   — Hermes gateway API URL (default: http://host.containers.internal:8642)
#   HOST_PORT        — Host port to expose (default: 8080)
#   IMAGE_NAME       — Docker image name (default: hermes-web)
#   CONTAINER_NAME   — Container name (default: hermes-web)

set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-hermes-web}"
CONTAINER_NAME="${CONTAINER_NAME:-hermes-web}"
HOST_PORT="${HOST_PORT:-8080}"
CONTAINER_PORT=8000
API_URL="${HERMES_API_URL:-http://host.containers.internal:8642}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { echo "[hermes-web] $*"; }

do_build() {
    log "Building image '${IMAGE_NAME}' (requires python:3.14-slim)..."
    podman build -t "${IMAGE_NAME}" "${SCRIPT_DIR}"
    log "Build complete."
}

do_save() {
    log "Saving image '${IMAGE_NAME}' to ${SCRIPT_DIR}/hermes-web.tar..."
    podman save -o "${SCRIPT_DIR}/hermes-web.tar" "${IMAGE_NAME}"
    local size
    size=$(du -sh "${SCRIPT_DIR}/hermes-web.tar" | cut -f1)
    log "Saved (${size}). Copy hermes-web.tar to offline machines."
}

do_load() {
    local tar="${SCRIPT_DIR}/hermes-web.tar"
    if [ ! -f "$tar" ]; then
        log "ERROR: ${tar} not found. Run './startup.sh build && ./startup.sh save' first."
        return 1
    fi
    log "Loading image from ${tar}..."
    podman load -i "$tar"
    log "Image loaded."
}

do_run() {
    # Check if image exists
    if ! podman image inspect "${IMAGE_NAME}" > /dev/null 2>&1; then
        if [ -f "${SCRIPT_DIR}/hermes-web.tar" ]; then
            log "Image not found locally. Loading from hermes-web.tar..."
            do_load || return 1
        else
            log "ERROR: Image '${IMAGE_NAME}' not found and hermes-web.tar not available."
            log "Run './startup.sh build && ./startup.sh save' (requires network and python:3.14-slim)."
            return 1
        fi
    fi

    # Stop existing container
    podman rm -f "${CONTAINER_NAME}" 2>/dev/null || true

    # Run
    log "Starting container on port ${HOST_PORT}..."
    podman run -d \
        --name "${CONTAINER_NAME}" \
        --replace \
        --pull=never \
        -p "${HOST_PORT}:${CONTAINER_PORT}" \
        -e "HERMES_API_URL=${API_URL}" \
        -e "PORT=${CONTAINER_PORT}" \
        "${IMAGE_NAME}"

    # Wait for startup
    sleep 2
    if curl -sf "http://localhost:${HOST_PORT}/v1/health" > /dev/null 2>&1; then
        log "Running! http://localhost:${HOST_PORT}"
    else
        log "Container started (health check not yet responding)."
        log "http://localhost:${HOST_PORT}"
    fi
}

do_stop() {
    log "Stopping ${CONTAINER_NAME}..."
    podman stop "${CONTAINER_NAME}" 2>/dev/null || true
    podman rm "${CONTAINER_NAME}" 2>/dev/null || true
    log "Stopped."
}

do_restart() {
    do_stop
    sleep 1
    do_run
}

do_status() {
    podman ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
    log "Image: $(podman image inspect "${IMAGE_NAME}" --format '{{.Id}}' 2>/dev/null || echo 'NOT FOUND')"
    if [ -f "${SCRIPT_DIR}/hermes-web.tar" ]; then
        log "Tarball: $(du -sh "${SCRIPT_DIR}/hermes-web.tar" | cut -f1)"
    fi
}

case "${1:-run}" in
    build)   do_build   ;;
    save)    do_save    ;;
    load)    do_load    ;;
    run)     do_run     ;;
    stop)    do_stop    ;;
    restart) do_restart ;;
    status)  do_status  ;;
    *)
        echo "Usage: $0 {build|save|load|run|stop|restart|status}"
        echo ""
        echo "Quick start (online, once):"
        echo "  ./startup.sh build && ./startup.sh save"
        echo ""
        echo "Quick start (offline, every time):"
        echo "  ./startup.sh run"
        ;;
esac