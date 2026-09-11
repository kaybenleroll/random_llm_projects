"""Claude Code transcript usage extractor.

Self-containment contract: this file's source is piped verbatim to
`python3 -` on remote hosts (see `run_extractor_local` / `run_extractor_remote`
in `token_cost_report.py`) with nothing else present on that host. It must
import stdlib only (`json`, `os`, `sys`, `collections.defaultdict`,
`datetime`) and must never import a sibling module -- any such import would
work locally (where the sibling file exists on disk) and then fail silently
or loudly on every remote host, since only this file's text is shipped over
SSH, not the rest of the repo.
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
    duplicate_lines_skipped_global = 0
    window_usage_lines_with_msgid = 0
    window_duplicate_lines = 0
    cache_nested_lines = 0
    cache_flat_fallback_lines = 0
    cache_absent_lines = 0
    unrecognized_cache_key_lines = 0
    unrecognized_cache_keys_seen = set()

    seen_msg_ids = set()
    buckets = defaultdict(lambda: {
        "input": 0.0, "cache_write_5m": 0.0, "cache_write_1h": 0.0,
        "cache_read": 0.0, "output": 0.0, "lines": 0,
    })
    # msg.id -> per-line token contribution, for every line that actually
    # landed in a bucket (in-window, survived per-host dedup). Consumed only
    # by the parent's cross-host dedup pass at combine time -- never used
    # for anything within this host's own extraction.
    msgid_contributions = {}

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

                    if tier is None:
                        if in_window:
                            lines_skipped_unknown_model += 1
                        continue

                    usage_lines_total += 1
                    mid = msg.get("id")
                    is_dup = False
                    if mid:
                        if mid in seen_msg_ids:
                            is_dup = True
                        else:
                            seen_msg_ids.add(mid)
                    else:
                        if in_window:
                            lines_missing_message_id += 1

                    if in_window and mid:
                        window_usage_lines_with_msgid += 1
                        if is_dup:
                            window_duplicate_lines += 1

                    if is_dup:
                        duplicate_lines_skipped_global += 1
                        continue

                    if not in_window:
                        continue

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
                        has_unrecognized = False
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
                                has_unrecognized = True
                                unrecognized_cache_keys_seen.add(k)
                        cache_nested_lines += 1
                        if has_unrecognized:
                            unrecognized_cache_key_lines += 1
                    elif flat_cw:
                        cw_1h = flat_cw
                        cache_flat_fallback_lines += 1
                    else:
                        cache_absent_lines += 1

                    day = d.date().isoformat()
                    key = (proj, day, model_id)
                    b = buckets[key]
                    b["input"] += input_tokens
                    b["cache_write_5m"] += cw_5m
                    b["cache_write_1h"] += cw_1h
                    b["cache_read"] += cache_read
                    b["output"] += output_tokens
                    b["lines"] += 1

                    if mid:
                        msgid_contributions[mid] = {
                            "project": proj, "day": day, "model": model_id,
                            "input": input_tokens, "cache_write_5m": cw_5m,
                            "cache_write_1h": cw_1h, "cache_read": cache_read,
                            "output": output_tokens,
                        }
        except Exception as e:
            sys.stderr.write("ERROR reading %s: %s\n" % (fpath, e))

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
            "duplicate_lines_skipped_global": duplicate_lines_skipped_global,
            "window_usage_lines_with_msgid": window_usage_lines_with_msgid,
            "window_duplicate_lines": window_duplicate_lines,
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
