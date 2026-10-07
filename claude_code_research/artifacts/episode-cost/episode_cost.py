#!/usr/bin/env python3
"""Episode cost: fully loaded per-issue cost of Claude Code work, from transcripts.

Read-only. Walks Claude Code session transcripts under ``~/.claude/projects/``
(only the project directories you select), prices every API turn at Anthropic
list prices, attributes each turn to a GitHub issue, and writes a deterministic
report to an output directory.

What it computes
----------------
* An **issue episode** is every session (and its subagent transcripts)
  attributable to issue N, from its first turn to the merge of the PR that
  closed N (``merged_at`` in the --issues file). Turns after the merge are reported
  separately and never join the episode: ``tail`` (same-issue branch, within
  --tail-days), post-merge default-branch activity (not attributable to the
  issue), cost on other issues' branches, and ``late`` (after the tail).
* **Attribution**. By default (**branch-first**) turn-level branch evidence
  wins: a turn whose own git branch matches ``issue-N`` (so ``issue-N`` and
  ``feature/issue-N-*``) is charged to N whatever the session is called. Every
  other turn (default branch, or a branch that names no issue) takes the
  session-level verdict, from the first tier that yields any issue number:
    1. the session's latest ``custom-title`` entry contains ``#N``
       (convention: ``claude --name "#N slug"``);
    2. the git branches recorded on the session's entries (main thread and
       subagents) name issues;
    3. the first user prompt has a line starting ``Task: #N``;
    4. subagent transcripts take their parent session's verdict (the parent is
       the session directory the transcript is stored under);
    5. (only with --pr-repo OWNER/NAME) the session's own ``pr-link`` entries
       name a pull request of that repository which the --issues file lists
       for an issue. This is a weak, session-level signal, so it ranks last.
  With ``--title-first`` the session-level verdict decides every turn instead
  (the older rule), so a long-lived session titled ``#A`` that works on the
  branch of issue B is charged entirely to A. Both rules are always computed
  and compared in summary.md / report.json; the flag only picks the headline.
  When the session-level verdict names more than one issue, a turn that cannot
  be placed by its own branch is **shared** between the named issues. Sessions
  with no signal go to an explicit **unattributed** bucket. Nothing is dropped.
* If the --issues file lists pull-request numbers for an issue, a ``#<PR>``
  token in a title or prompt is resolved to the issue (PR and issue numbers
  share one number space, so otherwise ``#<PR>`` would read as a second issue).
* **Cost classes**: ``main`` (main-thread turns of a session that mostly ran on
  the default branch), ``branch`` (main-thread turns of a session that mostly ran
  on a non-default branch), ``subagent`` (every turn from a subagent transcript,
  rolled up into its parent), ``hook_child`` (headless ``claude -p`` sessions:
  entrypoint ``sdk-cli`` and either at most 3 API turns or a first prompt
  starting with --hook-prompt-prefix).
* **Cost** is API-equivalent dollars at list prices: no plan, discount,
  fast-mode or cache-TTL assumptions beyond the TTL split recorded in each
  turn. See PRICES below for the table and its verification date.
* **De-duplication**: the same message can appear several times (streamed
  partial writes, resumed or forked sessions). One record per ``message.id`` is
  kept store-wide, the one with the largest ``output_tokens`` (ties: earliest
  timestamp, then path). Selection is of the whole record, never a per-field max.

Determinism: output has no wall-clock content, fixed float formatting, sorted
keys and sorted rows, and costs are summed as integers (nano-dollars), so
unchanged inputs give byte-identical files.

Output hygiene: project directory names are written as short hashes, never as
paths.

Safety: reads only ``*.jsonl`` and ``*.meta.json`` files under the selected
project directories, plus the --issues and --ccusage-json files you pass.
Writes only inside --out. Prompt text is matched in memory and never stored
or printed; session titles are not written out.
"""
import argparse
import csv
import fnmatch
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

# --------------------------------------------------------------------------
# Pricing
# --------------------------------------------------------------------------
# Verified against https://platform.claude.com/docs/en/about-claude/pricing on
# 2026-10-06 (live fetch). Unit: US cents per million tokens, as integers, so
# that cost arithmetic is exact. Tuple order: input, output, cache write 5m,
# cache write 1h, cache read.
PRICES_DATE = "2026-10-06"
PRICES = {
    "fable-5-1":  (1000, 5000, 1250, 2000, 25),
    "fable-5":    (1000, 5000, 1250, 2000, 100),
    "mythos-5-1": (1000, 5000, 1250, 2000, 25),
    "mythos-5":   (1000, 5000, 1250, 2000, 100),
    "opus-5-5":   (400, 2000, 500, 800, 20),
    "opus-5":     (500, 2500, 625, 1000, 50),
    "opus-4-8":   (500, 2500, 625, 1000, 50),
    "opus-4-7":   (500, 2500, 625, 1000, 50),
    "opus-4-6":   (500, 2500, 625, 1000, 50),
    "opus-4-5":   (500, 2500, 625, 1000, 50),
    "opus-4-1":   (1500, 7500, 1875, 3000, 150),
    "opus-4":     (1500, 7500, 1875, 3000, 150),
    "sonnet-5-5": (200, 1000, 250, 400, 20),
    "sonnet-5":   (200, 1000, 250, 400, 20),
    "sonnet-4-6": (300, 1500, 375, 600, 30),
    "sonnet-4-5": (300, 1500, 375, 600, 30),
    "sonnet-4":   (300, 1500, 375, 600, 30),
    "haiku-4-5":  (100, 500, 125, 200, 10),
    "haiku-3-5":  (80, 400, 100, 160, 8),
}
# Family fallback for model ids not in PRICES (counted and reported).
FAMILY_FALLBACK = {
    "fable": "fable-5-1", "mythos": "mythos-5-1", "opus": "opus-4-8",
    "sonnet": "sonnet-4-6", "haiku": "haiku-3-5",
}
DEFAULT_BRANCHES = {"", "main", "master", "HEAD", "develop", "trunk"}
DEFAULT_HOOK_PROMPT_PREFIX = "Analyse this Claude Code conversation excerpt"
CLASSES = ("main", "branch", "subagent", "hook_child")

TITLE_ISSUE_RE = re.compile(r"(?<![\w&/#])#(\d+)\b")
BRANCH_ISSUE_RE = re.compile(r"(?:^|[/_-])issue-?(\d+)(?!\d)", re.IGNORECASE)
TASK_RE = re.compile(r"(?m)^[ \t]*Task:[ \t]*#(\d+)\b")


def normalise_model(model_id):
    m = (model_id or "").lower()
    m = re.sub(r"-\d{8}$", "", m)
    m = re.sub(r"^claude-", "", m)
    m = re.sub(r"\[.*\]$", "", m)
    return m


def resolve_price(model_id):
    """Return (price_tuple or None, key_or_family, path) with path in
    exact / fallback / unpriced."""
    norm = normalise_model(model_id)
    if norm in PRICES:
        return PRICES[norm], norm, "exact"
    for fam, row in FAMILY_FALLBACK.items():
        if fam in norm:
            return PRICES[row], norm, "fallback"
    return None, norm, "unpriced"


def cost_nano(price, rec):
    """Exact cost in nano-dollars. price is cents per MTok, so
    tokens * cents * 10 = nano-dollars."""
    p_in, p_out, p_w5, p_w1, p_rd = price
    return 10 * (rec["input"] * p_in + rec["output"] * p_out
                 + rec["cw5m"] * p_w5 + rec["cw1h"] * p_w1
                 + rec["read"] * p_rd)


