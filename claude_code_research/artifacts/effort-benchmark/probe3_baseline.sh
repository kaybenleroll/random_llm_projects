#!/usr/bin/env bash
# Baseline (NON-isolated) run to show what the isolation flags remove: hooks/skills/agents/memory.
source "$(dirname "$0")/env_clean.sh"; cd "$(dirname "$0")/cwd"
"${CLEAN_ENV[@]}" claude -p --tools "" --model claude-sonnet-5 --effort medium --output-format stream-json --verbose --include-hook-events "Reply OK" < /dev/null > ../logs/probe_baseline_nonisolated.jsonl 2>&1
