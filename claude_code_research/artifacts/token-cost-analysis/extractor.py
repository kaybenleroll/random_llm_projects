"""Claude Code transcript usage extractor.

Self-containment contract: this file's source is piped verbatim to
`python3 -` on remote hosts (see `run_extractor_local` / `run_extractor_remote`
in `token_cost_report.py`) with nothing else present on that host. It must
import stdlib only (`json`, `os`, `sys`, `collections.defaultdict`,
`datetime`) and must never import a sibling module -- any such import would
work locally (where the sibling file exists on disk) and then fail silently
or loudly on every remote host, since only this file's text is shipped over
SSH, not the rest of the repo.

DEDUP POLICY (issue #101): message.id deduplication keeps the occurrence
with the MAX output_tokens per id ("keep-max"), not the first-seen
occurrence ("keep-first"). Streamed generation (chiefly in subagent
transcripts) writes an early line carrying a stub output_tokens count and a
later line carrying the settled count; keep-first was picking the stub,
undercounting output_tokens corpus-wide by ~36.5% (a much smaller ~4% dollar
effect, since output_tokens is a minority of priced cost). Selection is of
the WHOLE winning record, never a per-field max across occurrences.

Because the winner is not always the first occurrence, bucketing (window
membership, day-bucket assignment) is deferred to a second pass over the
winning records, keyed on each winner's own timestamp -- not the first
occurrence's. See scan()'s two-pass structure below.
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone


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


def _contribution(obj, msg, usage, proj, d, model_id, has_msgid):
    """Builds one candidate contribution record for a single usage line.
    Holds the same usage-extraction logic the extractor has always had
    (nested cache_creation TTL split, unknown-TTL-summed-at-1h-rate, flat
    fallback, absent) but *returns* the result instead of mutating buckets
    directly -- bucketing happens later, once dedup has picked a winner.

    Underscore-prefixed keys (_ts, _cache_shape, _cache_unrecognized,
    _unrecognized_keys) are internal bookkeeping for the second pass and
    are never emitted in scan()'s JSON output.
    """
    input_tokens = usage.get("input_tokens", 0) or 0
    cache_read = usage.get("cache_read_input_tokens", 0) or 0
    output_tokens = usage.get("output_tokens", 0) or 0

    flat_cw = usage.get("cache_creation_input_tokens", 0) or 0
    nested = usage.get("cache_creation")
    cw_5m = 0.0
    cw_1h = 0.0
    nested_nonzero = False
    unrecognized_keys = set()
    if isinstance(nested, dict):
        nested_nonzero = any(
            (v or 0) for v in nested.values() if isinstance(v, (int, float))
        )
    if nested_nonzero:
        shape = "nested"
        for k, v in nested.items():
            if not isinstance(v, (int, float)):
                continue
            if k == "ephemeral_5m_input_tokens":
                cw_5m += v
            elif k == "ephemeral_1h_input_tokens":
                cw_1h += v
            else:
                # unrecognized TTL bucket: sum it in (don't drop it),
                # price conservatively at the 1h rate, and flag it.
                cw_1h += v
                unrecognized_keys.add(k)
    elif flat_cw:
        cw_1h = flat_cw
        shape = "flat_fallback"
    else:
        shape = "absent"

    day = d.date().isoformat()

    return {
        "project": proj,
        "day": day,
        "model": model_id,
        "input": input_tokens,
        "cache_write_5m": cw_5m,
        "cache_write_1h": cw_1h,
        "cache_read": cache_read,
        "output": output_tokens,
        "has_msgid": has_msgid,
        "_ts": d,
        "_cache_shape": shape,
        "_cache_unrecognized": bool(unrecognized_keys),
        "_unrecognized_keys": unrecognized_keys,
    }


def scan(root, since_arg, until_arg):
    if since_arg:
        y, mo, da = [int(x) for x in since_arg.split("-")]
        SINCE = datetime(y, mo, da, 0, 0, 0, tzinfo=timezone.utc)
    else:
        SINCE = datetime(2000, 1, 1, tzinfo=timezone.utc)
    if until_arg:
        y, mo, da = [int(x) for x in until_arg.split("-")]
        UNTIL = datetime(y, mo, da, 23, 59, 59, 999999, tzinfo=timezone.utc)
    else:
        UNTIL = datetime(2100, 1, 1, tzinfo=timezone.utc)

    ROOT = root

    all_files = []
    if os.path.isdir(ROOT):
        for dirpath, dirnames, filenames in os.walk(ROOT):
            rel = os.path.relpath(dirpath, ROOT)
            proj = "(root)" if rel == "." else rel.split(os.sep)[0]
            for fn in filenames:
                if fn.endswith(".jsonl"):
                    all_files.append((os.path.join(dirpath, fn), proj))
    all_files.sort(key=lambda x: x[0])  # deterministic first-occurrence order

    lines_scanned = 0
    malformed_lines = 0
    usage_lines_total = 0
    lines_skipped_unknown_model = 0
    lines_missing_message_id = 0
    lines_missing_message_id_corpus_wide = 0
    duplicate_lines_skipped_global = 0
    window_usage_lines_with_msgid = 0
    window_duplicate_lines = 0
    keep_max_upgrades = 0
    output_tokens_gained_by_keep_max = 0

    winners = {}      # dedup_key -> winning contribution record (whole record)
    first_seen = {}   # dedup_key -> (day, in_window, output) of FIRST occurrence
    nomsgid_counter = 0

    # ---- pass 1: scan every eligible line, resolve the keep-max winner per
    # dedup key. Bucketing is deferred to pass 2, below, because the winner
    # for a key is not known until the whole corpus has been scanned. ----
    for fpath, proj in all_files:
        try:
            with open(fpath, "r", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    lines_scanned += 1
                    try:
                        obj = json.loads(line)
                    except Exception:
                        malformed_lines += 1
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
                    in_window = SINCE <= d <= UNTIL

                    # Unknown-tier lines are excluded from usage_lines_total
                    # (the pre-dedup denominator) -- this guard must stay
                    # exactly here, before that increment.
                    if tier is None:
                        if in_window:
                            lines_skipped_unknown_model += 1
                        continue

                    usage_lines_total += 1
                    mid = msg.get("id")
                    if mid:
                        key = mid
                    else:
                        nomsgid_counter += 1
                        key = "\x00nomsgid\x00%d" % nomsgid_counter  # never collapses
                        lines_missing_message_id_corpus_wide += 1
                        if in_window:
                            lines_missing_message_id += 1

                    rec = _contribution(obj, msg, usage, proj, d, model_id, bool(mid))
                    prev = winners.get(key)
                    is_dup = prev is not None

                    # window_usage_lines_with_msgid / window_duplicate_lines
                    # stay deliberately first-occurrence-based (unchanged
                    # semantics from before this restructure) so the
                    # existing dedup_ratio guardrail keeps working.
                    if in_window and mid:
                        window_usage_lines_with_msgid += 1
                        if is_dup:
                            window_duplicate_lines += 1

                    if prev is None:
                        winners[key] = rec
                        first_seen[key] = (rec["day"], in_window, rec["output"])
                    else:
                        duplicate_lines_skipped_global += 1
                        if rec["output"] >= prev["output"]:            # ties -> last seen wins
                            if rec["output"] > prev["output"]:
                                keep_max_upgrades += 1
                                output_tokens_gained_by_keep_max += rec["output"] - prev["output"]
                            winners[key] = rec                         # WHOLE record
        except Exception as e:
            sys.stderr.write("ERROR reading %s: %s\n" % (fpath, e))

    # ---- pass 2: apply the window filter to each WINNER's own timestamp,
    # bucket the survivors, and tally the boundary/day-straddle counters
    # that make the deferred-bucketing edge cases visible. ----
    distinct_msgids_total = len(winners)
    window_msgids_kept = 0
    msgids_boundary_rescued = 0
    msgids_boundary_dropped = 0
    msgids_day_straddled = 0
    cache_nested_lines = 0
    cache_flat_fallback_lines = 0
    cache_absent_lines = 0
    unrecognized_cache_key_lines = 0
    unrecognized_cache_keys_seen = set()

    buckets = defaultdict(lambda: {
        "input": 0.0, "cache_write_5m": 0.0, "cache_write_1h": 0.0,
        "cache_read": 0.0, "output": 0.0, "lines": 0,
    })
    # msg.id -> per-line token contribution, for every winning line that
    # actually landed in a bucket (in-window by the winner's own
    # timestamp). Consumed only by the parent's cross-host dedup pass at
    # combine time -- never used for anything within this host's own
    # extraction.
    msgid_contributions = {}

    for key, rec in winners.items():
        fs_day, fs_in_window, _fs_output = first_seen[key]
        winner_in_window = SINCE <= rec["_ts"] <= UNTIL

        if winner_in_window and not fs_in_window:
            # First occurrence was outside the window, the winner is
            # inside it -- the old dedup-before-window-filter caveat,
            # now fixed: this message would have been silently lost
            # before this restructure.
            msgids_boundary_rescued += 1
        elif fs_in_window and not winner_in_window:
            # New opposite edge case introduced by deferred bucketing:
            # first occurrence was inside the window, but the winner
            # (the settled value) falls outside it -- this message is
            # now dropped entirely, whereas keep-first would have at
            # least partially counted it (at the stub value).
            msgids_boundary_dropped += 1

        if rec["day"] != fs_day:
            msgids_day_straddled += 1

        if not winner_in_window:
            continue

        window_msgids_kept += 1

        shape = rec["_cache_shape"]
        if shape == "nested":
            cache_nested_lines += 1
            if rec["_cache_unrecognized"]:
                unrecognized_cache_key_lines += 1
                unrecognized_cache_keys_seen.update(rec["_unrecognized_keys"])
        elif shape == "flat_fallback":
            cache_flat_fallback_lines += 1
        else:
            cache_absent_lines += 1

        bkey = (rec["project"], rec["day"], rec["model"])
        b = buckets[bkey]
        b["input"] += rec["input"]
        b["cache_write_5m"] += rec["cache_write_5m"]
        b["cache_write_1h"] += rec["cache_write_1h"]
        b["cache_read"] += rec["cache_read"]
        b["output"] += rec["output"]
        b["lines"] += 1

        if rec["has_msgid"]:
            msgid_contributions[key] = {
                "project": rec["project"], "day": rec["day"], "model": rec["model"],
                "input": rec["input"], "cache_write_5m": rec["cache_write_5m"],
                "cache_write_1h": rec["cache_write_1h"], "cache_read": rec["cache_read"],
                "output": rec["output"],
            }

    bucket_list = []
    for (proj, day, model_id), b in buckets.items():
        rec = {"project": proj, "day": day, "model": model_id}
        rec.update(b)
        bucket_list.append(rec)

    out = {
        "meta": {
            "files_scanned": len(all_files),
            "lines_scanned": lines_scanned,
            "malformed_lines": malformed_lines,
            "usage_lines_total": usage_lines_total,
            "lines_skipped_unknown_model": lines_skipped_unknown_model,
            "lines_missing_message_id": lines_missing_message_id,
            "lines_missing_message_id_corpus_wide": lines_missing_message_id_corpus_wide,
            "duplicate_lines_skipped_global": duplicate_lines_skipped_global,
            "distinct_msgids_total": distinct_msgids_total,
            "window_usage_lines_with_msgid": window_usage_lines_with_msgid,
            "window_duplicate_lines": window_duplicate_lines,
            "window_msgids_kept": window_msgids_kept,
            "keep_max_upgrades": keep_max_upgrades,
            "output_tokens_gained_by_keep_max": output_tokens_gained_by_keep_max,
            "msgids_boundary_rescued": msgids_boundary_rescued,
            "msgids_boundary_dropped": msgids_boundary_dropped,
            "msgids_day_straddled": msgids_day_straddled,
            "cache_nested_lines": cache_nested_lines,
            "cache_flat_fallback_lines": cache_flat_fallback_lines,
            "cache_absent_lines": cache_absent_lines,
            "unrecognized_cache_key_lines": unrecognized_cache_key_lines,
            "unrecognized_cache_keys_seen": sorted(unrecognized_cache_keys_seen),
            "since": since_arg or None,
            "until": until_arg or None,
        },
        "buckets": bucket_list,
        "msgid_contributions": msgid_contributions,
    }
    return out


def main():
    args = sys.argv[1:]
    since_arg = args[0] if len(args) > 0 else ""
    until_arg = args[1] if len(args) > 1 else ""

    root = os.environ.get("TOKEN_COST_ROOT", os.path.expanduser("~/.claude/projects"))
    out = scan(root, since_arg, until_arg)
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    main()
