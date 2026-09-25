#!/usr/bin/env python3
"""Analyse the effort experiment. analyze.py [--schedule schedule.json] [--boot 10000] [--seed 1] [--out results.md]
Recall is ALWAYS recomputed from the judges' key_items found flags (13 items), never from self-reported counts.
Primary recall per run = mean of the two judges' recalls. A run with no completed review (terminal failure, e.g.
token/budget cap hit with no answer) counts as recall 0 in the ITT columns; completed-only columns are also shown."""
import argparse, json, os, random, statistics as st
from common import *

ap = argparse.ArgumentParser()
ap.add_argument("--schedule", default=SCHEDULE)
ap.add_argument("--boot", type=int, default=10000)
ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--out", default=os.path.join(ROOT, "results.md"))
a = ap.parse_args()
sched = read_json(a.schedule)
runs = {}   # (arm, n) -> dict
for it in sched["items"]:
    arm, n = it["arm"], it["n"]
    rec = read_json(os.path.join(RUNS, arm, "%d.json" % n))
    failed = read_json(os.path.join(RUNS, arm, "%d.failed.json" % n))
    if not rec and not failed:
        continue                       # not run yet
    d = {"arm": arm, "n": n, "ok": bool(rec and rec.get("ok")), "rec": rec or failed, "judges": {}}
    if d["ok"]:
        for j in JUDGES:
            jr = read_json(os.path.join(JUDGMENTS, arm, "%d.%s.json" % (n, j)))
            if jr and jr.get("ok"):
                # recompute from key_items, never trust any self-reported count
                d["judges"][j] = {int(k): v["found"] for k, v in jr["found"].items()}
    runs[(arm, n)] = d


def recall(d):
    """Mean over available judges of found/13; None if no review or no judgment."""
    if not d["ok"]:
        return 0.0                     # ITT: no review => nothing found
    vals = [sum(f.values()) / N_KEY for f in d["judges"].values()]
    return sum(vals) / len(vals) if vals else None


def boot_diff(x, y, rng, B):
    """Bootstrap 95% CI of mean(y) - mean(x)."""
    if len(x) < 2 or len(y) < 2:
        return None
    diffs = []
    for _ in range(B):
        bx = [rng.choice(x) for _ in x]
        by = [rng.choice(y) for _ in y]
        diffs.append(sum(by) / len(by) - sum(bx) / len(bx))
    diffs.sort()
    return diffs[int(0.025 * B)], diffs[int(0.975 * B) - 1]


def fmt(v, p=3):
    return "n/a" if v is None else ("%.*f" % (p, v))


out = []
P = out.append
by_arm = {}
for (arm, n), d in sorted(runs.items()):
    by_arm.setdefault(arm, []).append(d)
