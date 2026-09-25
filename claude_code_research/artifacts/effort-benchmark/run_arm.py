#!/usr/bin/env python3
"""Run ONE reviewer pass: run_arm.py <arm> <n> [--force] [--prompt-variant cap10] [--max-budget-usd 4.5]
  -> runs/<arm>/<n>.json (+ .review.md, .raw.json).
Skips if runs/<arm>/<n>.json already exists with ok=true (use --force to redo).
Status of a stored record ('status' field):
  ok         clean completion (records written before 2026-09-25 have no 'status' field; treat as ok)
  truncated  usable partial review (budget-guard stop, max_tokens, error subtype): text reconstructed from the transcript /
             raw events when CLI result text is empty; ok=True (judgeable) but truncated=True. Never pool with complete runs.
  failed     no usable text -> <n>.failed.json
Every record carries 'recon': per-turn output tokens/stop reasons, total output tokens over ALL turns (deduped by requestId),
thinking/text chars, truncated flag, terminal reason (see reconstruct.py). usage.output_tokens is ONE turn only.
Budget precedence: --max-budget-usd > env EFFORT_BUDGET_USD_REVIEW > arm spec > common.BUDGET_USD (unchanged default)."""
import argparse, json, os, sys
from common import *


def run_review(arm, n, force=False, prompt_variant=None, budget=None):
    spec = arm_spec(arm)
    model, effort = spec["model"], spec["effort"]
    variant = prompt_variant or spec["prompt_variant"]
    rec_path = os.path.join(RUNS, arm, "%d.json" % n)
    old = read_json(rec_path)
    if old and old.get("ok") and not force:
        return old
    oldf = read_json(os.path.join(RUNS, arm, "%d.failed.json" % n))
    if oldf and oldf.get("terminal") and not force:   # deterministic failure already recorded; --force to redo
        return oldf
    prompt = build_review_prompt(variant)
    what = "review %s/%d" % (arm, n)
    log("START " + what + (" variant=%s" % variant if variant else ""))
    r = with_retries(lambda: call_claude(prompt, model, effort, "review", budget=budget or spec["budget"],
                                         max_output_tokens=spec["max_output_tokens"], allow_partial=True), what)
    events = r.pop("events", None)
    r.pop("cmd", None)
    rec = {"arm": arm, "n": n, "model": model, "effort_requested": effort, "prompt_chars": len(prompt),
           "prompt_variant": variant or "default", **r}
    if r.get("session_id"):
        tr = transcript_efforts(r["session_id"])
        rec["transcript"] = tr
        rec["effort_verified"] = bool(tr and set(tr["effort_counts"]) == {effort})
    if "truncated" not in rec:
        rec["truncated"] = rec.get("stop_reason") not in (None, "end_turn", "stop_sequence")
    d = os.path.join(RUNS, arm)
    if events is not None:
        atomic_write(os.path.join(d, "%d.raw.json" % n), json.dumps(events))
    if rec.get("ok"):
        atomic_write(os.path.join(d, "%d.review.md" % n), rec["text"])
    text = rec.pop("text", None)
    if rec.get("ok"):
        atomic_write(rec_path, json.dumps(rec, indent=1))
    else:
        atomic_write(os.path.join(d, "%d.failed.json" % n), json.dumps(rec, indent=1))
    rc = rec.get("recon") or {}
    log("DONE  %s ok=%s status=%s out_tokens_last_turn=%s out_tokens_total=%s turns=%s wall=%ss stop=%s truncated=%s effort_verified=%s" % (
        what, rec.get("ok"), rec.get("status"), (rec.get("usage") or {}).get("output_tokens"), rc.get("total_output_tokens"),
        rc.get("turns"), rec.get("wall_s"), rec.get("stop_reason"), rec.get("truncated"), rec.get("effort_verified")))
    return rec


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("arm", choices=all_arm_names())
    ap.add_argument("n", type=int)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--prompt-variant", choices=sorted(PROMPT_VARIANTS), default=None)
    ap.add_argument("--max-budget-usd", default=None)
    a = ap.parse_args()
    rec = run_review(a.arm, a.n, a.force, a.prompt_variant, a.max_budget_usd)
    sys.exit(0 if rec.get("ok") else 1)
