#!/usr/bin/env python3
"""
Verification harness for a proposed regex-based pre-dispatch check ("does
this lineage's terminal Stress-Test Log entry show fold work left
incomplete?"). Run this BEFORE adopting any such gate — it tells you the
gate's false-positive rate against terminal lineages that actually
succeeded, and its true-positive rate against ones that didn't conclude.

Requires lineages.csv and the same STAGING_DIR already used by
parse_stress_test_logs.py (run that script first).

USAGE
-----
  python3 check_placeholder_bullet.py STAGING_DIR --lineages-csv LINEAGES_CSV

The regex below (PLACEHOLDER_RE) is a STARTING POINT, not a validated gate —
edit it to match the specific trigger language you're evaluating, then
re-run. Report the false-positive rate against CLEAN/ACCEPTED-terminal
lineages before trusting any number this produces; a gate that fires on a
large fraction of successful lineages is not usable as a hard block
regardless of its true-positive rate on the non-concluding set.

CAVEAT — do not conflate "non-concluding" with "abandoned inside the
review loop." In one measured sample of 18 lineages whose log's terminal
entry was RERUN_NEEDED with no closing entry, 0 had actually died inside
the stress-test loop — 78% had a corresponding issue/PR closed within
hours-to-days of the last log entry, meaning the work shipped and the log
was simply never updated with a closing entry. Before building a gate on
"lineage never reached CLEAN/ACCEPTED," check a sample of your own
non-concluding lineages against issue/PR history the same way, or the gate
will target a failure mode that mostly doesn't exist.
"""
import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_stress_test_logs as P

# Starting-point regex — edit to match your actual proposed trigger language.
PLACEHOLDER_RE = re.compile(
    r"(?i)"
    r"\bnot (?:yet )?folded\b"
    r"|\bstill (?:open|unresolved|has|describes|omits|false|contradicts|understated)\b"
    r"|\bremain(?:s|ing)? (?:open|unresolved)\b"
    r"|\bunaddressed\b"
    r"|\bleft (?:untouched|unaddressed|unresolved)\b"
    r"|\bsession paused\b"
    r"|\bpaused for handoff\b"
    r"|\bhand(?:ed)?[- ]?off\b"
    r"|\bno fixes applied\b"
    r"|\bbefore fold work (?:begins|began|begin)\b"
    r"|\bfold work (?:has not|hasn't|not) (?:begun|started)\b"
    r"|\bdeferred\b"
    r"|\bnot (?:fully )?addressed\b"
    r"|\bcarried[- ]over\b"
    r"|^\s*(?:Action|Self-review|Resolution)\s*:\s*(?:n/?a|TBD|TODO|placeholder)\b"
)


def find_terminal_block(path):
    """Re-run the parser's per-file logic and return (header_line, body_text)
    for the block selected as terminal, or (None, None) if none."""
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    section = P.extract_section(text)
    if section is None:
        return None, None

    headers = list(P.H3_SPLIT_RE.finditer(section))
    blocks = []
    bodies = []
    for i, hm in enumerate(headers):
        header_line = hm.group(1)
        body_start = hm.end()
        body_end = headers[i + 1].start() if i + 1 < len(headers) else len(section)
        body = section[body_start:body_end]
        parsed = P.classify_and_parse_header(header_line)
        parsed["order_in_section"] = i
        blocks.append(parsed)
        bodies.append(body)

    terminal_type, terminal_block = P.pick_terminal(blocks)
    if terminal_block is None:
        return None, None
    idx = terminal_block["order_in_section"]
    return terminal_block.get("header"), bodies[idx]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("staging_dir", help="Same STAGING_DIR passed to parse_stress_test_logs.py")
    ap.add_argument("--lineages-csv", required=True, help="Path to lineages.csv produced by parse_stress_test_logs.py")
    args = ap.parse_args()

    staging_dir = os.path.abspath(args.staging_dir)

    with open(args.lineages_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    positive_terms = {"CLEAN", "ACCEPTED"}
    gated_terms = {"RESTRUCTURE", "UNSETTLED", "PREMATURE"}

    positive_lineages, nonconcluding_lineages, gated_lineages = [], [], []
    for r in rows:
        tv = r["terminal_verdict"]
        if tv in positive_terms:
            positive_lineages.append(r)
        elif tv in gated_terms:
            gated_lineages.append(r)
        else:
            nonconcluding_lineages.append(r)

    print(f"positive (CLEAN+ACCEPTED) lineages: {len(positive_lineages)}")
    print(f"gated (RESTRUCTURE+UNSETTLED+PREMATURE) lineages: {len(gated_lineages)}")
    print(f"non-concluding (RERUN_NEEDED-terminal/abandoned/superseded) lineages: {len(nonconcluding_lineages)}")
    print()

    def check_group(name, group):
        n_total = 0
        n_trip = 0
        n_no_terminal_block = 0
        trip_examples = []
        for r in group:
            machine, fname = r["machine"], r["file"]
            path = os.path.join(staging_dir, machine, fname)
            if not os.path.exists(path):
                print(f"  WARN missing file: {path}")
                continue
            header, body = find_terminal_block(path)
            n_total += 1
            if body is None:
                n_no_terminal_block += 1
                continue
            if PLACEHOLDER_RE.search(body) or (header and PLACEHOLDER_RE.search(header)):
                n_trip += 1
                trip_examples.append((machine, fname, header))
        pct = round(100 * n_trip / n_total, 1) if n_total else None
        print(f"=== {name} ===")
        print(f"n={n_total} n_no_terminal_block={n_no_terminal_block} n_trip={n_trip} pct={pct}")
        for ex in trip_examples[:15]:
            print("   TRIP:", ex)
        if len(trip_examples) > 15:
            print(f"   ... and {len(trip_examples) - 15} more")
        print()
        return n_total, n_trip, trip_examples

    check_group("FALSE-POSITIVE CHECK (positive-terminal lineages: CLEAN+ACCEPTED)", positive_lineages)
    check_group("TRUE-POSITIVE CHECK (non-concluding lineages)", nonconcluding_lineages)
    check_group("(context only) gated lineages (RESTRUCTURE/UNSETTLED/PREMATURE) — already halted today", gated_lineages)


if __name__ == "__main__":
    main()