P("# Effort experiment results\n")
P("Runs found: %d; schedule seed %s, n per arm %s.\n" % (len(runs), sched["seed"], sched["n_per_arm"]))
P("## Per-arm summary (recall = mean of both judges, over 13 key items)\n")
P("| arm | runs | completed | recall mean (ITT) | median | range | recall mean (completed only) | out tok mean | thinking tok mean | wall s mean | cost $ mean | out tok / recalled defect | truncated |")
P("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
rec_by_arm = {}
for arm in ARMS:
    ds = by_arm.get(arm, [])
    if not ds:
        continue
    rs = [recall(d) for d in ds if recall(d) is not None]
    rec_by_arm[arm] = rs
    comp = [d for d in ds if d["ok"]]
    rc = [recall(d) for d in comp if recall(d) is not None]
    tok = [d["rec"]["usage"]["output_tokens"] for d in comp]
    thk = [d["rec"]["usage"].get("thinking_tokens") or 0 for d in comp]
    wall = [d["rec"]["wall_s"] for d in ds if d["rec"].get("wall_s") is not None]
    cost = [d["rec"].get("cost_usd") or 0 for d in ds]
    trunc = sum(1 for d in ds if d["rec"].get("truncated") or d["rec"].get("terminal"))
    mean_rec = sum(rs) / len(rs) if rs else None
    tpd = (sum(tok) / len(tok)) / (mean_rec * N_KEY) if tok and mean_rec else None
    P("| %s | %d | %d | %s (%s/13) | %s | %s-%s | %s | %s | %s | %s | %s | %s | %d |" % (
        arm, len(ds), len(comp), fmt(mean_rec), fmt(mean_rec * N_KEY if mean_rec is not None else None, 1),
        fmt(st.median(rs) if rs else None), fmt(min(rs) if rs else None, 2), fmt(max(rs) if rs else None, 2),
        fmt(sum(rc) / len(rc) if rc else None), fmt(sum(tok) / len(tok) if tok else None, 0),
        fmt(sum(thk) / len(thk) if thk else None, 0), fmt(sum(wall) / len(wall) if wall else None, 0),
        fmt(sum(cost) / len(cost), 2), fmt(tpd, 0), trunc))

P("\n## Per-judge recall (mean over runs)\n")
P("| arm | " + " | ".join(JUDGES) + " |")
P("|---|" + "---|" * len(JUDGES))
for arm in ARMS:
    ds = [d for d in by_arm.get(arm, []) if d["ok"]]
    if not ds:
        continue
    cells = []
    for j in JUDGES:
        v = [sum(d["judges"][j].values()) / N_KEY for d in ds if j in d["judges"]]
        cells.append(fmt(sum(v) / len(v) if v else None))
    P("| %s | %s |" % (arm, " | ".join(cells)))

P("\n## Pairwise vs cheaper baseline within each model (bootstrap 95% CI on recall difference, arm - baseline)\n")
P("| comparison | mean diff | 95% CI | n (arm/base) | CI excludes 0 |")
P("|---|---|---|---|---|")
rng = random.Random(a.seed)
for fam, base in BASELINE.items():
    for arm in ARMS:
        if not arm.startswith(fam + "-") or arm == base or arm not in rec_by_arm or base not in rec_by_arm:
            continue
        x, y = rec_by_arm[base], rec_by_arm[arm]
        ci = boot_diff(x, y, rng, a.boot)
        md = sum(y) / len(y) - sum(x) / len(x)
        P("| %s vs %s | %s | %s | %d/%d | %s |" % (
            arm, base, fmt(md), "n/a (n<2)" if ci is None else "[%s, %s]" % (fmt(ci[0]), fmt(ci[1])),
            len(y), len(x), "n/a" if ci is None else ("yes" if ci[0] > 0 or ci[1] < 0 else "no")))

# inter-judge agreement over item-level verdicts (runs where both judges succeeded)
P("\n## Inter-judge agreement (item level)\n")
jn = list(JUDGES)
both = [d for d in runs.values() if d["ok"] and all(j in d["judges"] for j in jn)]
if both:
    agree = tot = 0
    a1 = b1 = 0
    per_item = {i: [0, 0] for i in range(1, N_KEY + 1)}
    for d in both:
        for i in range(1, N_KEY + 1):
            x, y = d["judges"][jn[0]][i], d["judges"][jn[1]][i]
            tot += 1; agree += (x == y); a1 += x; b1 += y
            per_item[i][0] += (x == y); per_item[i][1] += 1
    po = agree / tot
    pa, pb = a1 / tot, b1 / tot
    pe = pa * pb + (1 - pa) * (1 - pb)
    kappa = (po - pe) / (1 - pe) if pe < 1 else float("nan")
    rc0 = [sum(d["judges"][jn[0]].values()) for d in both]
    rc1 = [sum(d["judges"][jn[1]].values()) for d in both]
    P("Runs judged by both: %d (%d item verdict pairs). Raw agreement %.1f%%, Cohen's kappa %.2f. "
      "%s found rate %.1f%%, %s found rate %.1f%%." % (len(both), tot, 100 * po, kappa, jn[0], 100 * pa, jn[1], 100 * pb))
    P("Mean per-run count: %s %.2f/13, %s %.2f/13; mean absolute per-run count difference %.2f.\n" % (
        jn[0], sum(rc0) / len(rc0), jn[1], sum(rc1) / len(rc1), sum(abs(x - y) for x, y in zip(rc0, rc1)) / len(rc0)))
    P("Per-item agreement: " + ", ".join("#%d %d/%d" % (i, v[0], v[1]) for i, v in per_item.items()))
else:
    P("No run judged by both judges yet.")

P("\n## Effort verification (transcript `effort` field vs requested)\n")
for arm in ARMS:
    ds = by_arm.get(arm, [])
    if ds:
        P("- %s: %s" % (arm, ", ".join("run %d -> %s" % (d["n"], (d["rec"].get("transcript") or {}).get("effort_counts")) for d in ds)))
open(a.out, "w").write("\n".join(out) + "\n")
print("\n".join(out))
