#!/usr/bin/env python3
"""Smoke check over completed run records (no model calls): smoke_check.py [--runs runs] [--min-runs 2]
Reads runs/<arm>/<n>.json written by run_arm.py and PASS/FAILs each criterion. Exit 0 only if all pass.

(a) effort applied : record.effort_verified is true AND the session transcript's assistant-line `effort` values are
                     exactly {requested effort} (recomputed here from the transcript file, not just the stored flag).
(b) isolation      : init reports no tools, skills, slash commands or MCP servers; no memory paths; only built-in agents;
                     reported model == requested model; every run has its own session id; all transcripts live in one
                     project directory derived from the harness cwd (so nothing ran in another working directory).
Run-to-run isolation is by construction: each call is a fresh `claude -p` process (new session id, no --continue/--resume)."""
import argparse, glob, json, os, sys

BUILTIN_AGENTS = {"claude", "Explore", "general-purpose", "Plan", "statusline-setup"}


def transcript_effort_counts(path):
    vals = {}
    try:
        for line in open(path):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "assistant" and "effort" in d:
                vals[str(d["effort"])] = vals.get(str(d["effort"]), 0) + 1
    except OSError:
        return None
    return vals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--min-runs", type=int, default=2)
    a = ap.parse_args()
    recs = []
    for p in sorted(glob.glob(os.path.join(a.runs, "*", "*.json"))):
        b = os.path.basename(p)
        if b.endswith((".raw.json", ".failed.json", ".recovered.json")):
            continue
        try:
            recs.append((p, json.load(open(p))))
        except ValueError:
            pass
    results = []

    def check(name, ok, detail=""):
        results.append(ok)
        print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("  -- " + detail) if detail and not ok else ""))

    check("at least %d completed run records" % a.min_runs, len(recs) >= a.min_runs, "found %d" % len(recs))
    sids, dirs = [], set()
    for p, r in recs:
        tag = "%s/%s" % (r.get("arm"), r.get("n"))
        init = r.get("init") or {}
        tr = r.get("transcript") or {}
        counts = transcript_effort_counts(tr.get("path", ""))
        req = r.get("effort_requested")
        check("%s effort applied (transcript effort values == {%s})" % (tag, req),
              bool(r.get("effort_verified")) and counts is not None and set(counts) == {req},
              "stored flag=%r transcript counts=%r" % (r.get("effort_verified"), counts))
        check("%s no tools/skills/slash-commands/MCP" % tag,
              all(init.get(k) == [] for k in ("tools", "skills", "slash_commands", "mcp_servers")), repr({k: init.get(k) for k in ("tools", "skills", "slash_commands", "mcp_servers")}))
        check("%s no memory paths" % tag, not init.get("memory_paths"), repr(init.get("memory_paths")))
        check("%s only built-in agents" % tag, set(init.get("agents") or []) <= BUILTIN_AGENTS, repr(init.get("agents")))
        check("%s reported model == requested model" % tag, r.get("model_reported") == r.get("model"),
              "%r vs %r" % (r.get("model_reported"), r.get("model")))
        check("%s exit 0 and ok" % tag, r.get("exit_code") == 0 and bool(r.get("ok")))
        sids.append(r.get("session_id"))
        if tr.get("path"):
            dirs.add(os.path.dirname(tr["path"]))
    check("every run has a distinct session id", len(sids) == len(set(sids)) and None not in sids)
    check("all transcripts in one cwd-derived project dir ending '-cwd'", len(dirs) == 1 and next(iter(dirs)).endswith("-cwd"), repr(dirs))
    print("\nRESULT: %s" % ("ALL PASS" if all(results) else "FAILURES PRESENT"))
    sys.exit(0 if all(results) else 1)


main()
