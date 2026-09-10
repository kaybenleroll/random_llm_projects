#!/usr/bin/env python3
"""Unified multi-host Claude Code token-cost report.

Walks each named host's ~/.claude/projects/**/*.jsonl transcripts (locally,
or over SSH for remote hosts), dedupes usage lines by message.id, prices
tokens by exact model ID (falling back to tier pricing for anything not yet
in the pricing table), and prints a combined per-project cost report.

Usage:
    token_cost_report.py --hosts local,s3rbase[,newhost...] \\
        [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--out PATH] [--allow-partial]

--hosts is required: comma-separated SSH aliases (must already exist in
~/.ssh/config for remote hosts). "local" means "run the extractor directly
on this machine, no SSH."

--since / --until are UTC dates (inclusive), matching how Claude Code
transcript timestamps are stored. If omitted, the tool covers full
available history. ccusage's default daily bucketing is LOCAL-date, not
UTC -- a few-percent gap against `ccusage daily` for the same nominal
window is expected from that alone, on top of the dedup tradeoff below.

KNOWN LIMITATION -- dedup-before-window-filter: message.id deduplication
happens globally across each host's entire transcript corpus, BEFORE the
--since/--until window is applied. This is deliberate (it matches the
corpus-wide ground truth this tool was validated against), but it means a
message whose first occurrence falls outside the requested window will
NOT be counted even if a duplicate of it falls inside the window. This can
under-count totals near a window boundary. Widen the window if you need an
exact boundary-accurate figure.

CROSS-HOST DEDUP: on top of each host's own per-host message.id dedup, the
combine step also dedupes message.id globally across all requested hosts --
if the same project directory is replicated across two hosts (sync, backup),
a message.id seen in more than one host's output is counted only once
(alphabetically-first host, by name, keeps it). The stdout summary and JSON
report's "cross_host_dedup" section state how many duplicates were found,
their estimated $ value, and which host(s) they were dropped from.

Host-failure policy: if any named host fails (SSH failure, non-zero exit,
timeout, or unparseable/contaminated stdout), the tool prints which host(s)
failed and exits non-zero WITHOUT writing a combined report, unless
--allow-partial is passed, in which case the report is written with a
top-level "partial": true marker and the failed hosts listed.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

# --------------------------------------------------------------------------
# Pricing tables
# --------------------------------------------------------------------------

# Normalize before lookup: strip a trailing -YYYYMMDD date suffix, if present.
def normalize_model_id(model_id: str) -> str:
    return re.sub(r"-\d{8}$", "", model_id or "")


MODEL_PRICING = {
    # model_id (post-normalization): (input, output, cache_write_1h, cache_write_5m, cache_read) -- $/MTok
    "claude-sonnet-5":   (2.0, 10.0, 4.0, 2.5, 0.20),
    "claude-sonnet-4-6": (3.0, 15.0, 6.0, 3.75, 0.30),
    "claude-opus-5":     (5.0, 25.0, 10.0, 6.25, 0.50),
    "claude-opus-4-8":   (5.0, 25.0, 10.0, 6.25, 0.50),
    "claude-haiku-4-5":  (1.0, 5.0, 2.0, 1.25, 0.10),
    "claude-fable-5":    (10.0, 50.0, 20.0, 12.5, 0.25),   # confirmed special cache-read rate
    "claude-fable-5-1":  (10.0, 50.0, 20.0, 12.5, 0.25),   # same, confirmed special rate
    # extend with any other exact (normalized) model IDs observed in the data -- the tool
    # prints every distinct normalized model ID it saw, with line counts, in its summary,
    # specifically so a gap in this table is visible at a glance rather than silently
    # absorbed by the fallback below.
}
TIER_FALLBACK = {
    "sonnet": (2.0, 10.0, 4.0, 2.5, 0.20),
    "opus":   (5.0, 25.0, 10.0, 6.25, 0.50),
    "haiku":  (1.0, 5.0, 2.0, 1.25, 0.10),
    "fable":  (10.0, 50.0, 20.0, 12.5, 0.25),
}


def tier_of(model_id):
    if not model_id:
        return None
    m = model_id.lower()
    for t in ("sonnet", "opus", "haiku", "fable"):
        if t in m:
            return t
    return None


def resolve_pricing(model_id):
    """Returns (pricing_tuple_or_None, path, normalized_id).
    path is "exact", "tier_fallback", or "unresolved" (the last should not
    occur in practice -- the extractor already drops lines whose model
    matches no tier substring at all)."""
    norm = normalize_model_id(model_id)
    if norm in MODEL_PRICING:
        return MODEL_PRICING[norm], "exact", norm
    tier = tier_of(model_id)
    if tier and tier in TIER_FALLBACK:
        return TIER_FALLBACK[tier], "tier_fallback", norm
    return None, "unresolved", norm


def price_bucket(rec):
    """rec: dict with input/output/cache_write_1h/cache_write_5m/cache_read raw
    token counts and a "model" field. Returns (cost_usd, pricing_path, normalized_model_id)."""
    pricing, path, norm = resolve_pricing(rec["model"])
    if pricing is None:
        return 0.0, path, norm
    p_in, p_out, p_cw1h, p_cw5m, p_cread = pricing
    cost = (
        rec["input"] / 1e6 * p_in
        + rec["output"] / 1e6 * p_out
        + rec["cache_write_1h"] / 1e6 * p_cw1h
        + rec["cache_write_5m"] / 1e6 * p_cw5m
        + rec["cache_read"] / 1e6 * p_cread
    )
    return cost, path, norm


# --------------------------------------------------------------------------
# Embedded extractor -- executed identically on every host (local subprocess
# or over SSH), never string-interpolated. since/until reach it as argv.
# --------------------------------------------------------------------------

_EXTRACTOR_SRC = r"""
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


