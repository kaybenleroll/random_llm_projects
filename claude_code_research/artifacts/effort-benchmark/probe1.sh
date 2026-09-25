#!/usr/bin/env bash
source "$(dirname "$0")/env_clean.sh"
cd "$(dirname "$0")/cwd"
echo "--- bare"; time "${CLEAN_ENV[@]}" claude -p --bare --model claude-sonnet-5 --effort medium --output-format json "Say OK" 2>&1 | head -c 600
echo; echo "--- isolated (no bare)"; time "${CLEAN_ENV[@]}" claude -p --setting-sources "" --tools "" --strict-mcp-config --disable-slash-commands --no-session-persistence --model claude-sonnet-5 --effort medium --output-format json "Say OK" 2>&1 | head -c 3000
