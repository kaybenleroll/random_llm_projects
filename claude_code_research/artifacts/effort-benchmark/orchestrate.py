#!/usr/bin/env python3
"""Resumable orchestrator: orchestrate.py [--schedule schedule.json] [--jobs 1] [--no-judge] [--limit N]
Per schedule item: review -> both judges. Completed steps (ok=true files) are skipped, so re-running resumes.
Failed steps are retried (see common.with_retries) then logged and left incomplete for the next invocation.
Graceful stop: `touch STOP` (checked before each item). STATUS.txt is rewritten atomically after every step; its last line
is 'FINAL: DONE|HALTED_WEEKLY_LIMIT|HALTED_CONSECUTIVE_FAILURES|STOPPED' when this process ends (run_full.sh adds
'FINAL: CRASHED' if the process dies without one)."""
import argparse, glob, os, sys, threading, time, traceback
from concurrent.futures import ThreadPoolExecutor
import common
from common import *
from limits import LimitGate
from run_arm import run_review
from judge import judge_one

MAX_CONSEC_FAILS = 6
STATUS = os.path.join(ROOT, "STATUS.txt")

ap = argparse.ArgumentParser()
ap.add_argument("--schedule", default=SCHEDULE)
ap.add_argument("--jobs", type=int, default=1)
ap.add_argument("--no-judge", action="store_true")
ap.add_argument("--limit", type=int, default=0, help="only the first N schedule items")
ap.add_argument("--status", default=STATUS)
a = ap.parse_args()
sched = read_json(a.schedule)
items = sched["items"][: a.limit or None]
stop_file = os.path.join(ROOT, "STOP")
failed = []
lock = threading.Lock()
T0 = time.time()
S = {"state": "STARTING", "last_error": "none", "consec": 0, "halt": None, "final": None}


def counts():
    arms = sorted({it["arm"] for it in items})
    tot = {x: sum(1 for it in items if it["arm"] == x) for x in arms}
    rows = []
    for arm in arms:
        ok = {int(os.path.basename(p)[:-5]) for p in glob.glob(os.path.join(RUNS, arm, "*.json"))
              if os.path.basename(p)[:-5].isdigit() and (read_json(p) or {}).get("ok")}
        fl = {int(os.path.basename(p).split(".")[0]) for p in glob.glob(os.path.join(RUNS, arm, "*.failed.json"))} - ok
        sched_ns = {it["n"] for it in items if it["arm"] == arm}
        rows.append((arm, len(ok & sched_ns), len(fl & sched_ns), tot[arm]))
    jc = {}
    for j in JUDGES:
        jc[j] = sum(1 for p in glob.glob(os.path.join(JUDGMENTS, "*", "*.%s.json" % j))
                    if not p.endswith(".failed.json") and (read_json(p) or {}).get("ok"))
    return rows, jc


def write_status(final=None):
    with lock:
        if final:
            S["final"] = final
        try:
            rows, jc = counts()
        except Exception as e:      # status must never take the sweep down
            rows, jc = [], {}
            S["last_error"] = "status counting failed: %r" % (e,)
        L = ["updated: " + time.strftime("%Y-%m-%d %H:%M:%S %Z"),
             "started: %s (elapsed %.1f h)" % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(T0)), (time.time() - T0) / 3600),
             "pid: %d   jobs: %d   schedule items: %d" % (os.getpid(), a.jobs, len(items)),
             "state: " + S["state"],
             "consecutive failed runs: %d (halt at %d)" % (S["consec"], MAX_CONSEC_FAILS),
             "last error: " + S["last_error"],
             "", "arm             done failed total"]
        for arm, d, f, t in rows:
            L.append("%-15s %4d %6d %5d" % (arm, d, f, t))
        L.append("%-15s %4d %6d %5d" % ("ALL", sum(r[1] for r in rows), sum(r[2] for r in rows), sum(r[3] for r in rows)))
        L.append("judgings ok: " + ", ".join("%s %d/%d" % (j, c, sum(r[1] for r in rows)) for j, c in jc.items()))
        if final:
            L.append("FINAL: " + final)
        atomic_write(a.status, "\n".join(L) + "\n")


def set_state(s):
    S["state"] = s
    log("STATE " + s)
    write_status()


gate = LimitGate(on_state=set_state, stop_file=stop_file)
common.GATE = gate


def note(ok, what, rec=None):
    """Track consecutive failures (usage-limit failures are not counted) and refresh STATUS.txt."""
    with lock:
        if ok:
            S["consec"] = 0
        elif not (rec or {}).get("limit_halt") and not (rec or {}).get("limit"):
            S["consec"] += 1
            S["last_error"] = "%s %s: %s" % (time.strftime("%H:%M:%S"), what, str((rec or {}).get("error"))[:300])
            if S["consec"] >= MAX_CONSEC_FAILS and not S["halt"]:
                S["halt"] = "HALTED_CONSECUTIVE_FAILURES"
                log("HALT: %d consecutive failed runs" % S["consec"])
        elif (rec or {}).get("limit"):
            S["last_error"] = "%s %s: %s" % (time.strftime("%H:%M:%S"), what, str((rec or {}).get("error"))[:300])
    write_status()


def pipeline(it):
    if os.path.exists(stop_file):
        log("STOP file present, skipping %s/%d" % (it["arm"], it["n"]))
        return
    if gate.halted or S["halt"]:
        return
    arm, n = it["arm"], it["n"]
    try:
        rec = run_review(arm, n)
        note(bool(rec.get("ok")), "review %s/%d" % (arm, n), rec)
        if not rec.get("ok"):
            with lock:
                failed.append("review %s/%d" % (arm, n))
            return
        if a.no_judge:
            return
        for j in JUDGES:
            if gate.halted or S["halt"]:
                with lock:
                    failed.append("%s %s/%d (halted)" % (j, arm, n))
                return
            jr = judge_one(arm, n, j)
            note(bool(jr.get("ok")), "%s %s/%d" % (j, arm, n), jr)
            if not jr.get("ok"):
                with lock:
                    failed.append("%s %s/%d" % (j, arm, n))
    except Exception as e:  # never let one item kill the sweep
        log("EXCEPTION %s/%d: %r\n%s" % (arm, n, e, traceback.format_exc()))
        with lock:
            failed.append("exception %s/%d" % (arm, n))
        note(False, "exception %s/%d" % (arm, n), {"error": repr(e)})


log("orchestrator start: %d items, jobs=%d, pid=%d" % (len(items), a.jobs, os.getpid()))
set_state("RUNNING")
final = "CRASHED"
try:
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        list(ex.map(pipeline, items))
    if gate.halted:
        final = "HALTED_WEEKLY_LIMIT"
        S["last_error"] = "usage limit: " + gate.halted
    elif S["halt"]:
        final = S["halt"]
    elif os.path.exists(stop_file):
        final = "STOPPED"
    else:
        final = "DONE"
except BaseException as e:
    S["last_error"] = "orchestrator exception: %r" % (e,)
    log("ORCHESTRATOR CRASH: %r\n%s" % (e, traceback.format_exc()))
    final = "CRASHED"
S["state"] = "FINISHED"
write_status(final)
log("orchestrator end: FINAL %s. incomplete steps: %s" % (final, failed or "none"))
sys.exit(0 if final == "DONE" else 1)
