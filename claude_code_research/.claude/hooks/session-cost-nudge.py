#!/usr/bin/env python3
"""
UserPromptSubmit hook: cost-aware session-handoff nudge (pilot, project-scoped).

Computes the current context replay cost in absolute tokens from the latest
assistant turn's `usage` object, and — edge-triggered on a latched high-water
mark — prepends an escalating reminder to context when the cost crosses a rung
(~150k informational, ~300k active nudge, ~500k strong recommendation).

Design notes (see plan quizzical-spinning-lemon.md):
  - Cost = usage.input_tokens + cache_read_input_tokens + cache_creation_input_tokens
    (window-independent; three disjoint input partitions, no double-count).
  - Reads only a BOUNDED TAIL of the transcript (seek from end, enlarge on miss)
    — never readlines() the whole multi-MB transcript.
  - Per-session state file `.scratch/.session-nudge-<session_id>.json` avoids the
    read-modify-write race a shared file would have — no flock needed.
  - High-water latch: only fires when current_rung > highest_rung_fired, so a
    post-compaction token drop never re-fires a lower rung.
  - Whole body wrapped so any error exits silently — never hard-fail a prompt.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Rung thresholds in absolute cost tokens. `>=` crosses.
RUNG_THRESHOLDS = [
    (3, 500_000),
    (2, 300_000),
    (1, 150_000),
]

# Bounded tail read parameters.
INITIAL_TAIL_BYTES = 64 * 1024
MAX_TAIL_BYTES = 2 * 1024 * 1024


def rung_for_cost(cost: int) -> int:
    """Return the highest rung (0-3) reached by `cost` tokens."""
    for rung, threshold in RUNG_THRESHOLDS:
        if cost >= threshold:
            return rung
    return 0


def message_for_rung(rung: int, cost: int) -> str:
    """Escalating reminder text, prepended to context on a genuine crossing."""
    measured = f"{cost:,}"
    if rung == 1:
        return (
            f"[session-cost] Context has crossed ~150k tokens (measured: {measured}). "
            "Informational only — no action needed."
        )
    if rung == 2:
        return (
            f"[session-cost] Context is at ~300k tokens (measured: {measured}). "
            "If you are at a natural stopping point — no pending edits, not mid-tool-chain — "
            "consider /new-session to hand off cleanly. Otherwise continue."
        )
    # rung == 3
    return (
        f"[session-cost] Context is at ~500k tokens (measured: {measured}) — "
        "replay cost per turn is now significant. Strongly consider /new-session at the "
        "next clean seam (a task boundary with no pending state)."
    )


def _read_tail_lines(path: Path, tail_bytes: int):
    """Read up to the last `tail_bytes` of `path`.

    Returns (lines, reached_start). `lines` are decoded text lines; when the read
    does not cover byte 0 the first (possibly partial) line is dropped, so every
    returned line is complete. `reached_start` is True when the read spanned the
    whole file (nothing was dropped).
    """
    file_size = path.stat().st_size
    read_size = min(tail_bytes, file_size)
    with open(path, "rb") as f:
        f.seek(file_size - read_size)
        data = f.read(read_size)
    reached_start = read_size >= file_size
    text = data.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if not reached_start and lines:
        # First line may be a partial mid-line fragment — drop it. Safe because
        # we enlarge the read whenever no usage line is found, so any usage line
        # straddling the boundary is fully captured on the next, larger pass.
        lines = lines[1:]
    return lines, reached_start


def _usage_cost(entry: dict):
    """Return cost tokens for an assistant entry with non-null usage, else None."""
    if entry.get("type") != "assistant":
        return None
    usage = entry.get("message", {}).get("usage")
    if usage is None:
        # Fall back to a top-level usage field if the schema ever changes.
        usage = entry.get("usage")
    if not usage:
        return None
    return (
        (usage.get("input_tokens", 0) or 0)
        + (usage.get("cache_read_input_tokens", 0) or 0)
        + (usage.get("cache_creation_input_tokens", 0) or 0)
    )


def find_last_usage_cost(transcript_path: Path):
    """Walk the transcript backward for the last assistant line with non-null usage.

    Reads only a bounded tail, enlarging it (doubling, capped) if no usage-bearing
    assistant line is found. Returns cost tokens, or None if there is no such line
    anywhere (brand-new session / first turn).
    """
    file_size = transcript_path.stat().st_size
    if file_size == 0:
        return None
    tail_bytes = INITIAL_TAIL_BYTES
    while True:
        lines, reached_start = _read_tail_lines(transcript_path, tail_bytes)
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            cost = _usage_cost(entry)
            if cost is not None:
                return cost
        if reached_start or tail_bytes >= MAX_TAIL_BYTES:
            return None
        tail_bytes = min(tail_bytes * 2, MAX_TAIL_BYTES)


def load_highest_rung(state_path: Path) -> int:
    try:
        return int(json.loads(state_path.read_text()).get("highest_rung_fired", 0))
    except Exception:
        return 0


def persist_rung(state_path: Path, rung: int) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"highest_rung_fired": rung}))


def append_event(scratch: Path, session_id: str, rung: int, cost: int) -> None:
    try:
        scratch.mkdir(parents=True, exist_ok=True)
        event = {
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rung": rung,
            "cost_tokens": cost,
        }
        with open(scratch / "nudge-events.jsonl", "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return

    try:
        transcript_path_str = data.get("transcript_path", "")
        session_id = data.get("session_id", "")
        cwd = data.get("cwd", "") or os.getcwd()
        if not transcript_path_str or not session_id:
            return

        transcript_path = Path(transcript_path_str)
        if not transcript_path.exists():
            return

        cost = find_last_usage_cost(transcript_path)
        if cost is None:
            # Brand-new session, first turn — nothing to walk back to. Never fire
            # rung 1 on an undefined/zero sum.
            return

        current_rung = rung_for_cost(cost)
        if current_rung == 0:
            return

        scratch = Path(cwd) / ".scratch"
        state_path = scratch / f".session-nudge-{session_id}.json"
        highest = load_highest_rung(state_path)

        if current_rung <= highest:
            # Already fired at or above this rung — latched. Common fast path.
            return

        print(message_for_rung(current_rung, cost), flush=True)
        persist_rung(state_path, current_rung)
        append_event(scratch, session_id, current_rung, cost)
    except Exception:
        # Never hard-fail the user's prompt.
        return


if __name__ == "__main__":
    main()
