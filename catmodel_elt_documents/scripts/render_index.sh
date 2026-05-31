#!/usr/bin/env bash
set -euo pipefail

source ./render.env
mkdir -p "$OUTPUT_DIR"
quarto render executable_index.qmd --to html
rm -f "$OUTPUT_DIR/executable_index.html"
mv executable_index.html "$OUTPUT_DIR/executable_index.html"
rm -rf executable_index_files
rm -rf "$OUTPUT_DIR/executable_index_files"
