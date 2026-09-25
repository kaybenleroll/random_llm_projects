#!/usr/bin/env python3
"""Round-robin-by-replicate schedule: make_schedule.py [--n 10] [--seed 20260924] [--arms a,b,...] -> schedule.json
Every arm gets replicate k before any arm gets replicate k+1; the arm order within each replicate is a seeded shuffle
(so time-of-day / rate-limit drift is not confounded with arm, and an early halt leaves balanced arms)."""
import argparse, json, random
from common import *
ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=10)
ap.add_argument("--seed", type=int, default=20260924)
ap.add_argument("--arms", default=",".join(ARMS))
ap.add_argument("--out", default=SCHEDULE)
ap.add_argument("--print", type=int, default=0, dest="show", help="print the first N scheduled jobs")
a = ap.parse_args()
arms = a.arms.split(",")
rng = random.Random(a.seed)
items = []
for rep in range(1, a.n + 1):
    order = list(arms)
    rng.shuffle(order)
    items += [{"arm": arm, "n": rep} for arm in order]
for pos, it in enumerate(items, 1):
    it["pos"] = pos
atomic_write(a.out, json.dumps({"seed": a.seed, "n_per_arm": a.n, "arms": arms, "items": items}, indent=1))
print("wrote %s: %d runs" % (a.out, len(items)))
for it in items[: a.show]:
    print("  #%-3d %-14s replicate %d" % (it["pos"], it["arm"], it["n"]))