def fmt_usd(nano):
    return "%.4f" % (nano / 1e9)


def parse_ts(ts):
    if not ts or not isinstance(ts, str):
        return None
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else ""


# --------------------------------------------------------------------------
# Transcript scanning
# --------------------------------------------------------------------------

def list_transcripts(root, project_globs):
    """Sorted list of (project, session_id, is_subagent, path)."""
    out = []
    try:
        projects = sorted(os.listdir(root))
    except OSError:
        return out
    for proj in projects:
        if not any(fnmatch.fnmatchcase(proj, g) for g in project_globs):
            continue
        pdir = os.path.join(root, proj)
        if not os.path.isdir(pdir):
            continue
        for dirpath, dirnames, filenames in os.walk(pdir):
            dirnames.sort()
            for fn in sorted(filenames):
                if not fn.endswith(".jsonl"):
                    continue
                path = os.path.join(dirpath, fn)
                rel = os.path.relpath(path, pdir).split(os.sep)
                if len(rel) == 1:
                    out.append((proj, fn[:-6], False, path))
                else:
                    out.append((proj, rel[0], True, path))
    out.sort(key=lambda t: t[3])
    return out


def _text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(b.get("text") or "")
        return "\n".join(parts)
    return ""


def _is_tool_result(content):
    return isinstance(content, list) and any(
        isinstance(b, dict) and b.get("type") == "tool_result" for b in content)


def usage_record(usage):
    cc = usage.get("cache_creation")
    cw5 = cw1 = 0
    nested = False
    if isinstance(cc, dict):
        for k, v in cc.items():
            if not isinstance(v, (int, float)):
                continue
            if v:
                nested = True
            if k == "ephemeral_5m_input_tokens":
                cw5 += int(v)
            else:  # 1h and any unrecognised bucket: priced at the 1h rate
                cw1 += int(v)
    if not nested:
        cw5 = 0
        cw1 = int(usage.get("cache_creation_input_tokens") or 0)
    return {
        "input": int(usage.get("input_tokens") or 0),
        "output": int(usage.get("output_tokens") or 0),
        "cw5m": cw5, "cw1h": cw1,
        "read": int(usage.get("cache_read_input_tokens") or 0),
        "fast": usage.get("speed") == "fast",
    }


def scan_file(path, is_subagent, hook_prefix):
    """Scan one transcript. Returns a dict of per-file facts and raw turns.
    Prompt text is matched here and discarded."""
    info = {"titles": [], "entrypoints": set(), "task_issue": None,
            "hook_prompt": False, "turns": [], "usage_lines": 0,
            "pr_links": set()}
    seen_first_prompt = False
    try:
        fh = open(path, "r", errors="replace")
    except OSError:
        return info
    with fh:
        for lineno, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            if ('"usage"' not in line and '"custom-title"' not in line
                    and '"pr-link"' not in line
                    and '"type":"user"' not in line
                    and '"type": "user"' not in line):
                continue
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if not isinstance(o, dict):
                continue
            ep = o.get("entrypoint")
            if ep:
                info["entrypoints"].add(ep)
            typ = o.get("type")
            if typ == "pr-link":
                n = o.get("prNumber")
                if isinstance(n, int) and not is_subagent:
                    info["pr_links"].add((o.get("prRepository") or "", n))
                continue
            if typ == "custom-title":
                t = o.get("customTitle")
                if isinstance(t, str) and t:
                    info["titles"].append(t)
                continue
            if typ == "user" and not is_subagent and not seen_first_prompt \
                    and not o.get("isMeta"):
                msg = o.get("message")
                content = msg.get("content") if isinstance(msg, dict) else None
                if _is_tool_result(content):
                    continue
                text = _text_of(content)
                if text.strip():
                    seen_first_prompt = True
                    m = TASK_RE.search(text)
                    if m:
                        info["task_issue"] = int(m.group(1))
                    if text.lstrip().startswith(hook_prefix):
                        info["hook_prompt"] = True
                continue
            if typ == "assistant":
                msg = o.get("message")
                if not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                if not isinstance(usage, dict):
                    continue
                ts = parse_ts(o.get("timestamp"))
                if ts is None:
                    continue
                model = msg.get("model") or ""
                if not model or model.startswith("<"):  # <synthetic>
                    continue
                info["usage_lines"] += 1
                rec = usage_record(usage)
                rec["ts"] = ts
                rec["model"] = model
                rec["branch"] = o.get("gitBranch") or ""
                rec["id"] = msg.get("id") or ""
                rec["lineno"] = lineno
                info["turns"].append(rec)
    return info


def read_meta(path):
    meta_path = path[:-6] + ".meta.json"
    try:
        with open(meta_path, "r") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def scan_store(root, project_globs, hook_prefix=DEFAULT_HOOK_PROMPT_PREFIX):
    """Scan transcripts and de-duplicate. Returns a Store dict."""
    files = list_transcripts(root, project_globs)
    sessions = {}      # (project, session_id) -> session dict
    best = {}          # message id -> winning record (keep-max)
    nomsgid = 0
    raw_usage_lines = 0
    cross_session_dups = 0
    nested_files = 0
    for fidx, (proj, sid, is_sub, path) in enumerate(files):
        info = scan_file(path, is_sub, hook_prefix)
        key = (proj, sid)
        s = sessions.get(key)
        if s is None:
            s = sessions[key] = {
                "project": proj, "session_id": sid, "titles": [],
                "entrypoints": set(), "task_issue": None, "hook_prompt": False,
                "main_files": 0, "subagent_files": 0, "main_usage_lines": 0,
                "agent_types": Counter(), "pr_links": set(),
            }
        s["entrypoints"] |= info["entrypoints"]
        if is_sub:
            s["subagent_files"] += 1
            s["agent_types"][read_meta(path).get("agentType") or "unknown"] += 1
        else:
            s["main_files"] += 1
            s["titles"].extend(info["titles"])
            if info["task_issue"] is not None and s["task_issue"] is None:
                s["task_issue"] = info["task_issue"]
            s["hook_prompt"] = s["hook_prompt"] or info["hook_prompt"]
            s["pr_links"] |= info["pr_links"]
            s["main_usage_lines"] += info["usage_lines"]
        raw_usage_lines += info["usage_lines"]
        # subagent transcripts below an extra directory level, e.g.
        # <session>/subagents/workflows/<run>/agent-*.jsonl
        nested = is_sub and len(os.path.relpath(
            path, os.path.join(root, proj)).split(os.sep)) > 3
        nested_files += nested
        for rec in info["turns"]:
            rec["session"] = key
            rec["sub"] = is_sub
            rec["fidx"] = fidx
            rec["nested"] = nested
            if rec["id"]:
                k = rec["id"]
            else:
                nomsgid += 1
                k = "\x00%d" % nomsgid
            order = (rec["ts"], fidx, rec["lineno"])
            rec["order"] = order
            b = best.get(k)
            if b is not None and b["session"] != key:
                cross_session_dups += 1
            if (b is None or rec["output"] > b["output"]
                    or (rec["output"] == b["output"] and order < b["order"])):
                best[k] = rec
    return {"files": files, "sessions": sessions, "best": best,
            "raw_usage_lines": raw_usage_lines,
            "cross_session_dup_lines": cross_session_dups,
            "nested_files": nested_files}


