#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./render.sh
#   ./render.sh path/to/file.md

MD_INPUT="${1:-openclaw_primer.md}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
REPO_ROOT="$(cd "$PROJECT_DIR/.." && pwd)"
TEMPLATE="$REPO_ROOT/doc_template.html"

if [[ ! -f "$MD_INPUT" ]]; then
  echo "Error: Markdown input not found: $MD_INPUT" >&2
  exit 1
fi

if [[ ! -f "$TEMPLATE" ]]; then
  echo "Error: Template not found: $TEMPLATE" >&2
  exit 1
fi

BASE_NAME="${MD_INPUT%.md}"
HTML_OUT="${BASE_NAME}.html"
PDF_OUT="${BASE_NAME}.pdf"

TITLE="OpenClaw Primer: A Comprehensive, Podman-First Guide"
AUTHOR="28 May 2026"

echo "Rendering HTML -> $HTML_OUT"
podman run --rm -v "$REPO_ROOT:/repo" -w /repo/openclaw_primer docker.io/pandoc/core:latest \
  "$MD_INPUT" -o "$HTML_OUT" \
  --standalone --embed-resources --toc --toc-depth=3 \
  --syntax-highlighting=tango --template="/repo/doc_template.html" \
  --metadata title="$TITLE" \
  --metadata author="$AUTHOR"

echo "Rendering PDF -> $PDF_OUT"
podman run --rm -v "$REPO_ROOT:/repo" -w /repo/openclaw_primer docker.io/pandoc/latex:latest \
  "$MD_INPUT" -o "$PDF_OUT" \
  --pdf-engine=xelatex --toc --toc-depth=3 \
  -V geometry:margin=1.2in -V fontsize=11pt -V linestretch=1.25 \
  -V colorlinks=true -V linkcolor=NavyBlue -V urlcolor=NavyBlue \
  -V toc-title="Table of Contents" \
  --metadata title="$TITLE" \
  --metadata author="$AUTHOR"

echo "Done. Outputs:"
ls -lh "$HTML_OUT" "$PDF_OUT"
