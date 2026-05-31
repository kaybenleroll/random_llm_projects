#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <backup-tarball>" >&2
  exit 1
fi

ARCHIVE="$1"
if [[ ! -f "$ARCHIVE" ]]; then
  echo "Error: backup archive not found: $ARCHIVE" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "$ROOT_DIR/state/openclaw" "$ROOT_DIR/state/workspace" "$ROOT_DIR/state/ollama" "$ROOT_DIR/state/vllm-cache"

# Stop services before restore.
if command -v podman >/dev/null 2>&1; then
  (cd "$ROOT_DIR" && podman compose -f podman-compose.yml down || true)
fi

# Restore files in place.
(
  cd "$ROOT_DIR"
  tar -xzf "$ARCHIVE"
)

# Bring services back.
if command -v podman >/dev/null 2>&1; then
  (cd "$ROOT_DIR" && podman compose -f podman-compose.yml up -d || true)
fi

echo "Restore complete from: $ARCHIVE"
