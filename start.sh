#!/bin/bash
# Start the Hermes Web Interface in a Podman container

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTAINER_NAME="hermes-web"
IMAGE_NAME="hermes-web:latest"
HOST_PORT=9119
CONTAINER_PORT=9119

echo "🦾 Starting Hermes Web Interface..."

# Check if Podman is available
if ! command -v podman &> /dev/null; then
    echo "❌ Podman is not installed. Please install Podman first."
    exit 1
fi

# Build the image
echo "📦 Building container image..."
podman build -f "$PROJECT_DIR/Podmanfile" -t "$IMAGE_NAME" "$PROJECT_DIR"

# Stop and remove existing container if running
if podman ps -a --filter "name=$CONTAINER_NAME" --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "🛑 Stopping existing container..."
    podman stop "$CONTAINER_NAME" 2>/dev/null || true
    podman rm "$CONTAINER_NAME" 2>/dev/null || true
fi

# Check if port is already in use
if ss -tlnp | grep -q ":${HOST_PORT} "; then
    echo "⚠️  Port $HOST_PORT is already in use."
    read -p "Do you want to proceed anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Start the container
echo "🚀 Starting container..."
podman run -d \
    --name "$CONTAINER_NAME" \
    --publish ${HOST_PORT}:${CONTAINER_PORT} \
    -v /home/bmaze/.hermes:/home/bmaze/.hermes:ro \
    -v /home/bmaze/.hermes/hermes-agent/.hermes:/usr/local/hermes:ro \
    -e HOME=/home/bmaze \
    -e HERMES_HOME=/home/bmaze/.hermes \
    -e PATH="/usr/local/hermes/bin:/usr/local/bin:/usr/bin:/bin" \
    --restart unless-stopped \
    --security-opt label=disable \
    "$IMAGE_NAME"

# Wait for container to start
echo "⏳ Waiting for container to start..."
sleep 2

# Check container status
if podman ps --filter "name=$CONTAINER_NAME" --format '{{.Names}} {{.Status}}' | grep -q "^${CONTAINER_NAME}"; then
    echo ""
    echo "✅ Hermes Web Interface is running!"
    echo "🌐 Access it at: http://localhost:${HOST_PORT}"
    echo ""
    echo "📋 Container logs: podman logs -f $CONTAINER_NAME"
    echo "🛑 Stop: podman stop $CONTAINER_NAME"
    echo "🗑️  Remove: podman rm $CONTAINER_NAME"
else
    echo "❌ Failed to start container. Check logs:"
    podman logs "$CONTAINER_NAME"
    exit 1
fi