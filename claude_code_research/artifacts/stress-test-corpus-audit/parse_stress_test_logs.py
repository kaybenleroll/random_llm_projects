#!/usr/bin/env python3
"""
Extract Stress-Test Log entries from a corpus of plan-file snapshots and
produce structured tables: pass counts per lineage, per-pass finding/
restatement yield, terminal-verdict distribution, and (optionally) a
before/after comparison across named "ship dates" (e.g. when a process
change landed).

USAGE
-----
  python3 parse_stress_test_logs.py STAGING_DIR [--out-dir OUT_DIR] [--ship-dates FILE.json]

STAGING_DIR must contain one subdirectory per machine/source, each holding
copies of that machine's plan files (`*.md`) — read-only snapshots, not the
live plan directories. Any number of subdirectories works; each becomes a
"machine" label in the output. Example layout:

  staging/
    local/*.md
    remote-host/*.md

Two-machine staging example (adjust host/path to your setup):
  mkdir -p staging/local staging/remote
  cp ~/.claude/plans/*.md staging/local/
  ssh remote-host 'tar -C ~/.claude/plans -cf - .' | tar -C staging/remote -xf -

Single-machine use is just as valid — one subdirectory under STAGING_DIR.

--ship-dates FILE.json (optional): a JSON object mapping a label to a
YYYY-MM-DD date, e.g. {"my_process_change_2026-01-01": "2026-01-01"}. For
each entry, lineages are split into before/after that date and pass-count
stats are compared. Omit this flag to skip that comparison entirely — it
is optional context, not required for the core parse.

OUTPUT (all written into --out-dir, default STAGING_DIR/..):
  blocks.csv      - one row per ### header block within a Stress-Test Log section
  lineages.csv    - one row per plan file that has a Stress-Test Log section
  q_ship_dates.csv - before/after ship-date bucket stats (only if --ship-dates given)
  q_per_pass.csv  - per-pass-number aggregate findings + restatement split
  summary.txt     - human-readable printout of all the above

KNOWN CAVEATS (see README.md for the full explanation of each):
  - Log entry ordering (newest-first vs oldest-first) varies by file — this
    script resolves the "terminal" (most recent) entry by (date, time,
    pass_num) comparison, never by raw file/list position, except as a
    last-resort tiebreak.
  - Arrow-suffix verdicts ("RERUN_NEEDED -> CLEAN") are resolved to the
    token AFTER the arrow — that is the outcome after fold-in.
  - A "take-stock" keyword appearing in a header's prose (not as the
    literal marker line) must not misclassify a genuine findings-bearing
    pass block as a non-pass marker — see EXCLUDE_RE's ordering relative
    to the pass_num/verdict check in classify_and_parse_header().
"""
import argparse
import csv
import glob
import os
import re
import json
import statistics as stats
from collections import defaultdict, Counter

VERDICTS = ["CLEAN", "ACCEPTED", "RERUN_NEEDED", "UNSETTLED", "RESTRUCTURE", "PREMATURE"]
VERDICT_RE = re.compile(r"\b(" + "|".join(VERDICTS) + r")\b")
SUPERSEDED_RE = re.compile(r"(?i)\bsupersed", )

MODEL_RE = re.compile(r"(?i)\b(opus|sonnet|haiku|fable|mythos)\b")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
TIME_RE = re.compile(r"\b(\d{2}:\d{2})\b")

ORDINAL_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
                  "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10}

PASS_NUM_RE = re.compile(r"(?i)\bpass\s*#?\s*(\d+)\b")
RUN_NUM_RE = re.compile(r"(?i)\b(?:run|round)\s+(\d+)\b")
ORD_PASS_RE = re.compile(r"(?i)\b(" + "|".join(ORDINAL_WORDS) + r")\s+pass\b")
ORD_NUM_PASS_RE = re.compile(r"(?i)\b(\d+)(?:st|nd|rd|th)\s+pass\b")
PASSES_RANGE_RE = re.compile(r"(?i)\bpasses?\s+(\d+)\s*[-–]\s*(\d+)\b")

