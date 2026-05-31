#!/usr/bin/env bash
set -euo pipefail

MODE="${MODE:-dev}"
source ./render.env

if [[ "$MODE" == "full" ]]; then
  export RENDER_N_SIMS="$FULL_N_SIMS"
else
  export RENDER_N_SIMS="$DEV_N_SIMS"
fi

mkdir -p "$OUTPUT_DIR"

./scripts/render_primer.sh
./scripts/render_quickstart.sh
./scripts/render_index.sh

echo "Rendered all documents in mode=$MODE with n_sims=$RENDER_N_SIMS"
