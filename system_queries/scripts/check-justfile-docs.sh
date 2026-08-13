#!/usr/bin/env bash
# Diff Justfile recipe names against the target names documented in CLAUDE.md's
# health-target tables. Flags undocumented recipes and stale table rows so the
# two don't silently drift apart. Run via `just docs-check`.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
JUSTFILE="$REPO_ROOT/Justfile"
CLAUDE_MD="$REPO_ROOT/CLAUDE.md"

justfile_targets=$(grep -oE '^[a-zA-Z][a-zA-Z0-9_-]*(\s[a-zA-Z0-9_-]+)*:' "$JUSTFILE" \
    | sed -E 's/:$//; s/\s.*//' \
    | grep -v '^default$' \
    | sort -u)

claude_md_targets=$(grep -oE '^\| `[a-zA-Z0-9_-]+`' "$CLAUDE_MD" \
    | sed -E 's/^\| `//; s/`$//' \
    | sort -u)

missing_from_claude_md=$(comm -23 <(echo "$justfile_targets") <(echo "$claude_md_targets"))
stale_in_claude_md=$(comm -13 <(echo "$justfile_targets") <(echo "$claude_md_targets"))

status=0

if [ -n "$missing_from_claude_md" ]; then
    echo "Justfile targets undocumented in CLAUDE.md:"
    echo "$missing_from_claude_md" | sed 's/^/  /'
    status=1
fi

if [ -n "$stale_in_claude_md" ]; then
    echo "CLAUDE.md rows referencing targets no longer in the Justfile:"
    echo "$stale_in_claude_md" | sed 's/^/  /'
    status=1
fi

if [ "$status" -eq 0 ]; then
    echo "CLAUDE.md target tables match Justfile recipes ($(echo "$justfile_targets" | wc -l) targets)."
fi

exit "$status"