# --------------------------------------------------------------------------
# Attribution
# --------------------------------------------------------------------------

def branch_issue(branch):
    m = BRANCH_ISSUE_RE.search(branch or "")
    return int(m.group(1)) if m else None


def title_issues(titles, alias):
    """Issues named by the session's latest title."""
    if not titles:
        return set()
    return {alias.get(int(n), int(n)) for n in TITLE_ISSUE_RE.findall(titles[-1])}


def session_is_hook(s, hook_turn_max=3):
    return ("sdk-cli" in s["entrypoints"]
            and (s["hook_prompt"] or s["main_usage_lines"] <= hook_turn_max))


def pr_link_issues(s, alias, pr_repo):
    """Issues whose pull requests the session itself linked (pr-link entries).
    Only PRs in `alias` (listed issues' PRs) in the repository `pr_repo` count."""
    if not pr_repo:
        return frozenset()
    return frozenset(alias[n] for repo, n in s["pr_links"]
                     if repo == pr_repo and n in alias)


def attribute_session(s, turns, alias, pr_repo=None):
    """Decide attribution for one session.

    Returns (signal, issues_frozenset, mode). turn_target(turn) then maps each
    turn to ("issue", n) | ("shared", frozenset) | ("none", None).
    """
    hook = session_is_hook(s)
    t_issues = frozenset() if hook else frozenset(title_issues(s["titles"], alias))
    b_issues = frozenset(i for i in (branch_issue(t["branch"]) for t in turns)
                         if i is not None)
    task = None if hook else s["task_issue"]
    if task is not None:
        task = alias.get(task, task)
    if t_issues:
        return "title", t_issues
    if b_issues:
        return "branch", b_issues
    if task is not None:
        return "task", frozenset([task])
    p_issues = pr_link_issues(s, alias, pr_repo)
    if p_issues:
        return "pr", p_issues
    return "none", frozenset()


def turn_target(signal, issues, turn, title_first=False):
    """Map one turn to ("issue", n, sig) | ("shared", frozenset, sig) |
    ("none", None, "none"). sig is the evidence that decided this turn."""
    if signal == "none":
        return ("none", None, "none")
    bi = branch_issue(turn["branch"])
    if title_first:
        if len(issues) == 1:
            return ("issue", next(iter(issues)), signal)
        if bi in issues:
            return ("issue", bi, signal)
        return ("shared", issues, signal)
    if bi is not None:
        return ("issue", bi, "branch")
    if len(issues) == 1:
        return ("issue", next(iter(issues)), signal)
    return ("shared", issues, signal)


def classify_session(s, turns):
    if session_is_hook(s):
        return "hook_child"
    total = on_branch = 0
    for t in turns:
        c = t["nano"]
        total += c
        if (t["branch"] or "") not in DEFAULT_BRANCHES:
            on_branch += c
    if total == 0:
        n_b = sum(1 for t in turns if (t["branch"] or "") not in DEFAULT_BRANCHES)
        return "branch" if turns and n_b * 2 > len(turns) else "main"
    return "branch" if on_branch * 2 > total else "main"


def price_turns(store):
    """Attach nano-dollar costs; return pricing diagnostics."""
    diag = {"fallback_models": Counter(), "unpriced_models": Counter(),
            "fast_turns": 0}
    for rec in store["best"].values():
        price, norm, path = resolve_price(rec["model"])
        if path == "fallback":
            diag["fallback_models"][norm] += 1
        elif path == "unpriced":
            diag["unpriced_models"][norm] += 1
        if rec["fast"]:
            diag["fast_turns"] += 1
        rec["nano"] = cost_nano(price, rec) if price else 0
        rec["norm_model"] = norm
    return diag


def build(store, issues_meta, tail_days=14, title_first=False, pr_repo=None):
    """Attribute every winning turn under the selected rule (branch-first by
    default, title-first with title_first=True) and also under the other rule,
    in the same invocation, for the side-by-side comparison. Returns the
    analysis dict of the selected rule, with result["comparison"]."""
    res = _build_one(store, issues_meta, tail_days, title_first, pr_repo)
    other = _build_one(store, issues_meta, tail_days, not title_first, pr_repo)
    branch_first, title_res = (other, res) if title_first else (res, other)
    keys = sorted(n for n in res["targets"]
                  if n in res["issues"] or n in other["issues"])
    res["comparison"] = {
        "issue_set": keys,
        "branch_first": _rule_summary(branch_first, keys),
        "title_first": _rule_summary(title_res, keys),
    }
    return res


def _rule_summary(res, keys):
    zero = {"episode_nano": 0, "tail_nano": 0, "tail_default_branch_nano": 0,
            "tail_other_issues_nano": 0, "late_nano": 0}
    rows = {n: res["issues"].get(n, zero) for n in keys}
    eps = [rows[n]["episode_nano"] for n in keys]
    return {
        "episode_by_issue": {n: rows[n]["episode_nano"] for n in keys},
        "median_nano": median(eps), "sum_nano": sum(eps),
        "tail_nano": sum(rows[n]["tail_nano"] for n in keys),
        "tail_default_branch_nano": sum(rows[n]["tail_default_branch_nano"] for n in keys),
        "tail_other_issues_nano": sum(rows[n]["tail_other_issues_nano"] for n in keys),
        "late_nano": sum(rows[n]["late_nano"] for n in keys),
    }