# Header must NOT be treated as a real pass entry if it matches any of these —
# but see classify_and_parse_header(): a header carrying both a parsed pass_num
# AND a verdict token is short-circuited to PASS *before* this filter runs, so
# an incidental keyword match here (e.g. "take-stock triggered") never demotes
# a genuine, findings-bearing pass block.
EXCLUDE_RE = re.compile(
    r"(?i)not a stress-test pass|no pass run|not run,|not run$|not yet run|"
    r"deliberately|deliberate$|counter reset|take-?stock|\boverride\b|"
    r"evidence\b|spike\b|sweep\b|implementation \+ verification|leak-channel|"
    r"new issue candidates|recommended next action|process note|scope decision|"
    r"other decisions taken|post-pass|fold \(option|option [a-d] evidence|"
    r"phase 0 result|final review|resolution \d|take-stock resolution|"
    r"pass 2 resolution"
)

ACCEPTED_STANDALONE_RE = re.compile(r"(?i)^\s*accepted\b")
COUNTER_RESET_RE = re.compile(r"(?i)counter reset")

FINDINGS_RE = re.compile(r"(?i)(\d+)\s+findings?\b(?:\s*\((\d+)\s+before cap\))?")

RESTATEMENT_MARKERS = re.compile(
    r"(?i)\bnot folded\b|\bstill (has|open|describes|omits|false|contradicts|"
    r"understated|unresolved)\b|\bunresolved\b|\bcarried[- ]over\b|\bsecond failed fix\b|"
    r"\bremains unresolved\b|\bsame (defect|issue)\b|\brepeat of\b|\bnot addressed\b|"
    r"\bnot yet resolved\b|\bre-raised\b|\bresurged\b"
)
NEW_MARKERS = re.compile(
    r"(?i)^\s*-\s*(inconsistency|gap|underspecified|showstopper|suggestion|finding)?\s*\(new"
    r"|new, introduced by|newly introduced|introduced by the"
)

FOLD_FAIL_MARKERS = re.compile(
    r"(?i)not folded|only partially|partially applied|still open|still unresolved|"
    r"not (fully )?addressed|remains unresolved|carried[- ]over|not yet folded"
)

SECTION_START_RE = re.compile(r"^## Stress-Test Log\s*$", re.MULTILINE)
NEXT_H2_RE = re.compile(r"^## ", re.MULTILINE)
H3_SPLIT_RE = re.compile(r"^### (.+)$", re.MULTILINE)
ARROW_RE = re.compile(r"→|->")


def extract_section(text):
    m = SECTION_START_RE.search(text)
    if not m:
        return None
    start = m.end()
    rest = text[start:]
    m2 = NEXT_H2_RE.search(rest)
    section = rest[: m2.start()] if m2 else rest
    return section


def extract_verdict(h):
    """Verdict token, arrow-aware: 'RERUN_NEEDED -> ... CLEAN' relabels to CLEAN.

    When the header contains a relabeling arrow, the verdict after the arrow
    wins (it's the outcome after fold-in), falling back to the pre-arrow
    token only when nothing valid follows the arrow.
    """
    am = ARROW_RE.search(h)
    if am:
        after = VERDICT_RE.search(h[am.end():])
        if after:
            return after.group(1)
        before = VERDICT_RE.search(h[:am.start()])
        if before:
            return before.group(1)
        return None
    vm = VERDICT_RE.search(h)
    return vm.group(1) if vm else None


