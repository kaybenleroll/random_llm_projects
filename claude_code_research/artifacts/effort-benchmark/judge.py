#!/usr/bin/env python3
"""Blind judge. judge.py <arm> <n> [judge-name ...]  -> judgments/<arm>/<n>.<judge>.json
The judge sees only the review text + answer key (no arm, model, effort or run id). Recall is recomputed
from key_items (never from any self-reported count)."""
import json, os, re, sys
from common import *


def build_prompt(review_text):
    head = open(os.path.join(INPUTS, "judge_prompt_head.txt")).read()
    key = open(os.path.join(INPUTS, "answer-key.md")).read()
    return "%s\n<answer_key>\n%s\n</answer_key>\n\n<review>\n%s\n</review>\n" % (head, key, review_text)


def parse_verdict(text):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        d = json.loads(t)
    except ValueError:
        m = re.search(r"\{.*\}", t, re.S)
        if not m:
            return None, "no JSON found"
        try:
            d = json.loads(m.group(0))
        except ValueError as e:
            return None, "bad JSON: %s" % e
    items = d.get("key_items") if isinstance(d, dict) else None
    if not isinstance(items, list):
        return None, "missing key_items"
    found = {}
    for it in items:
        try:
            i = int(str(it.get("item_id")).split("-")[0])
        except (ValueError, AttributeError):
            return None, "bad item_id %r" % (it,)
        if not isinstance(it.get("found"), bool):
            return None, "non-bool found for %s" % i
        found[i] = {"found": it["found"], "quote": str(it.get("quote", ""))[:400]}
    if sorted(found) != list(range(1, N_KEY + 1)):
        return None, "item ids %s != 1..%d" % (sorted(found), N_KEY)
    return found, None


def judge_one(arm, n, judge, force=False, pilot_dir=None):
    jroot = os.path.join(ROOT, "judgments-fable-pilot") if pilot_dir else JUDGMENTS
    out = os.path.join(jroot, arm, "%d.%s.json" % (n, judge))
    old = read_json(out)
    if old and old.get("ok") and not force:
        return old
    rp = os.path.join(pilot_dir or RUNS, arm, "%d.review.md" % n)
    review = open(rp).read()
    model, effort = JUDGES[judge]
    prompt = build_prompt(review)
    what = "judge %s %s/%d" % (judge, arm, n)
    log("START " + what)

    def once():
        r = call_claude(prompt, model, effort, "judge")
        if r.get("ok"):
            found, err = parse_verdict(r["text"])
            if err:
                r["ok"], r["error"] = False, "parse: " + err
            else:
                r["found"] = found
        return r

    r = with_retries(once, what)
    events = r.pop("events", None)
    r.pop("cmd", None)
    rec = {"arm": arm, "n": n, "judge": judge, "model": model, "effort_requested": effort, **r}
    if rec.get("session_id"):
        tr = transcript_efforts(rec["session_id"])
        rec["effort_verified"] = bool(tr and set(tr["effort_counts"]) == {effort})
    if rec.get("ok"):
        rec["found"] = {str(k): v for k, v in rec["found"].items()}
        rec["recall_count"] = sum(1 for v in rec["found"].values() if v["found"])  # recomputed, not self-reported
        rec["recall"] = rec["recall_count"] / N_KEY
    atomic_write(out if rec.get("ok") else out.replace(".json", ".failed.json"), json.dumps(rec, indent=1))
    log("DONE  %s ok=%s recall=%s wall=%ss out_tokens=%s" % (
        what, rec.get("ok"), rec.get("recall_count"), rec.get("wall_s"), (rec.get("usage") or {}).get("output_tokens")))
    return rec


if __name__ == "__main__":
    argv = sys.argv[1:]
    pilot_dir = None
    if "--pilot-dir" in argv:
        i = argv.index("--pilot-dir")
        pilot_dir = os.path.abspath(argv[i + 1])
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]
    if len(args) < 2:
        sys.exit("usage: judge.py <arm> <n> [judge ...] [--force] [--pilot-dir DIR]")
    judges = args[2:] or list(JUDGES)
    ok = all(judge_one(args[0], int(args[1]), j, "--force" in sys.argv, pilot_dir).get("ok") for j in judges)
    sys.exit(0 if ok else 1)