def _build_one(store, issues_meta, tail_days, title_first, pr_repo):
    alias = {}
    for it in issues_meta:
        for pr in it.get("prs") or []:
            alias[int(pr)] = int(it["number"])
    targets = {int(it["number"]): it for it in issues_meta}
    diag = price_turns(store)

    by_session = defaultdict(list)
    for key in store["best"]:
        rec = store["best"][key]
        by_session[rec["session"]].append(rec)
    for lst in by_session.values():
        lst.sort(key=lambda r: r["order"])

    session_rows = []
    issue_acc = {}
    shared_acc = defaultdict(lambda: Counter())
    unattr_acc = Counter()
    signal_cost = Counter()
    all_turns = []  # (ts, nano, kind, who, sig, cls, conflict, evidenced)

    def acc(n):
        a = issue_acc.get(n)
        if a is None:
            a = issue_acc[n] = {
                "turn_list": [], "sessions": set(), "sub_files": 0,
                "session_class": {}, "signals": Counter(),
                "shared_exposure": 0.0, "shared_sessions": set(),
            }
        return a

    for key in sorted(store["sessions"]):
        s = store["sessions"][key]
        turns = by_session.get(key, [])
        signal, issues = attribute_session(s, turns, alias, pr_repo)
        scls = classify_session(s, turns)
        s["class"] = scls
        s["signal"] = signal
        s["issues"] = issues
        cost = sum(t["nano"] for t in turns)
        verdict = "unattributed"
        if signal != "none":
            verdict = "issue" if len(issues) == 1 else "multi"
        row = {
            "project": s["project"], "session_id": s["session_id"],
            "class": scls, "signal": signal,
            "issues": " ".join(str(i) for i in sorted(issues)),
            "verdict": verdict, "turns": len(turns),
            "subagent_files": s["subagent_files"],
            "cost_nano": cost,
            "first_ts": iso(turns[0]["ts"]) if turns else "",
            "last_ts": iso(max(t["ts"] for t in turns)) if turns else "",
        }
        session_rows.append(row)
        turn_issues = set()
        for t in turns:
            cls = "subagent" if t["sub"] else scls
            kind, who, sig = turn_target(signal, issues, t, title_first)
            bi = branch_issue(t["branch"])
            conflict = kind == "issue" and bi is not None and bi != who
            evid = kind == "issue" and (sig in ("branch", "pr") or bi == who)
            all_turns.append((t["ts"], t["nano"], kind, who, sig, cls, conflict, evid))
            if kind == "none":
                unattr_acc[cls] += t["nano"]
                signal_cost["none"] += t["nano"]
                continue
            signal_cost[sig] += t["nano"]
            if kind == "shared":
                shared_acc[who][cls] += t["nano"]
                for n in who:
                    a = acc(n)
                    a["shared_exposure"] += t["nano"] / len(who)
                    a["shared_sessions"].add(key)
                continue
            turn_issues.add(who)
            a = acc(who)
            a["turn_list"].append((t["ts"], t["nano"], cls, t["sub"], bi))
            a["sessions"].add(key)
            a["session_class"][key] = scls
            a["signals"][sig] += t["nano"]
        row["turn_issues"] = " ".join(str(i) for i in sorted(turn_issues))
    # subagent files per issue (files in sessions that have attributed turns)
    for n, a in issue_acc.items():
        a["sub_files"] = sum(store["sessions"][k]["subagent_files"]
                             for k in a["sessions"])

    # per-issue summaries
    tail = timedelta(days=tail_days)
    issues_out = {}
    for n in sorted(issue_acc):
        a = issue_acc[n]
        meta = targets.get(n)
        end = None
        if meta:
            end = parse_ts(meta.get("merged_at")) or parse_ts(meta.get("closed_at"))
        tl = sorted(a["turn_list"], key=lambda x: x[0])
        # windows: episode (up to the merge); after the merge, by where the turn
        # ran: this issue's own branch ("tail"), the default branch / a branch
        # naming no issue ("tail_default"), another issue's branch ("tail_other");
        # anything after the tail window is "late" whatever its branch.
        win = {"episode": Counter(), "tail": Counter(), "tail_default": Counter(),
               "tail_other": Counter(), "late": Counter()}
        n_main = n_sub = 0
        for ts, nano, cls, sub, bi in tl:
            if end is None or ts <= end:
                w = "episode"
            elif ts > end + tail:
                w = "late"
            elif bi == n:
                w = "tail"
            elif bi is None:
                w = "tail_default"
            else:
                w = "tail_other"
            win[w][cls] += nano
            if w == "episode":
                if sub:
                    n_sub += 1
                else:
                    n_main += 1
        ep_turns = [x for x in tl if end is None or x[0] <= end]
        sc = Counter(a["session_class"].values())
        issues_out[n] = {
            "number": n,
            "in_issues_file": meta is not None,
            "end_ts": iso(end) if end else "",
            "episode_nano": sum(win["episode"].values()),
            "tail_nano": sum(win["tail"].values()),
            "tail_default_branch_nano": sum(win["tail_default"].values()),
            "tail_other_issues_nano": sum(win["tail_other"].values()),
            "late_nano": sum(win["late"].values()),
            "total_nano": sum(sum(w.values()) for w in win.values()),
            "episode_by_class": {c: win["episode"][c] for c in CLASSES},
            "tail_by_class": {c: win["tail"][c] for c in CLASSES},
            "sessions": len(a["sessions"]),
            "sessions_by_class": {c: sc.get(c, 0) for c in ("main", "branch", "hook_child")},
            "subagent_transcripts": a["sub_files"],
            "turns_main": n_main,
            "turns_subagent": n_sub,
            "first_ts": iso(tl[0][0]) if tl else "",
            "last_ts": iso(tl[-1][0]) if tl else "",
            "episode_first_ts": iso(ep_turns[0][0]) if ep_turns else "",
            "episode_last_ts": iso(ep_turns[-1][0]) if ep_turns else "",
            "signal_nano": {k: v for k, v in sorted(a["signals"].items())},
            "shared_exposure_even_split_nano": int(round(a["shared_exposure"])),
            "shared_sessions": len(a["shared_sessions"]),
        }
    return {
        "alias": alias, "targets": targets, "issues": issues_out,
        "title_first": bool(title_first),
        "shared": {tuple(sorted(k)): dict(v) for k, v in shared_acc.items()},
        "unattributed": dict(unattr_acc), "signal_nano": dict(signal_cost),
        "sessions": session_rows, "pricing_diag": diag, "all_turns": all_turns,
    }


# --------------------------------------------------------------------------
# Coverage
# --------------------------------------------------------------------------

def coverage(result, since=None):
    """Cost split by attribution for turns on/after `since` (a datetime)."""
    targets = set(result["targets"])
    out = {"target_issues": 0, "other_issues": 0, "shared": 0, "unattributed": 0,
           "total": 0}
    by_class = {k: Counter() for k in
                ("target_issues", "other_issues", "shared", "unattributed")}
    by_signal = Counter()
    conflict_nano = 0
    evidence = {"branch_or_pr": 0, "title_or_prompt_only": 0}
    for ts, nano, kind, who, signal, cls, conflict, evid in result["all_turns"]:
        if since is not None and ts < since:
            continue
        out["total"] += nano
        if kind == "none":
            bucket = "unattributed"
        elif kind == "shared":
            bucket = "shared"
        elif who in targets:
            bucket = "target_issues"
        else:
            bucket = "other_issues"
        out[bucket] += nano
        by_class[bucket][cls] += nano
        by_signal[signal] += nano
        if conflict:
            conflict_nano += nano
        if bucket in ("target_issues", "other_issues"):
            evidence["branch_or_pr" if evid else "title_or_prompt_only"] += nano
    return {"totals": out, "conflict_nano": conflict_nano, "evidence": evidence,
            "by_class": {b: {c: v[c] for c in CLASSES} for b, v in by_class.items()},
            "by_signal": dict(sorted(by_signal.items()))}


# --------------------------------------------------------------------------
# Reconciliation against ccusage
# --------------------------------------------------------------------------

def load_ccusage_sessions(path):
    with open(path, "r") as fh:
        d = json.load(fh)
    rows = d.get("session") if isinstance(d, dict) else d
    out = {}
    for r in rows or []:
        sid = r.get("period") or r.get("sessionId")
        if sid:
            out[sid] = r
    return out


