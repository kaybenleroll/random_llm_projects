#!/usr/bin/env python3
"""
Blocking PreToolUse hook — prevents a subagent from backgrounding one of the
transcript-sanitizer project's known-slow, full-corpus commands.

Why: a subagent has no path for its own background task's completion event
to reach its own execution loop — only the agent that SPAWNED the subagent
receives that notification (Bash run_in_background / Monitor tool). A
subagent that backgrounds `just build-mirror` (or an equivalent slow
command) stalls forever waiting for a notification that will never arrive
at its own turn. Confirmed recurring in this project's session history
(see notes/ for the investigation) — always around bin/build-mirror.sh.

Handles two tool paths:
  - Bash with tool_input.run_in_background == true
  - Monitor (tool_input.command is the underlying shell command)

Only blocks when BOTH the backgrounding mechanism AND a known-slow command
are present. A foreground Bash call (run_in_background absent/false) to the
same command is never touched, regardless of timeout value.

Exits 2 with a stderr message on block (hard block, per project convention
for this hook). Exits 0 (silent) on every non-matching case — never errors
noisily, matches sibling hooks in this repo.
"""
import json
import re
import sys

# Substrings that identify a known-slow, full-real-corpus command for this
# project. Matched against the command string for Bash, or tool_input.command
# for Monitor. Keep this list in sync with artifacts/transcript-sanitizer's
# Justfile / bin/ scripts if new slow recipes are added.
SLOW_COMMAND_MARKERS = [
    "build-mirror",       # just build-mirror / bin/build-mirror.sh — mirrors+redacts ~1.5GB / ~9000 real transcript files
    "gitleaks-baseline",  # just gitleaks-baseline / bin/gitleaks-baseline.sh — gitleaks over the full raw corpus
    "gitleaks-mirror",    # just gitleaks-mirror recipe name
    "gitleaks-gate",      # bin/gitleaks-gate.sh — underlying script for gitleaks-mirror, also full-corpus-sized
    "redact-check",       # just redact-check / bin/redact-check.sh — dry-run scan of the same full corpus
]

BLOCK_MSG_TEMPLATE = (
    "[block-backgrounded-slow-commands] Blocked: {tool} attempted to background "
    "a known-slow full-corpus command ({marker!r} matched in: {cmd!r}).\n\n"
    "A subagent cannot receive its own background-task completion notification — "
    "only the agent that spawned it can. Backgrounding this command from inside "
    "a subagent stalls forever. This has happened repeatedly in this project's "
    "history.\n\n"
    "Fix: run this as a normal FOREGROUND Bash call with an explicit long "
    "timeout instead, e.g. timeout: 600000 (10 minutes). Do not set "
    "run_in_background, and do not use the Monitor tool for this command."
)


def _matched_marker(command: str) -> str | None:
    if not command:
        return None
    lowered = command.lower()
    for marker in SLOW_COMMAND_MARKERS:
        if marker in lowered:
            return marker
    return None


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return 0

    if tool_name == "Bash":
        if tool_input.get("run_in_background") is not True:
            return 0  # foreground call — never blocked, regardless of command/timeout
        command = tool_input.get("command", "")
        description = tool_input.get("description", "")
        # Check command first (authoritative); fall back to description —
        # observed in real transcripts a background *poll* command can be a
        # generic `while kill -0 $PID; do sleep 5; done` with the actual
        # target command named only in the description.
        marker = _matched_marker(command) or _matched_marker(description)
        if marker is None:
            return 0
        print(
            BLOCK_MSG_TEMPLATE.format(
                tool="Bash(run_in_background=true)", marker=marker, cmd=(command or description)[:200]
            ),
            file=sys.stderr,
        )
        return 2

    if tool_name == "Monitor":
        # Monitor input may carry `command` (shell source) or `ws` (websocket
        # source, never text-matches a shell command marker so it's a no-op
        # here). Real transcripts show the poll loop itself is often generic
        # (`while kill -0 $PID; do sleep 5; done`) with the actual target
        # command named only in `description` — check both.
        command = tool_input.get("command", "")
        description = tool_input.get("description", "")
        marker = _matched_marker(command) or _matched_marker(description)
        if marker is None:
            return 0
        print(
            BLOCK_MSG_TEMPLATE.format(tool="Monitor", marker=marker, cmd=(command or description)[:200]),
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
