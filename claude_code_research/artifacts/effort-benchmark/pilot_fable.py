#!/usr/bin/env python3
"""Fable effort pilot. n=1 per arm, task 1, cap10 prompt, model claude-fable-5-1, $6/run.
  ./pilot_fable.py --dry-run                      # DEFAULT. Prints invocations. Never launches claude.
  PILOT_FABLE_STAGE2=1 ./pilot_fable.py --execute <arm>   # STAGE 2 ONLY: one real run (spends subscription quota)
Outputs go to runs-fable-pilot/<arm>/1.* (separate from runs/). common.py, ARMS and runs/ are untouched.
Max effort: env CLAUDE_CODE_EFFORT_LEVEL=max set on the single child process only (plus --effort max); never global/settings."""
import argparse, json, os, sys
import common
from common import ROOT, CWD, STRIP_ENV, ISOLATION_FLAGS, atomic_write, read_json, build_review_prompt, transcript_efforts, log

MODEL = "claude-fable-5-1"
BUDGET = "6"
MAX_OUT = "128000"
VARIANT = "cap10"
PILOT_RUNS = os.path.join(ROOT, "runs-fable-pilot")
PILOT_LOG = os.path.join(ROOT, "logs", "pilot-fable.log")
ORDER = ["fable-low", "fable-medium", "fable-high", "fable-xhigh", "fable-max"]          # cheapest first
EFFORT = {"fable-low": "low", "fable-medium": "medium", "fable-high": "high", "fable-xhigh": "xhigh", "fable-max": "max"}
N = 1
SUBPROC_ENV = {"fable-max": {"CLAUDE_CODE_EFFORT_LEVEL": "max"}}   # per-subprocess only
TRANSCRIPT_FIELD = "assistant lines: top-level `effort` (also `perTurnEffort`); model at message.model"


def command(arm):
    return ["claude", "-p", "--model", MODEL, "--effort", EFFORT[arm], "--output-format", "json"] + ISOLATION_FLAGS + ["--max-budget-usd", BUDGET]


_ORIG_CHILD_ENV = common.child_env


def child_env(arm):
    env = _ORIG_CHILD_ENV(MAX_OUT)          # strips inherited CLAUDE_* incl. CLAUDE_CODE_EFFORT_LEVEL, sets auto-memory off + max output
    env.update(SUBPROC_ENV.get(arm, {}))
    return env


def dry_run():
    base = {k: "" for k in ("CLAUDE_CODE_DISABLE_AUTO_MEMORY", "CLAUDE_CODE_MAX_OUTPUT_TOKENS")}
    for arm in ORDER:
        print("== %s  (requested effort=%s, model=%s, n=1, task 1, prompt variant=%s, prompt_chars=%d)" % (
            arm, EFFORT[arm], MODEL, VARIANT, len(build_review_prompt(VARIANT))))
        print("  cmd   : " + " ".join(repr(c) if c == "" else c for c in command(arm)) + "   (prompt on stdin, cwd=%s)" % CWD)
        print("  budget: --max-budget-usd %s (per run)" % BUDGET)
        print("  env set (names only):")
        for k in base:
            print("    %s  [subprocess-scoped]" % k)
        for k in SUBPROC_ENV.get(arm, {}):
            print("    %s  [subprocess-scoped, EFFORT OVERRIDE; never exported globally]" % k)
        print("  env stripped from child: " + ",".join(STRIP_ENV))
        env = child_env(arm)
        print("  child would have CLAUDE_CODE_EFFORT_LEVEL: %s" % ("yes" if "CLAUDE_CODE_EFFORT_LEVEL" in env else "no"))
        print("  outputs: %s/{1.json,1.review.md,1.raw.json | 1.failed.json}" % os.path.join(PILOT_RUNS, arm))
        print("  effort check: %s ; must equal '%s' on every assistant line" % (TRANSCRIPT_FIELD, EFFORT[arm]))
    print("DRY RUN ONLY: no process launched, no model call.")


def execute(arm):
    global N
    if os.environ.get("PILOT_FABLE_STAGE2") != "1":
        sys.exit("refusing: set PILOT_FABLE_STAGE2=1 (stage 2 only; spends subscription quota)")
    rec_path = os.path.join(PILOT_RUNS, arm, "%d.json" % N)
    if os.path.exists(rec_path):
        sys.exit("already have %s (single attempt per arm; delete deliberately to redo)" % rec_path)
    common.child_env = lambda mot=None: child_env(arm)   # inject per-arm env into common.call_claude
    prompt = build_review_prompt(VARIANT)
    log("PILOT START %s" % arm, PILOT_LOG)
    r = common.call_claude(prompt, MODEL, EFFORT[arm], "review", budget=BUDGET, max_output_tokens=MAX_OUT, allow_partial=True)  # single attempt, no retries
    events = r.pop("events", None); r.pop("cmd", None)
    rec = {"arm": arm, "n": N, "model": MODEL, "effort_requested": EFFORT[arm], "env_effort_override": arm in SUBPROC_ENV,
           "prompt_chars": len(prompt), "prompt_variant": VARIANT, **r}
    if r.get("session_id"):
        tr = transcript_efforts(r["session_id"])
        rec["transcript"] = tr
        rec["effort_applied"] = sorted(tr["effort_counts"]) if tr else None
        rec["effort_verified"] = bool(tr and set(tr["effort_counts"]) == {EFFORT[arm]})
    d = os.path.join(PILOT_RUNS, arm)
    if events is not None:
        atomic_write(os.path.join(d, "%d.raw.json" % N), json.dumps(events))
    if rec.get("ok"):
        atomic_write(os.path.join(d, "%d.review.md" % N), rec["text"])
    rec.pop("text", None)
    atomic_write(rec_path if rec.get("ok") else os.path.join(d, "%d.failed.json" % N), json.dumps(rec, indent=1))
    log("PILOT DONE %s ok=%s status=%s cost=%s effort_verified=%s" % (arm, rec.get("ok"), rec.get("status"), rec.get("cost_usd"), rec.get("effort_verified")), PILOT_LOG)
    sys.exit(0 if rec.get("ok") else 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--execute", choices=ORDER)
    ap.add_argument("--n", type=int, default=1)
    a = ap.parse_args()
    N = a.n
    if a.execute:
        execute(a.execute)
    else:
        dry_run()
