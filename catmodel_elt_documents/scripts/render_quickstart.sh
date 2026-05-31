#!/usr/bin/env bash
set -euo pipefail

source ./render.env
mkdir -p "$OUTPUT_DIR"
quarto render primer_quickstart.qmd --to html
rm -f "$OUTPUT_DIR/primer_quickstart.html"
mv primer_quickstart.html "$OUTPUT_DIR/primer_quickstart.html"
rm -rf primer_quickstart_files
rm -rf "$OUTPUT_DIR/primer_quickstart_files"