def classify_and_parse_header(header_line):
    """Return dict with type in {PASS, ACCEPTED_STANDALONE, MARKER, MARKER_VERDICT,
    RANGE, UNPARSED} and fields."""
    h = header_line.strip()
    date_m = DATE_RE.search(h)
    date = date_m.group(1) if date_m else None
    time_m = TIME_RE.search(h)
    time = time_m.group(1) if time_m else None
    model_m = MODEL_RE.search(h)
    model = model_m.group(1).lower() if model_m else None

    is_counter_reset = bool(COUNTER_RESET_RE.search(h))
    if is_counter_reset:
        return dict(type="MARKER", date=date, time=time, model=model, pass_num=None,
                    verdict=None, header=h)

    pass_num = None
    scheme = None
    pm = PASS_NUM_RE.search(h)
    if pm:
        pass_num = int(pm.group(1)); scheme = "pass"
    else:
        rm = RUN_NUM_RE.search(h)
        if rm:
            pass_num = int(rm.group(1)); scheme = "run"
        else:
            om = ORD_PASS_RE.search(h)
            if om:
                pass_num = ORDINAL_WORDS[om.group(1).lower()]; scheme = "ordinal-word"
            else:
                onm = ORD_NUM_PASS_RE.search(h)
                if onm:
                    pass_num = int(onm.group(1)); scheme = "ordinal-num"

    verdict = extract_verdict(h)

    if pass_num is not None and verdict is not None:
        return dict(type="PASS", date=date, time=time, model=model, pass_num=pass_num,
                    scheme=scheme, verdict=verdict, superseded=False, header=h)

    if EXCLUDE_RE.search(h):
        if ACCEPTED_STANDALONE_RE.search(h) or re.search(r"(?i)\bACCEPTED\b", h):
            return dict(type="ACCEPTED_STANDALONE", date=date, time=time, model=model,
                        pass_num=None, verdict=verdict or "ACCEPTED", header=h)
        return dict(type="MARKER", date=date, time=time, model=model, pass_num=None,
                    verdict=None, header=h)

    rng = PASSES_RANGE_RE.search(h)
    if rng and pass_num is None:
        return dict(type="RANGE", date=date, time=time, model=model, pass_num=None,
                    range_end=int(rng.group(2)), verdict=verdict, header=h)

    if pass_num is None and date is not None and verdict is not None:
        return dict(type="ACCEPTED_STANDALONE" if verdict == "ACCEPTED" else "MARKER_VERDICT",
                    date=date, time=time, model=model, pass_num=None,
                    verdict=verdict, header=h)

    if pass_num is None:
        return dict(type="UNPARSED", date=date, time=time, model=model, pass_num=None,
                    verdict=None, header=h)

    superseded = bool(SUPERSEDED_RE.search(h))
    return dict(type="PASS", date=date, time=time, model=model, pass_num=pass_num,
                scheme=scheme, verdict=None, superseded=superseded, header=h)


def classify_findings_and_restatement(body):
    fm = FINDINGS_RE.search(body)
    n_findings = int(fm.group(1)) if fm else None
    n_before_cap = int(fm.group(2)) if (fm and fm.group(2)) else None

    bullets = [ln for ln in body.splitlines() if re.match(r"^\s*[-*]\s+", ln)]
    n_bullets = len(bullets)
    n_restatement = sum(1 for b in bullets if RESTATEMENT_MARKERS.search(b))
    n_new_flagged = sum(1 for b in bullets if NEW_MARKERS.search(b))
    return n_findings, n_before_cap, n_bullets, n_restatement, n_new_flagged


def process_file(machine, path):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    section = extract_section(text)
    if section is None:
        return None, []

    headers = list(H3_SPLIT_RE.finditer(section))
    blocks = []
    for i, hm in enumerate(headers):
        header_line = hm.group(1)
        body_start = hm.end()
        body_end = headers[i + 1].start() if i + 1 < len(headers) else len(section)
        body = section[body_start:body_end]
        parsed = classify_and_parse_header(header_line)
        n_findings, n_before_cap, n_bullets, n_restatement, n_new_flagged = \
            classify_findings_and_restatement(body)
        parsed.update(dict(
            machine=machine, file=os.path.basename(path), order_in_section=i,
            n_findings=n_findings, n_before_cap=n_before_cap, n_bullets=n_bullets,
            n_restatement=n_restatement, n_new_flagged=n_new_flagged,
            fold_fail_flag=bool(FOLD_FAIL_MARKERS.search(body)),
        ))
        blocks.append(parsed)
    return section, blocks


