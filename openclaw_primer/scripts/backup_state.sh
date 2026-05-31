#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$ROOT_DIR/backups"
STATE_DIR="$ROOT_DIR/state"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="$BACKUP_DIR/openclaw_state_${STAMP}.tar.gz"

mkdir -p "$BACKUP_DIR"
mkdir -p "$STATE_DIR/openclaw" "$STATE_DIR/workspace" "$STATE_DIR/ollama" "$STATE_DIR/vllm-cache"

# Stop services briefly to avoid inconsistent state while archiving.
if command -v podman >/dev/null 2>&1; then
  (cd "$ROOT_DIR" && podman compose -f podman-compose.yml stop || true)
fi

(
  cd "$ROOT_DIR"
  tar -czf "$OUT_FILE" \
    podman-compose.yml \
    state/openclaw \
    state/workspace \
    state/ollama \
    state/vllm-cache
)

# Restart the stack after backup.
if command -v podman >/dev/null 2>&1; then
  (cd "$ROOT_DIR" && podman compose -f podman-compose.yml up -d || true)
fi

echo "Backup complete: $OUT_FILE"
ls -lh "$OUT_FILE"
