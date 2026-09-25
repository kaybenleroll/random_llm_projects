#!/usr/bin/env bash
# Full experiment launcher (FOREGROUND: run it under nohup/setsid/systemd-inhibit yourself).
# Usage: ./run_full.sh [N_PER_ARM=10] [ARMS=comma list, default the 6 non-max arms] [JOBS=2]
# Resumable + idempotent: re-run the same command after any interruption; completed steps are skipped.
# Max arms are deliberately excluded (they can exhaust the token budget without an answer; see README, Known limitations).
set -u
cd "$(dirname "$0")"
N=${1:-10}; ARMS=${2:-opus-medium,opus-high,opus-xhigh,sonnet-medium,sonnet-high,sonnet-xhigh}; JOBS=${3:-2}
[ -f schedule.json ] || python3 make_schedule.py --n "$N" --arms "$ARMS" --seed 20260924
mkdir -p logs
echo $$ > logs/orch.pid
PY=
crashed() {
  # unexpected exit: make sure STATUS.txt ends with a FINAL line
  [ -n "$PY" ] && { pkill -TERM -P "$PY" 2>/dev/null; kill "$PY" 2>/dev/null; }
  if ! grep -q '^FINAL:' STATUS.txt 2>/dev/null; then
    printf 'state: FINISHED (wrapper exit)\nlast error: run_full.sh exited/was signalled before orchestrator wrote FINAL\nFINAL: CRASHED\n' >> STATUS.txt
  fi
}
trap 'crashed; exit 143' TERM INT HUP
python3 orchestrate.py --schedule schedule.json --jobs "$JOBS" &
PY=$!
wait "$PY"; RC=$?
trap - TERM INT HUP
# orchestrator ended (any way): ensure FINAL exists
if ! grep -q '^FINAL:' STATUS.txt 2>/dev/null; then
  printf 'last error: orchestrator process died with rc=%s\nFINAL: CRASHED\n' "$RC" >> STATUS.txt
fi
exit "$RC"