def reconcile(store, cc_rows, tolerance):
    """Compare per-session totals with a ccusage session JSON export, for the
    sessions present in the scanned store.

    Two figures are produced: the raw total, and a total that leaves out any
    model ccusage leaves unpriced (cost 0 with tokens > 0), because that is a
    ccusage price-table gap and not a difference in method. The tolerance is
    applied to the adjusted figure. A roll-up check compares sessions that
    have subagent transcripts with and without their subagents.
    """
    ours = defaultdict(int)
    ours_main = defaultdict(int)
    mod = defaultdict(lambda: Counter())
    nested_nano = 0
    sid_set = {k[1] for k in store["sessions"]}
    for rec in store["best"].values():
        sid = rec["session"][1]
        ours[sid] += rec["nano"]
        if not rec["sub"]:
            ours_main[sid] += rec["nano"]
        if sid in cc_rows:
            if rec.get("nested"):
                nested_nano += rec["nano"]
            t = mod[rec["norm_model"]]
            t["input"] += rec["input"]
            t["output"] += rec["output"]
            t["cache_creation"] += rec["cw5m"] + rec["cw1h"]
            t["read"] += rec["read"]
            t["nano"] += rec["nano"]
    common = sorted(sid_set & set(cc_rows))
    only_store = sorted(s for s in sid_set if s not in cc_rows and ours.get(s, 0))
    only_cc = len(set(cc_rows) - sid_set)
    cc_total = sum(round(cc_rows[s].get("totalCost", 0) * 1e9) for s in common)
    our_total = sum(ours.get(s, 0) for s in common)
    cc_model = defaultdict(lambda: Counter())
    for s in common:
        for mb in cc_rows[s].get("modelBreakdowns") or []:
            c = cc_model[normalise_model(mb.get("modelName"))]
            c["input"] += mb.get("inputTokens", 0)
            c["output"] += mb.get("outputTokens", 0)
            c["cache_creation"] += mb.get("cacheCreationTokens", 0)
            c["read"] += mb.get("cacheReadTokens", 0)
            c["nano"] += round(mb.get("cost", 0) * 1e9)
    unpriced = sorted(m for m, c in cc_model.items()
                      if c["nano"] == 0 and (c["input"] + c["output"] + c["read"]) > 0)
    adj_ours = our_total - sum(mod[m]["nano"] for m in unpriced)
    nested_files = store.get("nested_files", 0)
    adj_cc = cc_total
    per_model = [{"model": m, "ours": dict(mod.get(m, {})),
                  "ccusage": dict(cc_model.get(m, {}))}
                 for m in sorted(set(cc_model) | set(mod))]
    # subagent roll-up check over common sessions that have subagent transcripts
    with_sub = sorted(k[1] for k in store["sessions"]
                      if store["sessions"][k]["subagent_files"] and k[1] in cc_rows)
    roll_cc = sum(round(cc_rows[s].get("totalCost", 0) * 1e9) for s in with_sub)
    roll_ours = sum(ours.get(s, 0) for s in with_sub)
    roll_main = sum(ours_main.get(s, 0) for s in with_sub)
    worst = None
    for s in with_sub:
        c = round(cc_rows[s].get("totalCost", 0) * 1e9)
        if c > 0:
            r = abs(ours.get(s, 0) - c) / c
            if worst is None or (r, s) > worst:
                worst = (r, s)
    example = None
    if with_sub:
        s = max(with_sub, key=lambda x: (ours.get(x, 0) - ours_main.get(x, 0), x))
        example = {"session_id": s, "ours_total_nano": ours.get(s, 0),
                   "ours_main_only_nano": ours_main.get(s, 0),
                   "ccusage_nano": round(cc_rows[s].get("totalCost", 0) * 1e9)}

    def rel(a, b):
        return (a - b) / b if b else 0.0
    return {
        "tolerance": tolerance,
        "sessions_common": len(common),
        "sessions_only_in_store": len(only_store),
        "sessions_only_in_ccusage": only_cc,
        "ccusage_nano": cc_total, "ours_nano": our_total,
        "delta_raw": rel(our_total, cc_total),
        "nested_files": nested_files, "nested_nano": nested_nano,
        "delta_without_nested": rel(our_total - nested_nano, cc_total),
        "ccusage_unpriced_models": unpriced,
        "ours_adjusted_nano": adj_ours, "ccusage_adjusted_nano": adj_cc,
        "delta_adjusted": rel(adj_ours, adj_cc),
        "within_tolerance": abs(rel(adj_ours, adj_cc)) <= tolerance,
        "per_model": per_model,
        "rollup": {
            "sessions_with_subagents": len(with_sub),
            "ccusage_nano": roll_cc, "ours_with_rollup_nano": roll_ours,
            "ours_main_only_nano": roll_main,
            "delta_with_rollup": rel(roll_ours, roll_cc),
            "delta_main_only": rel(roll_main, roll_cc),
            "worst_session_rel": worst[0] if worst else 0.0,
            "worst_session_id": worst[1] if worst else "",
            "example": example,
        },
    }


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def _usd_map(d):
    return {k: fmt_usd(v) for k, v in sorted(d.items())}


