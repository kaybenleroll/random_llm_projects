#!/usr/bin/env python3
"""Session-level analysis of Claude Code transcript JSONL files (issue #71).

Walks ~/.claude/projects (or --root) and emits one row per transcript FILE
(top-level session or subagent transcript) at *session* granularity: turn
counts, token totals (deduped by message.id), a real_work/automated/subagent/
unclassified classification, and threshold-based flagging for oversized
sessions.

Usage:
    session_analysis.py [--root PATH] [--project SUBSTR] [--since YYYY-MM-DD]
        [--until YYYY-MM-DD] [--max-turns N] [--max-cache-creation N]
        [--out-dir PATH] [--no-parquet]

Does NOT satisfy the same contract as the sibling
artifacts/token-cost-analysis/token_cost_report.py: that tool aggregates by
(project, day, model) for $-cost reporting across multiple hosts. This tool
is local-only, session-granular, and has no pricing table by design (see the
"No $ column" note in the design plan) -- session_model_tokens.csv exists
specifically so a downstream join against the sibling's MODEL_PRICING is
possible without duplicating a pricing table here.

Exit codes: 2 on a usage error (bad --root, --since after --until, negative
threshold); 0 otherwise, including a run that matches zero rows. Never
non-zero for malformed transcript lines or unreadable files -- those are
counted in guardrail counters and reported, not fatal.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timezone

# --------------------------------------------------------------------------
# Time / CLI helpers (copy-adapted from token_cost_report.py:141-151, 680-685)
# --------------------------------------------------------------------------


def parse_ts(ts):
    """Parse an ISO-ish transcript timestamp to a UTC datetime, or None."""
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


def _valid_date(s):
    try:
        date.fromisoformat(s)
        return s
    except ValueError:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD, got %r" % s)


def window_bounds(since_arg, until_arg):
    """Returns (since_dt, until_dt), each None if the corresponding CLI arg
    was not given. since_dt is 00:00:00 UTC of that date; until_dt is
    23:59:59.999999 UTC of that date -- both inclusive."""
    since_dt = None
    until_dt = None
    if since_arg:
        y, mo, da = [int(x) for x in since_arg.split("-")]
        since_dt = datetime(y, mo, da, 0, 0, 0, tzinfo=timezone.utc)
    if until_arg:
        y, mo, da = [int(x) for x in until_arg.split("-")]
        until_dt = datetime(y, mo, da, 23, 59, 59, 999999, tzinfo=timezone.utc)
    return since_dt, until_dt


# --------------------------------------------------------------------------
# Discovery (Design/Input section)
# --------------------------------------------------------------------------

# Known non-transcript control/log files that would otherwise collide on
# session_id (e.g. 10 journal.jsonl files in the real corpus all sharing the
# stem "journal"). Denylist, not a schema sniff -- a future new non-transcript
# basename would still be silently ingested. Documented as a known gap.
NON_TRANSCRIPT_BASENAMES = {"journal.jsonl", "nudge-events.jsonl"}

_AGENT_BASENAME_RE = re.compile(r"^agent-[0-9a-f]+\.jsonl$", re.IGNORECASE)


def iter_transcript_files(root):
    """Yields every *.jsonl file path under root, deterministic order.
    Includes non-transcript-denylisted files -- identify_file() excludes
    them later; this function only walks the filesystem."""
    all_paths = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn.endswith(".jsonl"):
                all_paths.append(os.path.join(dirpath, fn))
    all_paths.sort()
    return all_paths


def identify_file(path, root):
    """Classify one *.jsonl path relative to root. Never raises.

    Returns a dict:
      excluded: bool -- True for a denylisted non-transcript basename
      kind: "top_level" | "subagent" | None (None iff excluded)
      session_id: file stem, or None iff excluded
      parent_session_id: the path segment immediately preceding the first
          "subagents" directory component (any depth below it), or None
      project: first path segment relative to root, or "(root)"
      subagent_path_unmatched: True iff the basename looks like a subagent
          transcript (agent-<hex>.jsonl) but no "subagents" segment exists
          anywhere in the path (older layout) -- treated as top-level.
    """
    rel = os.path.relpath(path, root)
    parts = rel.split(os.sep)
    basename = parts[-1]
    project = parts[0] if len(parts) > 1 else "(root)"

    if basename in NON_TRANSCRIPT_BASENAMES:
        return {
            "excluded": True,
            "kind": None,
            "session_id": None,
            "parent_session_id": None,
            "project": project,
            "subagent_path_unmatched": False,
        }

    stem, ext = os.path.splitext(basename)
    if ext != ".jsonl":
        stem = basename  # defensive; iter_transcript_files only yields .jsonl

    dir_parts = parts[:-1]
    if "subagents" in dir_parts:
        idx = dir_parts.index("subagents")  # first occurrence, any depth
        parent = dir_parts[idx - 1] if idx >= 1 else None
        return {
            "excluded": False,
            "kind": "subagent",
            "session_id": stem,
            "parent_session_id": parent,
            "project": project,
            "subagent_path_unmatched": False,
        }

    unmatched = bool(_AGENT_BASENAME_RE.match(basename))
    return {
        "excluded": False,
        "kind": "top_level",
        "session_id": stem,
        "parent_session_id": None,
        "project": project,
        "subagent_path_unmatched": unmatched,
    }


# --------------------------------------------------------------------------
# Pure line-classification helpers
# --------------------------------------------------------------------------


def is_meta_line(line):
    return bool(line.get("isMeta"))


def is_tool_result_line(line):
    """True iff this is a type:"user" line whose message.content is a list
    containing a tool_result block (as opposed to a genuine typed/queued
    prompt, whose content is a plain string)."""
    if line.get("type") != "user":
        return False
    msg = line.get("message")
    if not isinstance(msg, dict):
        return False
    content = msg.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_result":
                return True
    return False


def extract_usage(line):
    """Mirrors token_cost_report.py:273-308's cache-field handling
    (copy-adapt, not import). Returns None if this line carries no usable
    usage block; otherwise a dict of raw per-line token contributions keyed
    by message_id/model plus the six token fields."""
    if line.get("type") != "assistant":
        return None
    msg = line.get("message")
    if not isinstance(msg, dict):
        return None
    usage = msg.get("usage")
    if not isinstance(usage, dict):
        return None

    input_tokens = usage.get("input_tokens", 0) or 0
    cache_read_tokens = usage.get("cache_read_input_tokens", 0) or 0
    output_tokens = usage.get("output_tokens", 0) or 0

    flat_cw = usage.get("cache_creation_input_tokens", 0) or 0
    nested = usage.get("cache_creation")
    cache_creation_5m = 0
    cache_creation_1h = 0
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
                cache_creation_5m += v
            elif k == "ephemeral_1h_input_tokens":
                cache_creation_1h += v
            else:
                # Unrecognized nested TTL bucket: sum in (never drop),
                # conservatively attributed to the 1h bucket.
                cache_creation_1h += v
    elif flat_cw:
        cache_creation_1h = flat_cw
    # else: cache_creation absent entirely -- both stay 0.

    return {
        "message_id": msg.get("id"),
        "model": msg.get("model"),
        "input_tokens": input_tokens,
        "cache_creation_5m": cache_creation_5m,
        "cache_creation_1h": cache_creation_1h,
        "cache_read_tokens": cache_read_tokens,
        "output_tokens": output_tokens,
    }


# classify_session's 6-branch decision order (Design/Classification section).
_REAL_WORK_PROMPT_SOURCES = ("typed", "queued")
_AUTOMATED_PROMPT_SOURCES = ("sdk", "system")


def classify_session(is_subagent, candidate_user_lines):
    """Pure function. candidate_user_lines is the ordered list of non-meta
    type:"user" lines that survived the isSidechain exclusion (top-level
    files only -- callers pass every non-meta user line for subagent files,
    but is_subagent short-circuits before they're consulted).

    Returns (classification, classification_basis).
    """
    # 1. subagent-by-path -> subagent, unconditionally. Never consults
    #    promptSource.
    if is_subagent:
        return "subagent", "path"

    # 2. No non-meta user line survived the isSidechain exclusion -- covers
    #    both "no user lines at all" and "user lines exist but all excluded".
    if not candidate_user_lines:
        return "unclassified", "no_user_lines"

    first = candidate_user_lines[0]
    prompt_source = first.get("promptSource")

    # 3. Recognized promptSource -> mapped.
    if prompt_source in _REAL_WORK_PROMPT_SOURCES:
        return "real_work", "prompt_source"
    if prompt_source in _AUTOMATED_PROMPT_SOURCES:
        return "automated", "prompt_source"

    # 4. promptSource present but unrecognized -> unclassified. Does NOT
    #    fall through to the entrypoint fallback.
    if prompt_source is not None:
        return "unclassified", "unknown_prompt_source"

    # 5. promptSource absent -> entrypoint fallback.
    entrypoint = first.get("entrypoint")
    if entrypoint == "cli":
        return "real_work", "entrypoint_fallback"
    if entrypoint == "sdk-cli":
        return "automated", "entrypoint_fallback"

    # 6. No usable signal at all.
    return "unclassified", "no_signal"


def pick_primary_model(per_model):
    """per_model: {model_id: {"input_tokens","cache_creation_total",
    "cache_read_tokens","output_tokens","assistant_messages"}}.
    Selection: highest total token volume; ties broken by higher
    assistant_messages, then lexically smallest model id. Returns None if
    per_model is empty."""
    if not per_model:
        return None

    def volume(m):
        return (
            m["input_tokens"]
            + m["cache_creation_total"]
            + m["cache_read_tokens"]
            + m["output_tokens"]
        )

    ranked = sorted(
        per_model.items(),
        key=lambda kv: (-volume(kv[1]), -kv[1]["assistant_messages"], kv[0]),
    )
    return ranked[0][0]


def apply_thresholds(api_turns, cache_creation_total, max_turns, max_cache_creation):
    """flagged = api_turns > max_turns OR cache_creation_total >
    max_cache_creation. Applied uniformly to every row (real_work,
    automated, and subagent alike -- see Design/Thresholds)."""
    reasons = []
    if api_turns is not None and max_turns is not None and api_turns > max_turns:
        reasons.append("api_turns")
    if (
        cache_creation_total is not None
        and max_cache_creation is not None
        and cache_creation_total > max_cache_creation
    ):
        reasons.append("cache_creation_total")
    return (len(reasons) > 0, reasons)


# --------------------------------------------------------------------------
# Per-file accumulation
# --------------------------------------------------------------------------


class SessionAccumulator:
    """Accumulates one transcript file's lines into a session row plus a
    per-model token breakdown. feed() consumes one already-json.loads'd
    line; finalize() produces the outputs."""

    def __init__(self, kind, session_id, parent_session_id, project):
        self.kind = kind  # "top_level" | "subagent"
        self.session_id = session_id
        self.parent_session_id = parent_session_id
        self.project = project

        self.cwd = None
        self.git_branch = None
        self.cc_version = None
        self.first_ts = None
        self.last_ts = None

        self.api_turns = 0
        self.user_prompts = 0
        self.malformed_lines = 0
        self.user_lines_for_classification = []

        # message_id (or a synthetic "no id" key) -> extract_usage() dict.
        # Plain dict assignment = last-occurrence-wins dedup.
        self.usage_by_msgid = {}
        self.usage_no_msgid_count = 0
        self._nomsgid_counter = 0
        # Raw count of lines carrying a usable usage block, BEFORE dedup --
        # denominator for the dedup-ratio corpus invariant
        # (sum(assistant_messages)/usage_lines_seen). Distinct from
        # len(usage_by_msgid), which is post-dedup.
        self.usage_lines_seen = 0

    def feed(self, line):
        ts = parse_ts(line.get("timestamp"))
        if ts is not None:
            if self.first_ts is None or ts < self.first_ts:
                self.first_ts = ts
            if self.last_ts is None or ts > self.last_ts:
                self.last_ts = ts

        if self.cwd is None and line.get("cwd"):
            self.cwd = line["cwd"]
        if self.git_branch is None and line.get("gitBranch"):
            self.git_branch = line["gitBranch"]
        if self.cc_version is None and line.get("version"):
            self.cc_version = line["version"]

        if line.get("type") == "user" and not is_meta_line(line):
            is_sidechain = bool(line.get("isSidechain"))
            # The sidechain exclusion applies to api_turns/user_prompts and
            # the classification-candidate list ONLY for top-level files --
            # applying it to subagent files (all-sidechain by construction)
            # would zero them out. See Design/Turn counting.
            excluded = is_sidechain and self.kind == "top_level"
            if not excluded:
                self.api_turns += 1
                if not is_tool_result_line(line):
                    self.user_prompts += 1
                self.user_lines_for_classification.append(line)

        usage = extract_usage(line)
        if usage is not None:
            self.usage_lines_seen += 1
            mid = usage["message_id"]
            if mid:
                self.usage_by_msgid[mid] = usage  # last occurrence wins
            else:
                self._nomsgid_counter += 1
                key = "\x00nomsgid\x00%d" % self._nomsgid_counter
                self.usage_by_msgid[key] = usage
                self.usage_no_msgid_count += 1

    def finalize(self):
        is_subagent = self.kind == "subagent"
        classification, basis = classify_session(
            is_subagent, self.user_lines_for_classification
        )

        if not is_subagent and self.user_lines_for_classification:
            first = self.user_lines_for_classification[0]
            first_prompt_source = first.get("promptSource")
            entrypoint = first.get("entrypoint")
        else:
            first_prompt_source = None
            entrypoint = None

        per_model = defaultdict(
            lambda: {
                "input_tokens": 0,
                "cache_creation_5m": 0,
                "cache_creation_1h": 0,
                "cache_creation_total": 0,
                "cache_read_tokens": 0,
                "output_tokens": 0,
                "assistant_messages": 0,
            }
        )
        input_tokens = 0
        cache_creation_5m = 0
        cache_creation_1h = 0
        cache_read_tokens = 0
        output_tokens = 0
        real_message_ids = []

        for mid, u in self.usage_by_msgid.items():
            if not mid.startswith("\x00nomsgid\x00"):
                real_message_ids.append(mid)
            model = u["model"] or "(unknown)"
            pm = per_model[model]
            pm["input_tokens"] += u["input_tokens"]
            pm["cache_creation_5m"] += u["cache_creation_5m"]
            pm["cache_creation_1h"] += u["cache_creation_1h"]
            pm["cache_creation_total"] += u["cache_creation_5m"] + u["cache_creation_1h"]
            pm["cache_read_tokens"] += u["cache_read_tokens"]
            pm["output_tokens"] += u["output_tokens"]
            pm["assistant_messages"] += 1

            input_tokens += u["input_tokens"]
            cache_creation_5m += u["cache_creation_5m"]
            cache_creation_1h += u["cache_creation_1h"]
            cache_read_tokens += u["cache_read_tokens"]
            output_tokens += u["output_tokens"]

        per_model = dict(per_model)
        cache_creation_total = cache_creation_5m + cache_creation_1h
        primary_model = pick_primary_model(per_model) if per_model else None
        models_sorted = sorted(per_model.keys())

        duration_s = None
        if self.first_ts is not None and self.last_ts is not None:
            duration_s = (self.last_ts - self.first_ts).total_seconds()

        row = {
            "session_id": self.session_id,
            "parent_session_id": self.parent_session_id,
            "agent_id": self.session_id if is_subagent else None,
            "project": self.project,
            "cwd": self.cwd,
            "git_branch": self.git_branch,
            "cc_version": self.cc_version,
            "classification": classification,
            "classification_basis": basis,
            "first_prompt_source": first_prompt_source,
            "entrypoint": entrypoint,
            "first_ts": self.first_ts.isoformat() if self.first_ts else None,
            "last_ts": self.last_ts.isoformat() if self.last_ts else None,
            "duration_s": duration_s,
            "api_turns": self.api_turns,
            "user_prompts": self.user_prompts,
            "assistant_messages": len(self.usage_by_msgid),
            "input_tokens": input_tokens,
            "cache_creation_5m": cache_creation_5m,
            "cache_creation_1h": cache_creation_1h,
            "cache_creation_total": cache_creation_total,
            "cache_read_tokens": cache_read_tokens,
            "output_tokens": output_tokens,
            "primary_model": primary_model,
            "models": ";".join(models_sorted),
            "model_count": len(per_model),
            "malformed_lines": self.malformed_lines,
            "flagged": None,  # filled in by the caller (needs CLI thresholds)
            "flag_reasons": "",
            # Internal-only fields, not CSV columns (DictWriter uses
            # extrasaction="ignore"): consumed by the scan loop then dropped.
            "_first_ts_dt": self.first_ts,
            "_message_ids": real_message_ids,
        }
        return row, per_model


def scan_file(path, kind, session_id, parent_session_id, project):
    """Reads and accumulates one transcript file. May raise OSError if the
    file cannot be opened/read -- the caller (process_file) is responsible
    for catching it and counting files_unreadable. Never raises on a
    malformed JSON line; those are counted in the returned accumulator."""
    acc = SessionAccumulator(kind, session_id, parent_session_id, project)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                obj = json.loads(raw_line)
            except Exception:
                acc.malformed_lines += 1
                continue
            acc.feed(obj)
    return acc


GUARDRAIL_KEYS = [
    "files_seen",
    "files_excluded_non_transcript",
    "files_filtered_out",
    "rows_excluded_no_timestamp",
    "files_unreadable",
    "subagent_path_unmatched",
    "malformed_lines_total",
    "usage_lines_seen",
    "usage_lines_missing_message_id",
    "cross_file_duplicate_ids",
]


def new_guardrails():
    return {k: 0 for k in GUARDRAIL_KEYS}


def matches_filters(row, project_substr, since_dt, until_dt):
    """Pure function over an already-built row dict (needs row["project"]
    and row["_first_ts_dt"]). Returns (keep, exclude_reason) where
    exclude_reason is None | "project" | "no_timestamp" | "date_range".
    Used by process_file's post-scan date check and directly unit-testable
    without a full file scan."""
    if project_substr and project_substr not in row["project"]:
        return False, "project"
    if since_dt is not None or until_dt is not None:
        fts = row.get("_first_ts_dt")
        if fts is None:
            return False, "no_timestamp"
        if since_dt is not None and fts < since_dt:
            return False, "date_range"
        if until_dt is not None and fts > until_dt:
            return False, "date_range"
    return True, None


def process_file(path, root, guardrails, project_substr=None, since_dt=None, until_dt=None):
    """Discovers, filters, and scans one file. Never raises -- every failure
    mode (excluded, filtered, unreadable, date-filtered, no-timestamp) is
    counted in guardrails and returns (None, info). On success returns
    ((row, per_model), info) with flagged/flag_reasons still unset (the
    caller fills them in once, after thresholds are known)."""
    info = identify_file(path, root)

    if info["excluded"]:
        guardrails["files_excluded_non_transcript"] += 1
        return None, info

    if info["subagent_path_unmatched"]:
        guardrails["subagent_path_unmatched"] += 1

    # Cheap path-based project filter: skip opening the file entirely.
    if project_substr and project_substr not in info["project"]:
        guardrails["files_filtered_out"] += 1
        return None, info

    try:
        acc = scan_file(
            path, info["kind"], info["session_id"], info["parent_session_id"], info["project"]
        )
    except OSError as e:
        guardrails["files_unreadable"] += 1
        sys.stderr.write("WARNING: unreadable file %s: %s\n" % (path, e))
        return None, info

    guardrails["malformed_lines_total"] += acc.malformed_lines
    guardrails["usage_lines_seen"] += acc.usage_lines_seen
    guardrails["usage_lines_missing_message_id"] += acc.usage_no_msgid_count

    row, per_model = acc.finalize()

    keep, reason = matches_filters(row, None, since_dt, until_dt)
    if not keep:
        if reason == "no_timestamp":
            guardrails["rows_excluded_no_timestamp"] += 1
        else:
            guardrails["files_filtered_out"] += 1
        return None, info

    return (row, per_model), info


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

SESSION_COLUMNS = [
    "session_id", "parent_session_id", "agent_id", "project", "cwd", "git_branch",
    "cc_version", "classification", "classification_basis", "first_prompt_source",
    "entrypoint", "first_ts", "last_ts", "duration_s", "api_turns", "user_prompts",
    "assistant_messages", "input_tokens", "cache_creation_5m", "cache_creation_1h",
    "cache_creation_total", "cache_read_tokens", "output_tokens", "primary_model",
    "models", "model_count", "malformed_lines", "flagged", "flag_reasons",
]
assert len(SESSION_COLUMNS) == 29, "sessions.csv column count drifted from the design spec"

MODEL_COLUMNS = [
    "session_id", "project", "classification", "model", "input_tokens",
    "cache_creation_5m", "cache_creation_1h", "cache_creation_total",
    "cache_read_tokens", "output_tokens", "assistant_messages",
]


def build_model_rows(session_id, project, classification, per_model):
    rows = []
    for model, agg in per_model.items():
        row = {"session_id": session_id, "project": project, "classification": classification, "model": model}
        row.update(agg)
        rows.append(row)
    return rows


def write_csv(path, rows, columns):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


# --------------------------------------------------------------------------
# Parquet (conditional -- Design/Output section)
# --------------------------------------------------------------------------


def session_parquet_schema(pa):
    """Explicit schema for sessions.parquet, field order matching
    SESSION_COLUMNS. Declared explicitly (not inferred via
    pa.Table.from_pylist) because from_pylist infers a column's type from
    its values, and a leading None in a column (e.g. parent_session_id on a
    top-level/null-parent row, which fixture-file sort order and the real
    corpus both put first) coerces that whole column to pyarrow's null
    type -- silently dropping the "string" type information a downstream
    reader needs. Timestamps are plain strings (first_ts/last_ts), not
    pa.timestamp(), so CSV and Parquet always agree on their textual form."""
    string = pa.string()
    int64 = pa.int64()
    return pa.schema([
        pa.field("session_id", string),
        pa.field("parent_session_id", string),
        pa.field("agent_id", string),
        pa.field("project", string),
        pa.field("cwd", string),
        pa.field("git_branch", string),
        pa.field("cc_version", string),
        pa.field("classification", string),
        pa.field("classification_basis", string),
        pa.field("first_prompt_source", string),
        pa.field("entrypoint", string),
        pa.field("first_ts", string),
        pa.field("last_ts", string),
        pa.field("duration_s", pa.float64()),
        pa.field("api_turns", int64),
        pa.field("user_prompts", int64),
        pa.field("assistant_messages", int64),
        pa.field("input_tokens", int64),
        pa.field("cache_creation_5m", int64),
        pa.field("cache_creation_1h", int64),
        pa.field("cache_creation_total", int64),
        pa.field("cache_read_tokens", int64),
        pa.field("output_tokens", int64),
        pa.field("primary_model", string),
        pa.field("models", string),
        pa.field("model_count", int64),
        pa.field("malformed_lines", int64),
        pa.field("flagged", pa.bool_()),
        pa.field("flag_reasons", string),
    ])


def model_parquet_schema(pa):
    """Explicit schema for session_model_tokens.parquet, field order
    matching MODEL_COLUMNS. Same from_pylist-inference rationale as
    session_parquet_schema."""
    string = pa.string()
    int64 = pa.int64()
    return pa.schema([
        pa.field("session_id", string),
        pa.field("project", string),
        pa.field("classification", string),
        pa.field("model", string),
        pa.field("input_tokens", int64),
        pa.field("cache_creation_5m", int64),
        pa.field("cache_creation_1h", int64),
        pa.field("cache_creation_total", int64),
        pa.field("cache_read_tokens", int64),
        pa.field("output_tokens", int64),
        pa.field("assistant_messages", int64),
    ])


def _table_from_rows(pa, rows, schema):
    """Builds a pa.Table via from_arrays against an explicit schema (never
    from_pylist -- see session_parquet_schema's docstring)."""
    arrays = [pa.array([r.get(f.name) for r in rows], type=f.type) for f in schema]
    return pa.Table.from_arrays(arrays, schema=schema)


def try_write_parquet(out_dir, rows, model_rows):
    """Attempts sessions.parquet + session_model_tokens.parquet. Returns
    True if pyarrow was importable and both files were written; False on
    ImportError (prints a stdout note, never raises -- CSV output is always
    written regardless of this function's outcome)."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        print("pyarrow not installed -- skipping Parquet output (CSVs written as usual).")
        return False

    session_schema = session_parquet_schema(pa)
    session_table = _table_from_rows(pa, rows, session_schema)
    pq.write_table(session_table, os.path.join(out_dir, "sessions.parquet"))

    model_schema = model_parquet_schema(pa)
    model_table = _table_from_rows(pa, model_rows, model_schema)
    pq.write_table(model_table, os.path.join(out_dir, "session_model_tokens.parquet"))

    return True


def _pyarrow_importable():
    try:
        import pyarrow  # noqa: F401
        return True
    except ImportError:
        return False


def build_summary(rows, guardrails, elapsed_s, args, pyarrow_available=False):
    classification_counts = defaultdict(int)
    classification_basis_counts = defaultdict(int)
    unknown_prompt_source_values = defaultdict(int)
    token_totals_by_classification = defaultdict(lambda: defaultdict(int))

    for r in rows:
        classification_counts[r["classification"]] += 1
        classification_basis_counts[r["classification_basis"]] += 1
        if r["classification_basis"] == "unknown_prompt_source":
            unknown_prompt_source_values[r.get("first_prompt_source") or "(none)"] += 1
        tt = token_totals_by_classification[r["classification"]]
        for f in ("input_tokens", "cache_creation_total", "cache_read_tokens", "output_tokens"):
            tt[f] += r[f]

    flagged_rows = [r for r in rows if r["flagged"]]
    top20 = sorted(
        flagged_rows, key=lambda r: (r["cache_creation_total"], r["api_turns"]), reverse=True
    )[:20]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": args.root,
        "project_filter": args.project,
        "since": args.since,
        "until": args.until,
        "max_turns": args.max_turns,
        "max_cache_creation": args.max_cache_creation,
        "elapsed_s": elapsed_s,
        "rows_emitted": len(rows),
        "pyarrow_available": pyarrow_available,
        "classification_counts": dict(classification_counts),
        "classification_basis_counts": dict(classification_basis_counts),
        "unknown_prompt_source_values": dict(unknown_prompt_source_values),
        "flagged_count": len(flagged_rows),
        "token_totals_by_classification": {
            k: dict(v) for k, v in token_totals_by_classification.items()
        },
        "guardrails": dict(guardrails),
        "top_20_flagged": [
            {
                "session_id": r["session_id"],
                "project": r["project"],
                "classification": r["classification"],
                "api_turns": r["api_turns"],
                "cache_creation_total": r["cache_creation_total"],
                "flag_reasons": r["flag_reasons"],
            }
            for r in top20
        ],
    }


def print_summary(summary):
    print("=== session_analysis.py summary ===")
    print("root: %s  window: %s..%s  project filter: %s" % (
        summary["root"], summary["since"] or "(full history)",
        summary["until"] or "(full history)", summary["project_filter"] or "(none)"))
    print("elapsed: %.2fs" % summary["elapsed_s"])
    print("rows emitted: %d" % summary["rows_emitted"])
    print("pyarrow available: %s" % summary["pyarrow_available"])
    print()
    print("=== classification counts ===")
    for k, v in sorted(summary["classification_counts"].items()):
        print("  %-15s %d" % (k, v))
    print()
    print("=== classification_basis counts ===")
    for k, v in sorted(summary["classification_basis_counts"].items()):
        print("  %-25s %d" % (k, v))
    if summary["unknown_prompt_source_values"]:
        print("  unrecognized promptSource values:", dict(summary["unknown_prompt_source_values"]))
    print()
    print("flagged rows: %d (thresholds: max_turns=%s, max_cache_creation=%s)" % (
        summary["flagged_count"], summary["max_turns"], summary["max_cache_creation"]))
    print()
    print("=== guardrails ===")
    for k in GUARDRAIL_KEYS:
        print("  %-32s %d" % (k, summary["guardrails"].get(k, 0)))
    print()
    if summary["top_20_flagged"]:
        print("=== top flagged (up to 20) ===")
        for r in summary["top_20_flagged"]:
            print("  %-15s %-30s api_turns=%-5s cache_creation_total=%-10s reasons=%s" % (
                r["classification"], r["session_id"][:30], r["api_turns"],
                r["cache_creation_total"], r["flag_reasons"]))


def write_json_summary(path, summary):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)


# --------------------------------------------------------------------------
# CLI / main
# --------------------------------------------------------------------------


def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="session_analysis.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--root", default=os.path.expanduser("~/.claude/projects"),
                    help="Transcript root (default: ~/.claude/projects).")
    p.add_argument("--project", default=None, help="Only rows whose project dir contains this substring.")
    p.add_argument("--since", type=_valid_date, default=None,
                    help="UTC date, inclusive. Filters on a session's first_ts only.")
    p.add_argument("--until", type=_valid_date, default=None,
                    help="UTC date, inclusive. Filters on a session's first_ts only.")
    p.add_argument("--max-turns", type=int, default=175, help="Flag threshold for api_turns (default: 175, p95 real_work).")
    p.add_argument("--max-cache-creation", type=int, default=1525000,
                    help="Flag threshold for cache_creation_total (default: 1525000, p95 real_work).")
    p.add_argument("--out-dir", default=None, help="Output directory (default: claude_code_research/.scratch).")
    p.add_argument("--no-parquet", action="store_true", help="Skip Parquet output even if pyarrow is available.")
    return p


def default_outdir():
    here = os.path.dirname(os.path.abspath(__file__))
    repo_ish_root = os.path.abspath(os.path.join(here, "..", ".."))
    return os.path.join(repo_ish_root, ".scratch")


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if not os.path.isdir(args.root):
        parser.error("--root %r is not a directory" % args.root)
    if args.since and args.until and args.since > args.until:
        parser.error("--since must not be after --until")
    if args.max_turns < 0 or args.max_cache_creation < 0:
        parser.error("--max-turns and --max-cache-creation must be non-negative")

    since_dt, until_dt = window_bounds(args.since, args.until)
    out_dir = args.out_dir or default_outdir()
    os.makedirs(out_dir, exist_ok=True)

    guardrails = new_guardrails()
    global_seen_msgids = set()
    rows = []
    model_rows = []

    t0 = time.time()
    for path in iter_transcript_files(args.root):
        guardrails["files_seen"] += 1
        result, info = process_file(
            path, args.root, guardrails,
            project_substr=args.project, since_dt=since_dt, until_dt=until_dt,
        )
        if result is None:
            continue
        row, per_model = result

        for mid in row.get("_message_ids") or []:
            if mid in global_seen_msgids:
                guardrails["cross_file_duplicate_ids"] += 1
            else:
                global_seen_msgids.add(mid)

        flagged, reasons = apply_thresholds(
            row["api_turns"], row["cache_creation_total"], args.max_turns, args.max_cache_creation
        )
        row["flagged"] = flagged
        row["flag_reasons"] = ";".join(sorted(reasons))

        rows.append(row)
        model_rows.extend(
            build_model_rows(row["session_id"], row["project"], row["classification"], per_model)
        )
    elapsed = time.time() - t0

    write_csv(os.path.join(out_dir, "sessions.csv"), rows, SESSION_COLUMNS)
    write_csv(os.path.join(out_dir, "session_model_tokens.csv"), model_rows, MODEL_COLUMNS)

    if args.no_parquet:
        # Still report whether pyarrow *could* have been used, for an
        # accurate pyarrow_available in the summary -- but never write.
        pyarrow_available = _pyarrow_importable()
    else:
        pyarrow_available = try_write_parquet(out_dir, rows, model_rows)

    summary = build_summary(rows, guardrails, elapsed, args, pyarrow_available=pyarrow_available)
    print_summary(summary)
    write_json_summary(os.path.join(out_dir, "session_summary.json"), summary)

    sys.exit(0)


if __name__ == "__main__":
    main()