def main():
    args = sys.argv[1:]
    since_arg = args[0] if len(args) > 0 else ""
    until_arg = args[1] if len(args) > 1 else ""

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

    ROOT = os.path.expanduser("~/.claude/projects")

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
    sys.stdout.write(json.dumps(out))


main()
"""


# --------------------------------------------------------------------------
# Running the extractor
# --------------------------------------------------------------------------

LOCAL_TIMEOUT = 600
REMOTE_TIMEOUT = 120


def _extract_json(stdout_text, host_label):
    """Stdout-contamination-safe JSON parse: scan for the first '{' and the
    last '}' and parse that substring. Never silently treat unparseable
    output as zero usage -- fail loudly naming the host and a snippet."""
    first = stdout_text.find("{")
    last = stdout_text.rfind("}")
    if first == -1 or last == -1 or last < first:
        raise RuntimeError(
            "host %r: no JSON object found in extractor stdout. First 200 bytes: %r"
            % (host_label, stdout_text[:200])
        )
    candidate = stdout_text[first : last + 1]
    try:
        return json.loads(candidate)
    except Exception as e:
        raise RuntimeError(
            "host %r: failed to parse extractor JSON (%s). First 200 bytes of stdout: %r"
            % (host_label, e, stdout_text[:200])
        )


def run_extractor_local(since_arg, until_arg):
    proc = subprocess.run(
        [sys.executable, "-", since_arg, until_arg],
        input=_EXTRACTOR_SRC,
        capture_output=True,
        text=True,
        timeout=LOCAL_TIMEOUT,
    )
    return proc


def run_extractor_remote(host, since_arg, until_arg):
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, "python3", "-", since_arg, until_arg],
        input=_EXTRACTOR_SRC,
        capture_output=True,
        text=True,
        timeout=REMOTE_TIMEOUT,
    )
    return proc


def run_host(host, since_arg, until_arg):
    """Returns (ok, result_dict_or_None, failure_reason_or_None)."""
    try:
        if host == "local":
            proc = run_extractor_local(since_arg, until_arg)
        else:
            proc = run_extractor_remote(host, since_arg, until_arg)
    except subprocess.TimeoutExpired:
        return False, None, "timeout"
    except Exception as e:
        return False, None, "subprocess error: %s" % e

    if proc.returncode != 0:
        stderr_snip = (proc.stderr or "")[:300]
        return False, None, "non-zero exit %d, stderr: %r" % (proc.returncode, stderr_snip)

    try:
        parsed = _extract_json(proc.stdout or "", host)
    except RuntimeError as e:
        return False, None, str(e)

    return True, parsed, None


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------

def iso_week_of(day_iso):
    d = date.fromisoformat(day_iso)
    y, w, _ = d.isocalendar()
    return "%d-W%02d" % (y, w)


_LEDGER_FIELDS = ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")


def compute_cross_host_dedup(host_results):
    """Cross-host duplicate detection, on top of (not replacing) each host's
    own per-host message.id dedup. If the same project directory is
    replicated across hosts (sync/backup), the *same* message.id shows up in
    more than one host's msgid_contributions ledger; per-host dedup alone
    cannot see this since each host only tracks its own seen_msg_ids.

    Hosts are walked in sorted-name order for determinism: the
    alphabetically-first host to report a given message.id "keeps" it, every
    later host's copy is a cross-host duplicate and gets dropped from that
    host's bucket totals before pricing.

    Returns (subtract, line_counts, events):
      subtract:    {(host, project, day, model): {field: tokens_to_subtract}}
      line_counts: {(host, project, day, model): n_duplicate_lines}
      events:      [{"message_id","kept_host","dropped_host","project","day",
                      "model", <ledger token fields>}, ...] one per duplicate
                     found, in walk order -- kept as full detail for audit,
                     not just a count, since it's the only way to see *which*
                     project/day was double-counted and by how much.
    """
    seen_by = {}  # message_id -> host that keeps it
    subtract = defaultdict(lambda: defaultdict(float))
    line_counts = defaultdict(int)
    events = []

    for host in sorted(host_results.keys()):
        contributions = host_results[host].get("msgid_contributions", {}) or {}
        for mid, c in contributions.items():
            if mid not in seen_by:
                seen_by[mid] = host
                continue
            # Duplicate: this host's copy is dropped, seen_by[mid]'s copy is kept.
            key = (host, c["project"], c["day"], c["model"])
            for field in _LEDGER_FIELDS:
                subtract[key][field] += c.get(field, 0) or 0
            line_counts[key] += 1
            events.append({
                "message_id": mid,
                "kept_host": seen_by[mid],
                "dropped_host": host,
                "project": c["project"],
                "day": c["day"],
                "model": c["model"],
                **{f: c.get(f, 0) or 0 for f in _LEDGER_FIELDS},
            })

    return subtract, line_counts, events


def _cross_host_dedup_report(events):
    """Prices the dropped duplicate lines (for a $ estimate of what was
    excluded) and rolls events up into a (kept_host, dropped_host) -> count
    breakdown, capping the raw event list for report size."""
    dropped_usd = 0.0
    for ev in events:
        priced_rec = {f: ev[f] for f in _LEDGER_FIELDS}
        priced_rec["model"] = ev["model"]
        cost, _, _ = price_bucket(priced_rec)
        dropped_usd += cost

    pair_counts = defaultdict(int)
    for ev in events:
        pair_counts[(ev["kept_host"], ev["dropped_host"])] += 1
    by_host_pair = [
        {"kept_host": kept, "dropped_host": dropped, "count": n}
        for (kept, dropped), n in sorted(pair_counts.items(), key=lambda kv: -kv[1])
    ]

    EVENT_CAP = 200
    return {
        "duplicate_message_count": len(events),
        "dropped_usd": dropped_usd,
        "by_host_pair": by_host_pair,
        "events": events[:EVENT_CAP],
        "events_truncated": len(events) > EVENT_CAP,
    }


def aggregate(host_results):
    """host_results: {host: parsed_extractor_json}. Returns the combined
    report structure (pricing applied, projects rolled up, self-report
    stats computed)."""
    per_host_totals = defaultdict(float)
    grand_total = 0.0

    # project -> day -> usd  (for weekly rollup + span calc)
    project_day_usd = defaultdict(lambda: defaultdict(float))
    project_host_usd = defaultdict(lambda: defaultdict(float))
    project_total_usd = defaultdict(float)

    # model_id (raw) -> {"lines": N, "path": ..., "normalized": ..., "hosts": set()}
    model_id_table = defaultdict(lambda: {"lines": 0, "path": None, "normalized": None, "hosts": set()})

    self_report_per_host = {}

    # Cross-host dedup: detected globally across all hosts' msgid_contributions
    # ledgers, on top of (not replacing) each host's own per-host message.id
    # dedup done inside the extractor. Computed once, up front, then applied
    # per-bucket below before pricing.
    dedup_subtract, dedup_line_counts, dedup_events = compute_cross_host_dedup(host_results)

    for host, parsed in host_results.items():
        meta = parsed.get("meta", {})
        buckets = parsed.get("buckets", [])

        window_with_msgid = meta.get("window_usage_lines_with_msgid", 0) or 0
        window_dup = meta.get("window_duplicate_lines", 0) or 0
        dedup_ratio = (window_dup / window_with_msgid) if window_with_msgid else 0.0

        self_report_per_host[host] = {
            "files_scanned": meta.get("files_scanned"),
            "lines_scanned": meta.get("lines_scanned"),
            "malformed_lines": meta.get("malformed_lines"),
            "lines_skipped_unknown_model": meta.get("lines_skipped_unknown_model"),
            "lines_missing_message_id": meta.get("lines_missing_message_id"),
            "duplicate_lines_skipped_global": meta.get("duplicate_lines_skipped_global"),
            "window_usage_lines_with_msgid": window_with_msgid,
            "window_duplicate_lines": window_dup,
            "dedup_ratio": dedup_ratio,
            "dedup_ratio_zero_warning": window_with_msgid > 0 and dedup_ratio == 0.0,
            "cache_nested_lines": meta.get("cache_nested_lines"),
            "cache_flat_fallback_lines": meta.get("cache_flat_fallback_lines"),
            "cache_absent_lines": meta.get("cache_absent_lines"),
            "unrecognized_cache_key_lines": meta.get("unrecognized_cache_key_lines"),
            "unrecognized_cache_keys_seen": meta.get("unrecognized_cache_keys_seen"),
        }

        for rec in buckets:
            dedup_key = (host, rec["project"], rec["day"], rec["model"])
            if dedup_key in dedup_subtract:
                # Cross-host duplicate(s) landed in this bucket -- subtract
                # their token contribution (and line count) before pricing,
                # without mutating the host's raw parsed buckets.
                rec = dict(rec)
                sub = dedup_subtract[dedup_key]
                for field in _LEDGER_FIELDS:
                    rec[field] = max(0.0, rec.get(field, 0) - sub.get(field, 0.0))
                rec["lines"] = max(0, rec.get("lines", 0) - dedup_line_counts.get(dedup_key, 0))

            cost, path, norm = price_bucket(rec)
            per_host_totals[host] += cost
            grand_total += cost

            proj = rec["project"]
            day = rec["day"]
            project_day_usd[proj][day] += cost
            project_host_usd[proj][host] += cost
            project_total_usd[proj] += cost

            mid_key = rec["model"]
            mt = model_id_table[mid_key]
            mt["lines"] += rec.get("lines", 0)
            mt["path"] = path
            mt["normalized"] = norm
            mt["hosts"].add(host)

    # Warn on tier-fallback models (once per distinct raw model id)
    for mid_key, mt in model_id_table.items():
        if mt["path"] == "tier_fallback":
            sys.stderr.write(
                "WARNING: model id %r has no exact pricing-table entry, "
                "using tier fallback for normalized id %r (mis-prices older generations)\n"
                % (mid_key, mt["normalized"])
            )
        elif mt["path"] == "unresolved":
            sys.stderr.write(
                "WARNING: model id %r could not be priced at all (no exact match, no tier match) "
                "-- this should not happen since the extractor filters unknown-tier lines\n" % mid_key
            )

    # Build per-project summaries
    projects = []
    for proj, total in project_total_usd.items():
        days = sorted(project_day_usd[proj].keys())
        first_seen = days[0] if days else None
        last_seen = days[-1] if days else None
        if first_seen and last_seen:
            span_days = (date.fromisoformat(last_seen) - date.fromisoformat(first_seen)).days + 1
        else:
            span_days = 1
        observed_span_days = span_days
        norm_basis = max(observed_span_days, 7)
        monthly = total * 30 / norm_basis

        weekly = defaultdict(float)
        for day, usd in project_day_usd[proj].items():
            weekly[iso_week_of(day)] += usd

        projects.append({
            "project": proj,
            "total_usd": total,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "observed_span_days": observed_span_days,
            "normalized_monthly_usd": monthly,
            "per_host_usd": dict(project_host_usd[proj]),
            "weekly_usd": dict(sorted(weekly.items())),
        })
    projects.sort(key=lambda p: -p["normalized_monthly_usd"])

    model_id_table_out = [
        {
            "model_id": mid_key,
            "normalized_model_id": mt["normalized"],
            "lines": mt["lines"],
            "pricing_path": mt["path"],
            "hosts": sorted(mt["hosts"]),
        }
        for mid_key, mt in model_id_table.items()
    ]
    model_id_table_out.sort(key=lambda m: -m["lines"])

    return {
        "grand_total_usd": grand_total,
        "per_host_totals": dict(per_host_totals),
        "projects": projects,
        "self_report_per_host": self_report_per_host,
        "model_id_table": model_id_table_out,
        "cross_host_dedup": _cross_host_dedup_report(dedup_events),
    }


# --------------------------------------------------------------------------
# CLI / main
# --------------------------------------------------------------------------

def _valid_date(s):
    try:
        date.fromisoformat(s)
        return s
    except ValueError:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD, got %r" % s)


def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="token_cost_report.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--hosts", required=True, help="Comma-separated SSH aliases; 'local' runs here directly, no SSH.")
    p.add_argument("--since", type=_valid_date, default=None, help="UTC date, inclusive (YYYY-MM-DD). Default: full history.")
    p.add_argument("--until", type=_valid_date, default=None, help="UTC date, inclusive (YYYY-MM-DD). Default: full history.")
    p.add_argument("--out", default=None, help="Output path for the combined JSON report. Default: .scratch/token_cost_report_<UTC-timestamp>.json")
    p.add_argument("--allow-partial", action="store_true", help="Write a report even if some hosts failed (marks it partial).")
    return p


def default_scratch_dir():
    # Resolves a .scratch/ directory two levels up from this script's own
    # directory (artifacts/token-cost-analysis/), so it works from any checkout.
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", ".."))
    return os.path.join(repo_root, ".scratch")


def print_summary(report, hosts_requested, failed_hosts, partial, since_arg, until_arg):
    if partial:
        print("PARTIAL REPORT -- one or more hosts failed and were omitted (see failed_hosts below).")
    if failed_hosts:
        print("Failed hosts:")
        for h, reason in failed_hosts:
            print("  %s: %s" % (h, reason))
        print()

    print("Window: %s .. %s (UTC)" % (since_arg or "(full history)", until_arg or "(full history)"))
    print()

    print("=== Top projects by normalized monthly $ ===")
    for p in report["projects"][:10]:
        print(
            "  %-70s $%10.2f/mo  total=$%9.2f  span=%3dd  (%s..%s)"
            % (p["project"], p["normalized_monthly_usd"], p["total_usd"], p["observed_span_days"], p["first_seen"], p["last_seen"])
        )
    print()

    print("=== Per-host subtotals ===")
    for host, usd in sorted(report["per_host_totals"].items()):
        print("  %-20s $%.2f" % (host, usd))
    print()
    print("GRAND TOTAL: $%.2f" % report["grand_total_usd"])
    print()

    print("=== Cross-host duplicate detection ===")
    chd = report["cross_host_dedup"]
    if chd["duplicate_message_count"]:
        print(
            "  %d duplicate message(s) found across hosts (~$%.2f double-counted, "
            "already excluded from totals above)"
            % (chd["duplicate_message_count"], chd["dropped_usd"])
        )
        for pair in chd["by_host_pair"]:
            print(
                "    kept in %-15s dropped from %-15s: %d message(s)"
                % (pair["kept_host"], pair["dropped_host"], pair["count"])
            )
        if chd["events_truncated"]:
            print("    (event detail truncated in JSON report; counts above are exact)")
    else:
        print("  none found")
    print()

    print("=== Self-reporting guardrails (per host) ===")
    for host, sr in report["self_report_per_host"].items():
        print("  [%s]" % host)
        print(
            "    dedup ratio: %.2f%% (%d dup / %d with-msgid, within window)"
            % (sr["dedup_ratio"] * 100, sr["window_duplicate_lines"], sr["window_usage_lines_with_msgid"])
        )
        if sr["dedup_ratio_zero_warning"]:
            print("    WARNING: dedup ratio is 0%% -- check message.id field is present in this host's JSONL")
        print(
            "    cache: nested=%s flat_fallback=%s absent=%s unrecognized_key_lines=%s%s"
            % (
                sr["cache_nested_lines"], sr["cache_flat_fallback_lines"], sr["cache_absent_lines"],
                sr["unrecognized_cache_key_lines"],
                (" keys=%s" % sr["unrecognized_cache_keys_seen"]) if sr["unrecognized_cache_keys_seen"] else "",
            )
        )
        print("    lines_skipped_unknown_model: %s" % sr["lines_skipped_unknown_model"])
    print()

    print("=== Distinct model IDs seen (pricing path) ===")
    for m in report["model_id_table"]:
        print(
            "  %-40s lines=%-10d path=%-13s hosts=%s"
            % (m["model_id"], m["lines"], m["pricing_path"], ",".join(m["hosts"]))
        )


def main():
    args = build_arg_parser().parse_args()
    hosts_requested = [h.strip() for h in args.hosts.split(",") if h.strip()]
    since_arg = args.since or ""
    until_arg = args.until or ""
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    scratch = default_scratch_dir()
    os.makedirs(scratch, exist_ok=True)

    out_path = args.out or os.path.join(scratch, "token_cost_report_%s.json" % ts)

    host_results = {}
    failed_hosts = []

    for host in hosts_requested:
        print("Running extractor on %s..." % host, file=sys.stderr)
        ok, parsed, reason = run_host(host, since_arg, until_arg)
        if not ok:
            failed_hosts.append((host, reason))
            continue
        host_results[host] = parsed
        raw_path = os.path.join(scratch, "token_cost_raw_%s_%s.json" % (host, ts))
        with open(raw_path, "w") as f:
            json.dump(parsed, f, indent=2)
        print("  ok: %s" % raw_path, file=sys.stderr)

    partial = bool(failed_hosts)

    if failed_hosts and not args.allow_partial:
        print("ERROR: the following host(s) failed:", file=sys.stderr)
        for h, reason in failed_hosts:
            print("  %s: %s" % (h, reason), file=sys.stderr)
        print("No combined report written. Pass --allow-partial to write one anyway.", file=sys.stderr)
        sys.exit(1)

    if not host_results:
        print("ERROR: no host succeeded, nothing to report.", file=sys.stderr)
        sys.exit(1)

    report = aggregate(host_results)

    out = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "hosts_requested": hosts_requested,
            "hosts_succeeded": sorted(host_results.keys()),
            "failed_hosts": [{"host": h, "reason": r} for h, r in failed_hosts],
            "partial": partial,
            "since": since_arg or None,
            "until": until_arg or None,
            "pricing_mode": "exact-model-id",
        },
        "totals": {
            "grand_total_usd": report["grand_total_usd"],
            "per_host_totals": report["per_host_totals"],
        },
        "self_report_per_host": report["self_report_per_host"],
        "model_id_table": report["model_id_table"],
        "projects": report["projects"],
        "cross_host_dedup": report["cross_host_dedup"],
    }

    if partial:
        print("NOTE: this report is PARTIAL -- host(s) failed: %s" % ", ".join(h for h, _ in failed_hosts))

    print_summary(report, hosts_requested, failed_hosts, partial, since_arg, until_arg)

    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print()
    print("Wrote combined report to %s" % out_path)


if __name__ == "__main__":
    main()