def write_outputs(out_dir, result, store, params, since, recon):
    os.makedirs(out_dir, exist_ok=True)
    cov_all = coverage(result, None)
    cov_since = coverage(result, since) if since else None
    targets = sorted(result["targets"])

    # issues.csv
    cols = ["issue", "in_issues_file", "end_ts", "episode_usd", "tail_usd",
            "late_usd", "total_usd", "episode_main_usd", "episode_branch_usd",
            "episode_subagent_usd", "episode_hook_child_usd", "sessions",
            "sessions_main", "sessions_branch", "sessions_hook_child",
            "subagent_transcripts", "turns_main", "turns_subagent",
            "first_ts", "last_ts", "episode_first_ts", "episode_last_ts",
            "shared_exposure_even_split_usd", "shared_sessions",
            "tail_default_branch_usd", "tail_other_issues_usd",
            "episode_branch_first_usd", "episode_title_first_usd"]
    cmp_ = result["comparison"]
    bf = cmp_["branch_first"]["episode_by_issue"]
    tf = cmp_["title_first"]["episode_by_issue"]
    issue_nums = sorted(set(targets) | set(result["issues"]))
    rows = []
    for n in issue_nums:
        r = result["issues"].get(n)
        if r is None:
            rows.append([n, "1", "", "0.0000", "0.0000", "0.0000", "0.0000",
                         "0.0000", "0.0000", "0.0000", "0.0000", 0, 0, 0, 0, 0,
                         0, 0, "", "", "", "", "0.0000", 0, "0.0000", "0.0000",
                         fmt_usd(bf[n]) if n in bf else "",
                         fmt_usd(tf[n]) if n in tf else ""])
            continue
        e = r["episode_by_class"]
        rows.append([n, "1" if r["in_issues_file"] else "0", r["end_ts"],
                     fmt_usd(r["episode_nano"]), fmt_usd(r["tail_nano"]),
                     fmt_usd(r["late_nano"]), fmt_usd(r["total_nano"]),
                     fmt_usd(e["main"]), fmt_usd(e["branch"]),
                     fmt_usd(e["subagent"]), fmt_usd(e["hook_child"]),
                     r["sessions"], r["sessions_by_class"]["main"],
                     r["sessions_by_class"]["branch"],
                     r["sessions_by_class"]["hook_child"],
                     r["subagent_transcripts"], r["turns_main"],
                     r["turns_subagent"], r["first_ts"], r["last_ts"],
                     r["episode_first_ts"], r["episode_last_ts"],
                     fmt_usd(r["shared_exposure_even_split_nano"]),
                     r["shared_sessions"],
                     fmt_usd(r["tail_default_branch_nano"]),
                     fmt_usd(r["tail_other_issues_nano"]),
                     fmt_usd(bf[n]) if n in bf else "",
                     fmt_usd(tf[n]) if n in tf else ""])
    with open(os.path.join(out_dir, "issues.csv"), "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(cols)
        w.writerows(rows)

    # sessions.csv
    with open(os.path.join(out_dir, "sessions.csv"), "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["project", "session_id", "class", "signal", "issues",
                    "verdict", "turns", "subagent_transcripts", "cost_usd",
                    "first_ts", "last_ts", "turn_issues"])
        for r in sorted(result["sessions"],
                        key=lambda r: (project_id(r["project"]), r["session_id"])):
            w.writerow([project_id(r["project"]), r["session_id"], r["class"], r["signal"],
                        r["issues"], r["verdict"], r["turns"],
                        r["subagent_files"], fmt_usd(r["cost_nano"]),
                        r["first_ts"], r["last_ts"], r["turn_issues"]])

    # report.json
    def issue_json(r):
        return {
            "number": r["number"], "end_ts": r["end_ts"],
            "episode_usd": fmt_usd(r["episode_nano"]),
            "tail_usd": fmt_usd(r["tail_nano"]),
            "tail_default_branch_usd": fmt_usd(r["tail_default_branch_nano"]),
            "tail_other_issues_usd": fmt_usd(r["tail_other_issues_nano"]),
            "late_usd": fmt_usd(r["late_nano"]),
            "total_usd": fmt_usd(r["total_nano"]),
            "episode_by_class_usd": _usd_map(r["episode_by_class"]),
            "tail_by_class_usd": _usd_map(r["tail_by_class"]),
            "sessions": r["sessions"],
            "sessions_by_class": r["sessions_by_class"],
            "subagent_transcripts": r["subagent_transcripts"],
            "turns_main": r["turns_main"], "turns_subagent": r["turns_subagent"],
            "first_ts": r["first_ts"], "last_ts": r["last_ts"],
            "episode_first_ts": r["episode_first_ts"],
            "episode_last_ts": r["episode_last_ts"],
            "signal_usd": _usd_map(r["signal_nano"]),
            "shared_exposure_even_split_usd": fmt_usd(r["shared_exposure_even_split_nano"]),
            "shared_sessions": r["shared_sessions"],
        }

    def cov_json(c):
        if c is None:
            return None
        tot = c["totals"]["total"] or 1
        return {
            "usd": _usd_map(c["totals"]),
            "share_pct": {k: "%.2f" % (100.0 * v / tot)
                          for k, v in sorted(c["totals"].items()) if k != "total"},
            "by_class_usd": {b: _usd_map(v) for b, v in sorted(c["by_class"].items())},
            "by_signal_usd": _usd_map(c["by_signal"]),
            "branch_conflict_usd": fmt_usd(c["conflict_nano"]),
            "attributed_by_evidence_usd": _usd_map(c["evidence"]),
            "attributed_by_evidence_share_of_total_pct": {
                k: "%.2f" % (100.0 * v / tot) for k, v in sorted(c["evidence"].items())},
        }

    class_total = Counter()
    for r in result["sessions"]:
        class_total[r["class"]] += 1
    shared_rows = [{"issues": list(k), "usd": _usd_map(v),
                    "total_usd": fmt_usd(sum(v.values()))}
                   for k, v in sorted(result["shared"].items())]
    def rule_json(r):
        return {
            "issues_compared": len(cmp_["issue_set"]),
            "median_episode_usd": fmt_usd(r["median_nano"]),
            "sum_episode_usd": fmt_usd(r["sum_nano"]),
            "tail_same_issue_branch_usd": fmt_usd(r["tail_nano"]),
            "post_merge_default_branch_usd": fmt_usd(r["tail_default_branch_nano"]),
            "other_issues_branch_after_merge_usd": fmt_usd(r["tail_other_issues_nano"]),
            "late_usd": fmt_usd(r["late_nano"]),
        }
    delta = {"median_usd": fmt_usd(cmp_["branch_first"]["median_nano"]
                                   - cmp_["title_first"]["median_nano"]),
             "sum_usd": fmt_usd(cmp_["branch_first"]["sum_nano"]
                                - cmp_["title_first"]["sum_nano"])}
    report = {
        "params": params,
        "rule_comparison": {
            "headline_rule": "title_first" if result["title_first"] else "branch_first",
            "issue_set": cmp_["issue_set"],
            "branch_first": rule_json(cmp_["branch_first"]),
            "title_first": rule_json(cmp_["title_first"]),
            "delta_branch_first_minus_title_first_usd": delta,
        },
        "prices_verified": PRICES_DATE,
        "store": {
            "transcript_files": len(store["files"]),
            "sessions": len(store["sessions"]),
            "raw_usage_lines": store["raw_usage_lines"],
            "deduplicated_turns": len(store["best"]),
            "cross_session_duplicate_lines": store["cross_session_dup_lines"],
            "sessions_by_class": {c: class_total.get(c, 0) for c in ("main", "branch", "hook_child")},
        },
        "pricing": {
            "fallback_models": dict(sorted(result["pricing_diag"]["fallback_models"].items())),
            "unpriced_models": dict(sorted(result["pricing_diag"]["unpriced_models"].items())),
            "fast_mode_turns_not_repriced": result["pricing_diag"]["fast_turns"],
        },
        "coverage_all_time": cov_json(cov_all),
        "coverage_since": cov_json(cov_since),
        "issues": {str(n): issue_json(result["issues"][n])
                   for n in issue_nums if n in result["issues"]},
        "issues_without_attributed_cost": [n for n in targets
                                           if n not in result["issues"]],
        "shared_buckets": shared_rows,
        "unattributed_by_class_usd": _usd_map(
            {c: result["unattributed"].get(c, 0) for c in CLASSES}),
    }
    if recon is not None:
        report["reconciliation"] = recon_json(recon)
    with open(os.path.join(out_dir, "report.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)
        fh.write("\n")

    # summary.md
    with open(os.path.join(out_dir, "summary.md"), "w") as fh:
        fh.write(render_summary(report, result, targets, issue_nums, since, recon))
    if recon is not None:
        with open(os.path.join(out_dir, "reconciliation.md"), "w") as fh:
            fh.write(render_recon(recon))


def project_id(name):
    """Stable short hash standing in for a project directory name (which embeds
    a local path). Same name, same id, so rows stay joinable within a store."""
    return "p-" + hashlib.sha256(name.encode()).hexdigest()[:8]


def recon_json(r):
    def d(x):
        return {k: (fmt_usd(v) if k == "nano" else v) for k, v in sorted(x.items())}
    ro = r["rollup"]
    ex = ro["example"]
    return {
        "tolerance": "%.4f" % r["tolerance"],
        "sessions_common": r["sessions_common"],
        "sessions_only_in_store": r["sessions_only_in_store"],
        "sessions_only_in_ccusage": r["sessions_only_in_ccusage"],
        "ccusage_usd": fmt_usd(r["ccusage_nano"]),
        "ours_usd": fmt_usd(r["ours_nano"]),
        "delta_raw_pct": "%.3f" % (100 * r["delta_raw"]),
        "nested_subagent_files": r["nested_files"],
        "nested_subagent_usd": fmt_usd(r["nested_nano"]),
        "delta_without_nested_pct": "%.3f" % (100 * r["delta_without_nested"]),
        "ccusage_unpriced_models": r["ccusage_unpriced_models"],
        "ours_adjusted_usd": fmt_usd(r["ours_adjusted_nano"]),
        "delta_adjusted_pct": "%.3f" % (100 * r["delta_adjusted"]),
        "within_tolerance": r["within_tolerance"],
        "per_model": [{"model": m["model"], "ours": d(m["ours"]),
                       "ccusage": d(m["ccusage"])} for m in r["per_model"]],
        "rollup": {
            "sessions_with_subagents": ro["sessions_with_subagents"],
            "ccusage_usd": fmt_usd(ro["ccusage_nano"]),
            "ours_with_rollup_usd": fmt_usd(ro["ours_with_rollup_nano"]),
            "ours_main_only_usd": fmt_usd(ro["ours_main_only_nano"]),
            "delta_with_rollup_pct": "%.3f" % (100 * ro["delta_with_rollup"]),
            "delta_main_only_pct": "%.3f" % (100 * ro["delta_main_only"]),
            "worst_session_rel_pct": "%.3f" % (100 * ro["worst_session_rel"]),
            "worst_session_id": ro["worst_session_id"],
            "example": None if ex is None else {
                "session_id": ex["session_id"],
                "ours_total_usd": fmt_usd(ex["ours_total_nano"]),
                "ours_main_only_usd": fmt_usd(ex["ours_main_only_nano"]),
                "ccusage_usd": fmt_usd(ex["ccusage_nano"])},
        },
    }


def render_recon(r):
    j = recon_json(r)
    ro = j["rollup"]
    L = ["# Reconciliation with ccusage", "",
         "Compared over the %d sessions present in both the scanned store and the ccusage export "
         "(ccusage groups a session's subagent transcripts under the parent session id, as this script does)."
         % j["sessions_common"], "",
         "| measure | USD |", "|---|--:|",
         "| ccusage | %s |" % j["ccusage_usd"],
         "| this script | %s |" % j["ours_usd"],
         "| this script, excluding models ccusage leaves unpriced (%s) | %s |"
         % (", ".join(j["ccusage_unpriced_models"]) or "none", j["ours_adjusted_usd"]),
         "", "Raw delta %s%%. Delta after excluding ccusage-unpriced models %s%% against a tolerance of +/-%.2f%%: %s."
         % (j["delta_raw_pct"], j["delta_adjusted_pct"], 100 * r["tolerance"],
            "within tolerance" if r["within_tolerance"] else "OUTSIDE tolerance"),
         "", "Nested subagent transcripts (`<session>/subagents/<dir>/.../agent-*.jsonl`, e.g. workflow agents): %d files costing %s USD in this script. "
         "ccusage does not read them. Delta with those turns removed: %s%%."
         % (j["nested_subagent_files"], j["nested_subagent_usd"], j["delta_without_nested_pct"]),
         "", "Sessions in the store but not in ccusage: %d. Sessions in ccusage but not in the store (other projects): %d."
         % (j["sessions_only_in_store"], j["sessions_only_in_ccusage"]),
         "", "## Subagent roll-up check", "",
         "%d sessions have subagent transcripts. Summed over them: ccusage %s USD; this script with subagents rolled into the parent %s USD (%s%%); main thread only %s USD (%s%%)."
         % (ro["sessions_with_subagents"], ro["ccusage_usd"], ro["ours_with_rollup_usd"],
            ro["delta_with_rollup_pct"], ro["ours_main_only_usd"], ro["delta_main_only_pct"]),
         "Worst single session relative difference: %s%% (%s)." % (ro["worst_session_rel_pct"], ro["worst_session_id"])]
    if ro["example"]:
        e = ro["example"]
        L.append("Example session %s: ccusage %s; this script total %s; main thread only %s."
                 % (e["session_id"], e["ccusage_usd"], e["ours_total_usd"], e["ours_main_only_usd"]))
    L += ["", "## Per model (common sessions)", "",
          "| model | source | input | output | cache write | cache read | USD |",
          "|---|---|--:|--:|--:|--:|--:|"]
    for m in r["per_model"]:
        for lab, key in (("ccusage", "ccusage"), ("this script", "ours")):
            x = m[key]
            L.append("| %s | %s | %d | %d | %d | %d | %s |" % (
                m["model"], lab, x.get("input", 0), x.get("output", 0),
                x.get("cache_creation", 0), x.get("read", 0), fmt_usd(x.get("nano", 0))))
    L.append("")
    return "\n".join(L)


def median(vals):
    v = sorted(vals)
    n = len(v)
    if not n:
        return 0
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def render_summary(report, result, targets, issue_nums, since, recon):
    L = ["# Episode cost report", "",
         "Prices: Anthropic list prices verified %s. API-equivalent USD; no plan or cache-TTL assumptions." % PRICES_DATE,
         "Episode = first attributed turn to PR merge; tail = %d days after merge; late = after the tail."
         % report["params"]["tail_days"], ""]
    st = report["store"]
    L += ["Store: %d transcript files, %d sessions (%s), %d de-duplicated API turns."
          % (st["transcript_files"], st["sessions"],
             ", ".join("%s %d" % (k, v) for k, v in st["sessions_by_class"].items()),
             st["deduplicated_turns"]), ""]
    cmp_ = report["rule_comparison"]
    headline = cmp_["headline_rule"]
    L += ["Attribution rule for the per-issue table: %s. Both rules are computed in this run (comparison below)."
          % ("TITLE-FIRST (session title decides every turn)" if headline == "title_first"
             else "branch-first (a turn on an issue branch is charged to that issue; the session title/prompt only labels other turns)"), ""]
    L += ["## Per issue (USD)", "",
          "Columns: episode = up to the merge; tail = same-issue branch within the tail window; post-merge default = post-merge default-branch activity (not attributable to the issue); other issues = post-merge cost on other issues' branches (never charged to this issue); late = after the tail.", "",
          "| issue | episode | tail | post-merge default | other issues | late | main | branch | subagent | hook | sessions | sub files | turns main/sub | first | merge/close | shared (even split) |",
          "|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|---|---|--:|"]
    n_listed = 0
    for n in issue_nums:
        r = result["issues"].get(n)
        if r is None or not r["in_issues_file"]:
            continue
        e = r["episode_by_class"]
        n_listed += 1
        L.append("| %d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %d | %d | %d/%d | %s | %s | %s |" % (
            n, fmt_usd(r["episode_nano"]), fmt_usd(r["tail_nano"]),
            fmt_usd(r["tail_default_branch_nano"]), fmt_usd(r["tail_other_issues_nano"]),
            fmt_usd(r["late_nano"]),
            fmt_usd(e["main"]), fmt_usd(e["branch"]), fmt_usd(e["subagent"]),
            fmt_usd(e["hook_child"]), r["sessions"], r["subagent_transcripts"],
            r["turns_main"], r["turns_subagent"], r["episode_first_ts"][:10],
            r["end_ts"][:10], fmt_usd(r["shared_exposure_even_split_nano"])))
    missing = report["issues_without_attributed_cost"]
    if missing:
        L += ["", "No attributed cost found for: %s." % ", ".join(str(n) for n in missing)]
    if n_listed:
        bfj, tfj = cmp_["branch_first"], cmp_["title_first"]
        d = cmp_["delta_branch_first_minus_title_first_usd"]
        L += ["", "## Episode cost under both attribution rules", "",
              "Same issue set under both rules (%d issues from the --issues file with attributed cost under either rule)."
              % bfj["issues_compared"], "",
              "| rule | median episode | sum of episode | tail (same-issue branch) | post-merge default-branch activity (not attributable to the issue) | cost on other issues' branches after merge (never charged to this issue) |",
              "|---|--:|--:|--:|--:|--:|",
              "| branch-first (default) | %s | %s | %s | %s | %s |" % (
                  bfj["median_episode_usd"], bfj["sum_episode_usd"],
                  bfj["tail_same_issue_branch_usd"], bfj["post_merge_default_branch_usd"],
                  bfj["other_issues_branch_after_merge_usd"]),
              "| title-first (--title-first) | %s | %s | %s | %s | %s |" % (
                  tfj["median_episode_usd"], tfj["sum_episode_usd"],
                  tfj["tail_same_issue_branch_usd"], tfj["post_merge_default_branch_usd"],
                  tfj["other_issues_branch_after_merge_usd"]),
              "| delta (branch-first minus title-first) | %s | %s | | | |"
              % (d["median_usd"], d["sum_usd"]),
              "", "The headline episode cost never includes the post-merge default-branch activity or the cost on other issues' branches. The two medians differ because a long-lived session titled for an early issue often works on the branches of later issues; a large gap means title-first attribution is not trustworthy for this store. Quote both."]

    def cov_block(title, c):
        if c is None:
            return []
        out = ["", "## " + title, "", "| bucket | USD | share |", "|---|--:|--:|"]
        for k in ("target_issues", "other_issues", "shared", "unattributed"):
            out.append("| %s | %s | %s%% |" % (k, c["usd"][k], c["share_pct"][k]))
        out.append("| total | %s | 100.00%% |" % c["usd"]["total"])
        out += ["", "Cost by class within bucket (USD):", "",
                "| bucket | main | branch | subagent | hook_child |", "|---|--:|--:|--:|--:|"]
        for b in ("target_issues", "other_issues", "shared", "unattributed"):
            x = c["by_class_usd"][b]
            out.append("| %s | %s | %s | %s | %s |" % (
                b, x["main"], x["branch"], x["subagent"], x["hook_child"]))
        out += ["", "Cost by deciding signal (USD): " +
                ", ".join("%s %s" % (k, v) for k, v in c["by_signal_usd"].items()),
                "", "Attributed to an issue although the turn's own branch names a different issue (signal conflict): %s USD."
                % c["branch_conflict_usd"]]
        ev = c["attributed_by_evidence_usd"]
        evp = c["attributed_by_evidence_share_of_total_pct"]
        out += ["", "Attributed cost (target + other issues) by strength of evidence: attributed by branch/PR evidence %s USD (%s%% of total); attributed by title/prompt only %s USD (%s%% of total). The attributed share above counts both; only the first is confidently attributed."
                % (ev["branch_or_pr"], evp["branch_or_pr"],
                   ev["title_or_prompt_only"], evp["title_or_prompt_only"])]
        return out
    L += cov_block("Coverage, all time", report["coverage_all_time"])
    if since:
        L += cov_block("Coverage, turns on or after %s" % since.strftime("%Y-%m-%d"),
                       report["coverage_since"])
    L += ["", "target_issues = issues listed in --issues; other_issues = issues found by a signal but not listed; shared = multi-issue turns with no split signal; unattributed = no signal.", ""]
    pr = report["pricing"]
    L += ["## Pricing diagnostics", "",
          "Family-fallback models: %s." % (json.dumps(pr["fallback_models"]) if pr["fallback_models"] else "none"),
          "Unpriced models: %s." % (json.dumps(pr["unpriced_models"]) if pr["unpriced_models"] else "none"),
          "Fast-mode turns (priced at standard rates): %d." % pr["fast_mode_turns_not_repriced"], ""]
    if recon is not None:
        j = report["reconciliation"]
        L += ["## ccusage reconciliation", "",
              "ccusage %s USD vs this script %s USD over %d common sessions: raw delta %s%%; "
              "excluding models ccusage leaves unpriced (%s) the delta is %s%% (tolerance +/-%s). "
              "Subagent roll-up: %s%% with roll-up vs %s%% main thread only. See reconciliation.md."
              % (j["ccusage_usd"], j["ours_usd"], j["sessions_common"], j["delta_raw_pct"],
                 ", ".join(j["ccusage_unpriced_models"]) or "none", j["delta_adjusted_pct"],
                 "%.2f%%" % (100 * float(j["tolerance"])),
                 j["rollup"]["delta_with_rollup_pct"], j["rollup"]["delta_main_only_pct"]), ""]
    return "\n".join(L)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def load_issues(path):
    if not path:
        return []
    with open(path, "r") as fh:
        d = json.load(fh)
    if isinstance(d, dict):
        d = d.get("issues", [])
    out = []
    for it in d:
        out.append({
            "number": int(it["number"]),
            "merged_at": it.get("merged_at") or it.get("mergedAt"),
            "closed_at": it.get("closed_at") or it.get("closedAt"),
            "prs": [int(p) for p in it.get("prs") or []],
        })
    out.sort(key=lambda x: x["number"])
    return out


def build_arg_parser():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--projects-root", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--project-glob", action="append", default=None,
                    help="fnmatch pattern on project directory names (repeatable). "
                         "Default: every project directory.")
    ap.add_argument("--issues", help="JSON list of {number, merged_at, closed_at, prs}")
    ap.add_argument("--out", required=True, help="output directory (created)")
    ap.add_argument("--tail-days", type=int, default=14)
    ap.add_argument("--coverage-since", help="YYYY-MM-DD (UTC): also report coverage for turns on or after this date")
    ap.add_argument("--ccusage-json", help="output of `ccusage session --json` for reconciliation")
    ap.add_argument("--ccusage-tolerance", type=float, default=0.005,
                    help="relative tolerance on the adjusted total (default 0.005 = 0.5%%)")
    ap.add_argument("--hook-prompt-prefix", default=DEFAULT_HOOK_PROMPT_PREFIX)
    ap.add_argument("--pr-repo", metavar="OWNER/NAME",
                    help="enable the lowest-priority `pr` signal: a session that itself linked a "
                         "pull request of this repository (a pr-link entry) which belongs to a "
                         "listed issue is attributed to that issue. Off when omitted.")
    ap.add_argument("--title-first", action="store_true",
                    help="use the older rule as the headline: the session-level verdict "
                         "(title, then branch, task, pr link) decides every turn. Default: a "
                         "turn on a branch naming an issue is charged to that issue and the "
                         "session verdict only labels other turns. Both rules are always "
                         "computed and compared in the reports.")
    ap.add_argument("--turn-branch-wins", action="store_true",
                    help="no-op, kept for compatibility: this is now the default")
    return ap


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    globs = args.project_glob or ["*"]
    since = None
    if args.coverage_since:
        since = datetime.strptime(args.coverage_since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    issues_meta = load_issues(args.issues)
    store = scan_store(args.projects_root, globs, args.hook_prompt_prefix)
    result = build(store, issues_meta, args.tail_days, args.title_first, args.pr_repo)
    recon = None
    if args.ccusage_json:
        recon = reconcile(store, load_ccusage_sessions(args.ccusage_json),
                          args.ccusage_tolerance)
    params = {"project_globs_hashed": sorted(project_id(g) for g in globs),
              "tail_days": args.tail_days,
              "coverage_since": args.coverage_since or "",
              "hook_prompt_prefix": args.hook_prompt_prefix,
              "title_first": bool(args.title_first),
              "pr_repo": args.pr_repo or "",
              "issues_file_sha256": hashlib.sha256(
                  json.dumps(issues_meta, sort_keys=True).encode()).hexdigest()
              if issues_meta else ""}
    write_outputs(args.out, result, store, params, since, recon)
    print("wrote %s (%d files, %d sessions, %d turns)"
          % (args.out, len(store["files"]), len(store["sessions"]), len(store["best"])))
    if recon is not None and not recon["within_tolerance"]:
        print("ccusage reconciliation OUTSIDE tolerance: see %s"
              % os.path.join(args.out, "reconciliation.md"), file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
