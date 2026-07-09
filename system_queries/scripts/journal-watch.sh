#!/usr/bin/env bash
# Monitor systemd journal entry volume for unusual growth or approaching the SystemMaxUse cap.
# Run manually via `just journal-watch` or on a schedule via the journal-watch.timer/.service pair.
#
# NOTE: disk-usage (du -sm) alone cannot detect a log flood once SystemMaxUse is saturated —
# journald auto-vacuums old entries to stay under the cap as fast as new ones arrive, so disk
# usage stays flat even during an active flood. Detection is therefore based on journal entry
# COUNT logged since the last check (line_count), not disk footprint. current_mb is still
# reported for cap-proximity awareness.

set -uo pipefail

STATE_DIR="$HOME/.cache"
STATE_FILE="$STATE_DIR/journal-watch-state"
LOG_DIR="/home/mcooney/workspace/random_llm_projects/system_queries/logs"
LOG_FILE="$LOG_DIR/journal-watch.log"
LINE_COUNT_THRESHOLD=20000
CAP_MB=8192
CAP_WARN_MB=6554  # 80% of 8G SystemMaxUse cap (aspirational cap; actual cap may still be 2G)

mkdir -p "$STATE_DIR"
mkdir -p "$LOG_DIR"

current_mb=$(du -sm /var/log/journal 2>/dev/null | awk '{print $1}')
current_mb=${current_mb:-0}
now=$(date +%s)

previous_timestamp=""
previous_mb=""
first_run=1

if [ -f "$STATE_FILE" ]; then
    read -r previous_timestamp previous_mb < "$STATE_FILE" 2>/dev/null
    if [[ "$previous_timestamp" =~ ^[0-9]+$ ]] && [[ "$previous_mb" =~ ^[0-9]+$ ]]; then
        first_run=0
    fi
fi

if [ "$first_run" -eq 1 ]; then
    printf '%s\t%s\n' "$now" "$current_mb" > "$STATE_FILE"
    echo "journal-watch: first run, seeded state file with current=${current_mb}MB"
    printf '%s current=%sMB line_count=n/a flagged=0 (first run, state seeded)\n' "$(date -Iseconds)" "$current_mb" >> "$LOG_FILE"
    exit 0
fi

line_count=$(journalctl --since "@$previous_timestamp" --no-pager 2>/dev/null | wc -l)
line_count=${line_count:-0}

flagged=0
if [ "$line_count" -gt "$LINE_COUNT_THRESHOLD" ] || [ "$current_mb" -gt "$CAP_WARN_MB" ]; then
    flagged=1
fi

top_ids=""
if [ "$flagged" -eq 1 ]; then
    top_ids=$(journalctl --since "@$previous_timestamp" --no-pager -o short-precise 2>/dev/null \
        | awk '{print $5}' | sed -E 's/\[.*//; s/:$//' \
        | sort | uniq -c | sort -rn | head -5)
fi

if [ "$flagged" -eq 1 ] && command -v notify-send >/dev/null 2>&1; then
    notify-send -u critical "Journal growth anomaly" \
        "current=${current_mb}MB line_count=${line_count} (since last check)
Top identifiers (since last check):
${top_ids}"
fi

printf '%s\t%s\n' "$now" "$current_mb" > "$STATE_FILE"

if [ "$flagged" -eq 1 ]; then
    echo "journal-watch: ANOMALY current=${current_mb}MB line_count=${line_count} top_identifiers=[${top_ids//$'\n'/; }]"
    printf '%s current=%sMB line_count=%s flagged=1 top_identifiers=[%s]\n' \
        "$(date -Iseconds)" "$current_mb" "$line_count" "${top_ids//$'\n'/; }" >> "$LOG_FILE"
else
    echo "journal-watch: ok current=${current_mb}MB line_count=${line_count}"
    printf '%s current=%sMB line_count=%s flagged=0\n' "$(date -Iseconds)" "$current_mb" "$line_count" >> "$LOG_FILE"
fi

exit 0
