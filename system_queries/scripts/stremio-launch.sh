#!/usr/bin/env bash
# Start Stremio streaming server (if not already running) and open Chrome in app mode

CONTAINER_NAME="stremio-server"
IMAGE="docker.io/sleeyax/stremio-streaming-server:latest"
DATA_DIR="$HOME/.stremio-server"

mkdir -p "$DATA_DIR"

# Start container if not already running
if ! podman ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    echo "Starting Stremio server..."
    podman run -d \
        --name "$CONTAINER_NAME" \
        --restart unless-stopped \
        -p 11470:11470 \
        -v "$DATA_DIR:/root/.stremio-server:Z" \
        "$IMAGE"

    # Wait for server to be ready
    echo "Waiting for server..."
    for i in $(seq 1 15); do
        if curl -sf http://127.0.0.1:11470/health >/dev/null 2>&1 || \
           curl -sf http://127.0.0.1:11470/ >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
fi

# Open Stremio web app in Chrome app mode
exec google-chrome --app=https://app.strem.io \
    --class=Stremio \
    --window-size=1280,800 \
    2>/dev/null
