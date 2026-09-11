#!/usr/bin/env python3
"""Measure message.id duplication in a Claude Code transcript corpus.

This is a read-only scan, independent of `token_cost_report.py`'s own
extraction pipeline, written to answer one question: how much does
`token_cost_report.py`'s keep-first-by-message.id dedup policy undercount
`output_tokens` relative to keep-max, and does the divergence between
duplicate occurrences of one message.id ever touch a priced field other
than `output_tokens`?

It deliberately replicates `token_cost_report.py`'s embedded extractor
(`_EXTRACTOR_SRC`)'s own line-eligibility filters exactly, so this script
measures the same population that `extractor.scan()` actually prices, not
a related-but-different population:

    1. `message` must be a dict.
    2. `message.usage` must be a dict.
    3. `timestamp` (falling back to `createdAt`) must parse.
    4. `tier_of(model)` (from `message.model` or the top-level `model` key)
       must be non-None.

A line that fails any of those is not a "usage line" for this script's
purposes, exactly as it is not one for the extractor's `usage_lines_total`
counter.

Usable both as a CLI (prints JSON to stdout) and as a library
(`measure(root) -> dict`) -- the latter is what
`test_token_cost_report.py`'s `TestRealCorpusInvariants` is expected to
import directly, per the plan that introduced this script (see
`claude_code_research/artifacts/token-cost-analysis/README.md`, "Dedup
policy").

Usage:
    measure_dup_msgids.py [ROOT]

    ROOT defaults to ~/.claude/projects. Prints one JSON object to stdout.
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone


# --------------------------------------------------------------------------
# Filters and per-line field extraction -- kept in lockstep with
# token_cost_report.py's _EXTRACTOR_SRC. If that embedded extractor's
# eligibility filters or cache-field handling ever change, this file must
# change with it, or this script silently measures the wrong population.
# --------------------------------------------------------------------------

def parse_ts(ts):
    if not ts:
        return None
    try:
        ts = ts.replace("Z", "+00:00")
        d = datetime.fromisoformat(ts)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None


def tier_of(model_id):
    if not model_id:
        return None
    m = model_id.lower()
    for t in ("sonnet", "opus", "haiku", "fable"):
        if t in m:
            return t
    return None


def _priced_fields(usage):
    """Returns (input_tokens, cache_read, output_tokens, cw_5m, cw_1h) for
    one usage dict, using the identical nested-TTL-split / flat-fallback /
    absent logic as _EXTRACTOR_SRC. cw_5m/cw_1h are the two components of
    the single "cache write" priced dimension (nested `cache_creation` dict
    when present and non-zero, else the flat `cache_creation_input_tokens`
    fallback, else absent/zero)."""
    input_tokens = usage.get("input_tokens", 0) or 0
    cache_read = usage.get("cache_read_input_tokens", 0) or 0
    output_tokens = usage.get("output_tokens", 0) or 0

    flat_cw = usage.get("cache_creation_input_tokens", 0) or 0
    nested = usage.get("cache_creation")
    cw_5m = 0.0
    cw_1h = 0.0
    nested_nonzero = False
    if isinstance(nested, dict):
        nested_nonzero = any(
            (v or 0) for v in nested.values() if isinstance(v, (int, float))
        )
    if nested_nonzero:
        for k, v in nested.items():
            if not isinstance(v, (int, float)):
                continue
            if k == "ephemeral_5m_input_tokens":
                cw_5m += v
            elif k == "ephemeral_1h_input_tokens":
                cw_1h += v
            else:
                # unrecognized TTL bucket: extractor sums it at the 1h rate.
                cw_1h += v
    elif flat_cw:
        cw_1h = flat_cw

    return input_tokens, cache_read, output_tokens, cw_5m, cw_1h


def _walk_files(root):
    """Same walk + sort order as _EXTRACTOR_SRC: os.walk, filter *.jsonl,
    sort by full path for a deterministic first-occurrence scan order."""
    all_files = []
    if os.path.isdir(root):
        for dirpath, dirnames, filenames in os.walk(root):
            for fn in filenames:
                if fn.endswith(".jsonl"):
                    all_files.append(os.path.join(dirpath, fn))
    all_files.sort()
    return all_files


def _is_subagent_path(fpath):
    return "/subagents/" in fpath.replace(os.sep, "/")


# --------------------------------------------------------------------------
# Core measurement
# --------------------------------------------------------------------------

def measure(root):
    """Scans `root` (a ~/.claude/projects-shaped tree) and returns a dict of
    corpus-wide duplicate-message.id statistics. See module docstring for
    the eligibility filters applied.
    """
    root = os.path.expanduser(root)
    files = _walk_files(root)

    usage_lines_total = 0
    lines_missing_message_id = 0

    # msg.id -> list of occurrence dicts, in scan order (path-sorted, then
    # in-file line order -- matches the extractor's first-occurrence order).
    groups = defaultdict(list)

    for fpath in files:
        is_subagent = _is_subagent_path(fpath)
        try:
            with open(fpath, "r", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    msg = obj.get("message")
                    if not isinstance(msg, dict):
                        continue
                    usage = msg.get("usage")
                    if not isinstance(usage, dict):
                        continue
                    ts = obj.get("timestamp") or obj.get("createdAt")
                    d = parse_ts(ts)
                    if d is None:
                        continue
                    model_id = msg.get("model") or obj.get("model")
                    tier = tier_of(model_id)
                    if tier is None:
                        continue

                    usage_lines_total += 1

                    mid = msg.get("id")
                    if not mid:
                        lines_missing_message_id += 1
                        continue

                    input_tokens, cache_read, output_tokens, cw_5m, cw_1h = _priced_fields(usage)
                    day = d.date().isoformat()
                    groups[mid].append({
                        "day": day,
                        "ts": d,
                        "input": input_tokens,
                        "cache_read": cache_read,
                        "output": output_tokens,
                        "cw_5m": cw_5m,
                        "cw_1h": cw_1h,
                        "is_subagent": is_subagent,
                    })
        except Exception as e:
            sys.stderr.write("ERROR reading %s: %s\n" % (fpath, e))

    return _summarize(files, usage_lines_total, lines_missing_message_id, groups)


def _select_winner(occs):
    """Mirrors token_cost_report.py's planned Step 4 winner-selection:
    `if rec["output"] >= prev["output"]: winner = rec` walked in scan
    order, so ties resolve to the last-seen occurrence."""
    winner = None
    for occ in occs:
        if winner is None or occ["output"] >= winner["output"]:
            winner = occ
    return winner


def _summarize(files, usage_lines_total, lines_missing_message_id, groups):
    distinct_message_ids = len(groups)

    duplicate_groups = 0
    identical_groups = 0          # all 5 priced fields (incl. output) byte-identical across every occurrence
    divergent_groups = 0          # differ in at least one of those 5 fields (duplicate_groups - identical_groups)
    non_output_divergent_groups = 0  # differ in one of the 4 NON-output priced fields specifically -- expected 0
    keep_max_upgrades = 0         # divergent-in-a-way-that-changes-output groups (winner.output > first.output)
    output_tokens_gained_by_keep_max = 0
    day_straddle_count = 0
    order_disagreement_count = 0  # winner (max-output) isn't the last occurrence by timestamp

    # Overall totals across ALL ids (duplicate or not) plus all no-msgid lines.
    total_output_keep_first = 0
    total_output_keep_max = 0
    total_output_no_dedup = 0

    duplicate_lines_skipped_global = 0  # occurrences beyond the first, per id (mirrors extractor's counter)

    by_type = {
        "subagent": {"keep_first": 0, "keep_max": 0},
        "main_session": {"keep_first": 0, "keep_max": 0},
    }
    mixed_type_groups = 0

    for mid, occs in groups.items():
        first = occs[0]
        winner = _select_winner(occs)

        total_output_no_dedup += sum(o["output"] for o in occs)
        total_output_keep_first += first["output"]
        total_output_keep_max += winner["output"]

        types_seen = {o["is_subagent"] for o in occs}
        if len(types_seen) > 1:
            mixed_type_groups += 1
            group_type = "subagent" if winner["is_subagent"] else "main_session"
        else:
            group_type = "subagent" if types_seen.pop() else "main_session"
        by_type[group_type]["keep_first"] += first["output"]
        by_type[group_type]["keep_max"] += winner["output"]

        if len(occs) > 1:
            duplicate_groups += 1
            duplicate_lines_skipped_global += len(occs) - 1

            all5_match = all(
                (o["input"], o["cache_read"], o["cw_5m"], o["cw_1h"], o["output"])
                == (first["input"], first["cache_read"], first["cw_5m"], first["cw_1h"], first["output"])
                for o in occs
            )
            if all5_match:
                identical_groups += 1
            else:
                divergent_groups += 1

            non_output_match = all(
                (o["input"], o["cache_read"], o["cw_5m"], o["cw_1h"])
                == (first["input"], first["cache_read"], first["cw_5m"], first["cw_1h"])
                for o in occs
            )
            if not non_output_match:
                non_output_divergent_groups += 1

            if winner["output"] > first["output"]:
                keep_max_upgrades += 1
                output_tokens_gained_by_keep_max += winner["output"] - first["output"]

            if winner["day"] != first["day"]:
                day_straddle_count += 1

            last_by_ts = max(occs, key=lambda o: o["ts"])
            if last_by_ts["output"] != winner["output"]:
                order_disagreement_count += 1

    def ratio(a, b):
        return (a / b) if b else None

    return {
        "meta": {
            "files_scanned": len(files),
        },
        "usage_lines_total": usage_lines_total,
        "lines_missing_message_id": lines_missing_message_id,
        "distinct_message_ids": distinct_message_ids,
        "duplicate_message_id_groups": duplicate_groups,
        "identical_groups": identical_groups,
        "divergent_groups": divergent_groups,
        "non_output_divergent_groups": non_output_divergent_groups,
        "duplicate_lines_skipped_global": duplicate_lines_skipped_global,
        "keep_max_upgrades": keep_max_upgrades,
        "output_tokens_gained_by_keep_max": output_tokens_gained_by_keep_max,
        "day_straddle_count": day_straddle_count,
        "order_disagreement_count": order_disagreement_count,
        "mixed_type_groups": mixed_type_groups,
        "totals": {
            "keep_first_output_tokens": total_output_keep_first,
            "keep_max_output_tokens": total_output_keep_max,
            "no_dedup_output_tokens": total_output_no_dedup,
            "ratio_keep_max_over_keep_first": ratio(total_output_keep_max, total_output_keep_first),
            "ratio_no_dedup_over_keep_first": ratio(total_output_no_dedup, total_output_keep_first),
        },
        "by_transcript_type": {
            "subagent": {
                "keep_first_output_tokens": by_type["subagent"]["keep_first"],
                "keep_max_output_tokens": by_type["subagent"]["keep_max"],
                "ratio_keep_max_over_keep_first": ratio(
                    by_type["subagent"]["keep_max"], by_type["subagent"]["keep_first"]
                ),
            },
            "main_session": {
                "keep_first_output_tokens": by_type["main_session"]["keep_first"],
                "keep_max_output_tokens": by_type["main_session"]["keep_max"],
                "ratio_keep_max_over_keep_first": ratio(
                    by_type["main_session"]["keep_max"], by_type["main_session"]["keep_first"]
                ),
            },
        },
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("root", nargs="?", default="~/.claude/projects", help="Corpus root to scan (default: ~/.claude/projects)")
    args = p.parse_args(argv)

    result = measure(args.root)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