def later(a, b):
    """Chronological comparison used both for terminal-block selection and
    for ordering-check purposes: (date, time) decisive whenever they differ;
    then pass_num, decisive only when both sides have one; then file
    position (lower order_in_section wins) as the final, last-resort
    tiebreak — never the primary signal, since the corpus mixes
    newest-first and oldest-first logs."""
    ad, bd = a.get("date") or "", b.get("date") or ""
    if ad != bd:
        return a if ad > bd else b
    at, bt = a.get("time") or "", b.get("time") or ""
    if at != bt:
        return a if at > bt else b
    apn, bpn = a.get("pass_num"), b.get("pass_num")
    if apn is not None and bpn is not None and apn != bpn:
        return a if apn > bpn else b
    return a if a["order_in_section"] < b["order_in_section"] else b


def pick_terminal(blist):
    """Return (terminal_type, terminal_block_or_None) for one lineage's blocks."""
    candidates = []
    for b in blist:
        if b["type"] == "PASS" and b.get("verdict"):
            candidates.append(("PASS", b))
        elif b["type"] == "PASS" and b.get("superseded"):
            candidates.append(("PASS-superseded", b))
        elif b["type"] == "ACCEPTED_STANDALONE":
            candidates.append(("ACCEPTED_STANDALONE", b))
        elif b["type"] == "MARKER_VERDICT" and b.get("verdict"):
            candidates.append(("MARKER_VERDICT", b))
        # MARKER / RANGE / UNPARSED / verdict-less PASS blocks are not candidates

    if not candidates:
        return "ABANDONED_OR_UNPARSED", None

    best_type, best_b = candidates[0]
    for ttype, b in candidates[1:]:
        winner = later(best_b, b)
        if winner is b:
            best_type, best_b = ttype, b
    return best_type, best_b


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("staging_dir", help="Directory containing one subdirectory per machine, each with *.md plan snapshots")
    ap.add_argument("--out-dir", default=None, help="Where to write output CSVs/summary.txt (default: parent of staging_dir)")
    ap.add_argument("--ship-dates", default=None, help="Optional JSON file: {label: 'YYYY-MM-DD', ...} for before/after bucket comparison")
    args = ap.parse_args()

    staging_dir = os.path.abspath(args.staging_dir)
    out_dir = os.path.abspath(args.out_dir) if args.out_dir else os.path.dirname(staging_dir)
    os.makedirs(out_dir, exist_ok=True)

    machines = sorted(d for d in os.listdir(staging_dir) if os.path.isdir(os.path.join(staging_dir, d)))
    if not machines:
        raise SystemExit(f"No subdirectories found under {staging_dir} — expected one per machine/source, each holding *.md files.")

    ship_dates = {}
    if args.ship_dates:
        with open(args.ship_dates, encoding="utf-8") as f:
            ship_dates = json.load(f)

    all_blocks = []
    n_files_total = 0
    n_files_with_section = 0

    for machine in machines:
        d = os.path.join(staging_dir, machine)
        files = sorted(glob.glob(os.path.join(d, "*.md")))
        for path in files:
            n_files_total += 1
            section, blocks = process_file(machine, path)
            if section is None:
                continue
            n_files_with_section += 1
            all_blocks.extend(blocks)

    if n_files_total == 0:
        raise SystemExit(f"No *.md files found under any subdirectory of {staging_dir}.")

    # ---- write blocks.csv ----
    blocks_csv = os.path.join(out_dir, "blocks.csv")
    fieldnames = ["machine", "file", "order_in_section", "type", "date", "time", "model",
                  "pass_num", "scheme", "verdict", "superseded", "range_end",
                  "n_findings", "n_before_cap", "n_bullets", "n_restatement",
                  "n_new_flagged", "fold_fail_flag", "header"]
    with open(blocks_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for b in all_blocks:
            w.writerow(b)

    # ---- build lineage-level table ----
    by_file = defaultdict(list)
    for b in all_blocks:
        by_file[(b["machine"], b["file"])].append(b)

    lineages = []
    for (machine, fname), blist in by_file.items():
        dated = [b for b in blist if b.get("date")]
        first_date = min(b["date"] for b in dated) if dated else None

        pass_nums = [b["pass_num"] for b in blist if b["type"] == "PASS" and b["pass_num"]]
        range_ends = [b["range_end"] for b in blist if b["type"] == "RANGE" and b.get("range_end")]
        max_pass = max(pass_nums + range_ends) if (pass_nums or range_ends) else None
        n_pass_blocks = len([b for b in blist if b["type"] == "PASS"])
        total_pass_estimate = (max_pass if max_pass else 0)
        if not pass_nums and range_ends:
            total_pass_estimate = max(range_ends)

        terminal_type, terminal_block = pick_terminal(blist)
        if terminal_block is None:
            terminal_verdict = None
        elif terminal_type == "PASS-superseded":
            terminal_verdict = "SUPERSEDED"
        else:
            terminal_verdict = terminal_block.get("verdict") or "ACCEPTED"

        lineages.append(dict(
            machine=machine, file=fname, first_date=first_date,
            n_pass_blocks=n_pass_blocks, max_pass_num=max_pass,
            total_pass_estimate=total_pass_estimate,
            terminal_verdict=terminal_verdict, terminal_type=terminal_type,
            n_blocks_total=len(blist),
            n_unparsed=len([b for b in blist if b["type"] == "UNPARSED"]),
        ))

    lineages_csv = os.path.join(out_dir, "lineages.csv")
    with open(lineages_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(lineages[0].keys()))
        w.writeheader()
        for l in lineages:
            w.writerow(l)

    # ================= ship-date buckets (optional) =================
    q1_rows = []
    if ship_dates:
        usable_lineages = [l for l in lineages if l["first_date"] and l["total_pass_estimate"]]
        for label, ship in ship_dates.items():
            before = [l for l in usable_lineages if l["first_date"] < ship]
            after = [l for l in usable_lineages if l["first_date"] >= ship]
            for bucket_name, bucket in [("before", before), ("after", after)]:
                n = len(bucket)
                if n == 0:
                    q1_rows.append(dict(fix=label, bucket=bucket_name, n=0, mean_passes=None,
                                         median_passes=None, pct_gt3=None, pct_gt5=None, pct_gt7=None))
                    continue
                passes = [l["total_pass_estimate"] for l in bucket]
                mean_p = round(stats.mean(passes), 2)
                median_p = stats.median(passes)
                pct_gt3 = round(100 * sum(1 for p in passes if p > 3) / n, 1)
                pct_gt5 = round(100 * sum(1 for p in passes if p > 5) / n, 1)
                pct_gt7 = round(100 * sum(1 for p in passes if p > 7) / n, 1)
                q1_rows.append(dict(fix=label, bucket=bucket_name, n=n, mean_passes=mean_p,
                                     median_passes=median_p, pct_gt3=pct_gt3, pct_gt5=pct_gt5, pct_gt7=pct_gt7))

        q1_csv = os.path.join(out_dir, "q_ship_dates.csv")
        with open(q1_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(q1_rows[0].keys()))
            w.writeheader()
            for r in q1_rows:
                w.writerow(r)

    # ================= pass-count distribution =================
    n_with_log = len(lineages)
    lineages_with_pass_count = [l for l in lineages if l["total_pass_estimate"]]
    n_exceeding_7 = sum(1 for l in lineages_with_pass_count if l["total_pass_estimate"] > 7)
    pct_exceeding_7 = round(100 * n_exceeding_7 / len(lineages_with_pass_count), 2) if lineages_with_pass_count else None

    # ================= per-pass yield =================
    pass_blocks = [b for b in all_blocks if b["type"] == "PASS" and b["pass_num"]]
    by_pass_num = defaultdict(list)
    for b in pass_blocks:
        key = b["pass_num"] if b["pass_num"] < 7 else 7
        by_pass_num[key].append(b)

    q3_rows = []
    for n in range(1, 8):
        blist = by_pass_num.get(n, [])
        if not blist:
            continue
        findings_vals = [b["n_findings"] for b in blist if b["n_findings"] is not None]
        mean_findings = round(stats.mean(findings_vals), 2) if findings_vals else None
        total_bullets = sum(b["n_bullets"] for b in blist)
        total_restatement = sum(b["n_restatement"] for b in blist)
        total_new_flagged = sum(b["n_new_flagged"] for b in blist)
        pct_restatement = round(100 * total_restatement / total_bullets, 1) if total_bullets else None
        q3_rows.append(dict(pass_num=("7+" if n == 7 else n), n_blocks=len(blist),
                             mean_findings=mean_findings, total_bullets_classified=total_bullets,
                             n_bullets_restatement_flagged=total_restatement,
                             n_bullets_new_flagged=total_new_flagged,
                             pct_bullets_restatement_flagged=pct_restatement))

    if q3_rows:
        q3_csv = os.path.join(out_dir, "q_per_pass.csv")
        with open(q3_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(q3_rows[0].keys()))
            w.writeheader()
            for r in q3_rows:
                w.writerow(r)

    # ================= fold-in failure rate =================
    n_transitions = 0
    n_fold_fail = 0
    per_lineage_transition_blocks = defaultdict(list)
    for b in pass_blocks:
        per_lineage_transition_blocks[(b["machine"], b["file"])].append(b)
    for key, blist in per_lineage_transition_blocks.items():
        if len(blist) < 2:
            continue
        min_pass = min(b["pass_num"] for b in blist)
        for b in blist:
            if b["pass_num"] == min_pass:
                continue
            n_transitions += 1
            if b["fold_fail_flag"]:
                n_fold_fail += 1
    pct_fold_fail = round(100 * n_fold_fail / n_transitions, 1) if n_transitions else None

    # ================= verdict distribution =================
    verdict_counts_all_pass_blocks = Counter(b["verdict"] for b in pass_blocks if b["verdict"])
    terminal_counts = Counter(l["terminal_verdict"] or "NONE/ABANDONED" for l in lineages)
    terminal_type_counts = Counter(l["terminal_type"] for l in lineages)

    positive = terminal_counts.get("CLEAN", 0) + terminal_counts.get("ACCEPTED", 0)
    gated = terminal_counts.get("RESTRUCTURE", 0) + terminal_counts.get("UNSETTLED", 0) + terminal_counts.get("PREMATURE", 0)
    abandoned = terminal_counts.get("RERUN_NEEDED", 0) + terminal_counts.get("NONE/ABANDONED", 0) + terminal_counts.get("SUPERSEDED", 0)

    # ================= write summary =================
    summary_path = os.path.join(out_dir, "summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        def p(*a):
            print(*a, file=f)

        p(f"Staging dir: {staging_dir}  Machines: {machines}")
        p(f"Files total: {n_files_total}  Files with Stress-Test Log section: {n_files_with_section}")
        p(f"Total blocks parsed: {len(all_blocks)}  PASS blocks: {len(pass_blocks)}  "
          f"UNPARSED blocks: {sum(1 for b in all_blocks if b['type'] == 'UNPARSED')}")
        p()
        if q1_rows:
            p("=== Ship-date buckets ===")
            for r in q1_rows:
                p(r)
            p()
        p("=== Pass-count distribution ===")
        p(f"lineages with Stress-Test Log: {n_with_log}")
        p(f"lineages with parseable pass count: {len(lineages_with_pass_count)}")
        p(f"n exceeding 7 passes: {n_exceeding_7}  pct: {pct_exceeding_7}")
        p()
        p("=== Per-pass yield ===")
        for r in q3_rows:
            p(r)
        p()
        p("=== Fold-in failure ===")
        p(f"n_transitions={n_transitions} n_fold_fail_flagged={n_fold_fail} pct={pct_fold_fail}")
        p()
        p("=== Verdict distribution ===")
        p("All PASS-block verdicts:", dict(verdict_counts_all_pass_blocks))
        p("Terminal verdict per lineage:", dict(terminal_counts))
        p("Terminal type per lineage:", dict(terminal_type_counts))
        p(f"positive terminal (CLEAN+ACCEPTED)={positive}  gated (RESTRUCTURE+UNSETTLED+PREMATURE)={gated}  "
          f"abandoned/rerun-needed-terminal/superseded={abandoned}  total_lineages={len(lineages)}")

    print(open(summary_path, encoding="utf-8").read())
    print(f"\nWrote: {blocks_csv}\nWrote: {lineages_csv}\nWrote: {summary_path}")


if __name__ == "__main__":
    main()
