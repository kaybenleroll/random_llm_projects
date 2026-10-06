#!/usr/bin/env python3
"""Blinded, adversarial grading of one merged pull request.

Stdlib only. Python 3.9+.

Pipeline (see RUNBOOK.md):
  stage   extract the merged tree, the merged diff and the issue text into an
          opaque read-only directory, stripping process artefacts, then scan the
          staged inputs for leakage.
  grade   stage, then run N independent headless reviewers, then one headless
          verifier per blocker/major finding (and per partial/not_met AC),
          then aggregate to a grade.
  table   merge several grade.json files into one CSV/markdown table.

The source repository is only ever read (git archive, git diff, rev-parse).
Everything this script writes goes under --out.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import signal
import statistics
import subprocess
import sys
import tarfile
import time
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

# Any path component equal to one of these is stripped (process/agent config).
STRIP_COMPONENTS = {
    ".claude", ".agents", ".github", ".githooks", ".scratch", ".codex",
    ".cursor", ".gemini", ".superpowers", ".windsurf", ".aider.tags.cache.v3",
}
# File basenames stripped wherever they occur.
STRIP_BASENAMES = {
    "CLAUDE.md", "AGENTS.md", "GEMINI.md", "CLAUDE.local.md", ".mcp.json",
    "settings.local.json", ".claudeignore", "skills-lock.json",
}
# Root-relative path prefixes stripped by default (plan directories).
DEFAULT_STRIP_PREFIXES = ("docs/plans", "docs/superpowers", "planning", "plans", ".scratch")

READONLY_TOOLS = "Read,Grep,Glob"

# Leakage terms. HARD terms fail the run wherever they occur. ARM terms reveal
# process arms; hits in the issue, diff or prompts fail the run, hits in the
# source tree are recorded for the human to judge.
HARD_TERMS = {
    "co-authored-by": r"co-authored-by",
    "claude-session": r"claude-session",
    "claude.ai/code": r"claude\.ai/code",
    "generated-with": r"generated with \[?claude",
}
ARM_TERMS = {
    "stress-test": r"stress[- ]?test",
    "check-acs": r"check-acs",
    "orchestrat": r"orchestrat",
    "plan": r"\bplans?\b",
    "scratch": r"\.scratch",
    "docs/plans": r"docs/plans",
    "superpowers": r"superpowers",
    "subagent": r"sub-?agent",
    "claude.md": r"claude\.md",
}
TREE_WARN_ONLY_PREFIX = "after/"

SEVERITIES = ("blocker", "major", "minor")


def log(msg: str) -> None:
    print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# Stripping
# --------------------------------------------------------------------------

def is_stripped(relpath: str, extra_prefixes=()) -> bool:
    """True if a repo-relative POSIX path must not reach the reviewers."""
    p = PurePosixPath(relpath)
    parts = p.parts
    if any(part in STRIP_COMPONENTS for part in parts):
        return True
    if p.name in STRIP_BASENAMES:
        return True
    if p.name == ".env" or (p.name.startswith(".env.") and not p.name.endswith(".example")):
        return True
    for prefix in tuple(DEFAULT_STRIP_PREFIXES) + tuple(extra_prefixes):
        pre = PurePosixPath(prefix.strip("/"))
        if parts[: len(pre.parts)] == pre.parts:
            return True
    return False


_DIFF_HEADER = re.compile(r"^diff --git a/(.*?) b/(.*)$")


def filter_diff(diff_text: str, extra_prefixes=()):
    """Drop per-file blocks whose old or new path is stripped.

    Returns (filtered_text, dropped_paths).
    """
    blocks, cur = [], []
    for line in diff_text.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if cur:
                blocks.append(cur)
            cur = [line]
        else:
            cur.append(line)
    if cur:
        blocks.append(cur)
    kept, dropped = [], []
    for block in blocks:
        m = _DIFF_HEADER.match(block[0].rstrip("\n"))
        if not m:
            kept.extend(block)
            continue
        a, b = m.group(1), m.group(2)
        if is_stripped(a, extra_prefixes) or is_stripped(b, extra_prefixes):
            dropped.append(b)
        else:
            kept.extend(block)
    return "".join(kept), dropped


_ISSUE_PATH_REDACTIONS = [
    re.compile(r"(?:\./)?(?:[\w.-]+/)*\.scratch/[^\s)`'\"\]]*"),
    re.compile(r"(?:\./)?(?:docs/)?plans?/[^\s)`'\"\]]*"),
    re.compile(r"(?:\./)?planning/[^\s)`'\"\]]*"),
]


def build_issue_md(title: str, body: str, extra_prefixes=()):
    """Issue title and body only; plan-document paths redacted."""
    text = f"# {title.strip()}\n\n{(body or '').strip()}\n"
    redactions = 0
    pats = list(_ISSUE_PATH_REDACTIONS)
    for prefix in extra_prefixes:
        pats.append(re.compile(re.escape(prefix.strip("/")) + r"/[^\s)`'\"\]]*"))
    for pat in pats:
        text, n = pat.subn("[path removed]", text)
        redactions += n
    return text, redactions


# --------------------------------------------------------------------------
# Git (read-only) and staging
# --------------------------------------------------------------------------

def git_env() -> dict:
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def git(repo: Path, *args: str, text=True) -> str:
    r = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=text, check=False, env=git_env(),
    )
    if r.returncode != 0:
        err = r.stderr if text else r.stderr.decode("utf-8", "replace")
        raise RuntimeError(f"git {' '.join(args)} failed: {err.strip()}")
    return r.stdout


def make_tree_writable(root: Path) -> None:
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        os.chmod(dirpath, 0o755)
        for fn in filenames:
            try:
                os.chmod(os.path.join(dirpath, fn), 0o644)
            except OSError:
                pass


def make_tree_readonly(root: Path) -> None:
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        for fn in filenames:
            os.chmod(os.path.join(dirpath, fn), 0o444)
        os.chmod(dirpath, 0o555)


def extract_tree(repo: Path, sha: str, dest: Path, extra_prefixes=()):
    """Stream `git archive <sha>` and extract only non-stripped regular files."""
    dest.mkdir(parents=True, exist_ok=False)
    proc = subprocess.Popen(
        ["git", "-C", str(repo), "archive", "--format=tar", sha],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=git_env(),
    )
    extracted, stripped, skipped_links = 0, [], 0
    dest_real = dest.resolve()
    with tarfile.open(fileobj=proc.stdout, mode="r|") as tf:
        for m in tf:
            rel = m.name
            while rel.startswith("./"):
                rel = rel[2:]
            if rel in ("", "."):
                continue
            pp = PurePosixPath(rel)
            if pp.is_absolute() or ".." in pp.parts:
                raise RuntimeError(f"unsafe archive member: {m.name!r}")
            if is_stripped(rel, extra_prefixes):
                if m.isfile():
                    stripped.append(rel)
                continue
            target = dest / rel
            if m.isdir():
                continue
            if not m.isfile():
                skipped_links += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if not str(target.parent.resolve()).startswith(str(dest_real)):
                raise RuntimeError(f"path escapes destination: {m.name!r}")
            src = tf.extractfile(m)
            with open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            extracted += 1
    while proc.stdout.read(1 << 20):  # drain trailing padding so git exits cleanly
        pass
    proc.stdout.close()
    err =proc.stderr.read().decode("utf-8", "replace")
    proc.stderr.close()
    if proc.wait() != 0:
        raise RuntimeError(f"git archive failed: {err.strip()}")
    return {"files": extracted, "stripped_files": len(stripped),
            "stripped_sample": sorted(stripped)[:40], "skipped_symlinks_or_special": skipped_links}


def list_files(root: Path):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            out.append({"path": p.relative_to(root).as_posix(), "bytes": p.stat().st_size,
                        "sha256": sha256_file(p)})
    return out


def opaque_id(label: str, sha: str) -> str:
    return hashlib.sha256(f"{label}:{sha}".encode()).hexdigest()[:12]


def stage_inputs(repo: Path, merge_sha: str, issue_title: str, issue_body: str,
                 stage_dir: Path, extra_prefixes=()):
    """Create stage_dir/{after,diff.patch,issue.md}. Returns a manifest dict.

    The diff is the first-parent diff of the merge commit (for a squash merge:
    the whole change).
    """
    full = git(repo, "rev-parse", "--verify", f"{merge_sha}^{{commit}}").strip()
    try:
        parent = git(repo, "rev-parse", "--verify", f"{full}^1").strip()
    except RuntimeError as e:
        raise RuntimeError(f"{merge_sha} has no first parent") from e
    if stage_dir.exists():
        make_tree_writable(stage_dir)
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)
    tree_info = extract_tree(repo, full, stage_dir / "after", extra_prefixes)
    raw = git(repo, "diff", "--no-color", "--no-ext-diff", "--no-textconv", "-M", parent, full)
    diff_text, dropped = filter_diff(raw, extra_prefixes)
    (stage_dir / "diff.patch").write_text(diff_text, encoding="utf-8")
    issue_text, redactions = build_issue_md(issue_title, issue_body, extra_prefixes)
    (stage_dir / "issue.md").write_text(issue_text, encoding="utf-8")
    files = list_files(stage_dir)
    make_tree_readonly(stage_dir)
    return {
        "merge_sha": full, "first_parent": parent,
        "tree": tree_info, "diff_files_dropped": sorted(dropped),
        "issue_path_redactions": redactions,
        "extra_strip_prefixes": list(extra_prefixes),
        "files": files,
        "files_sha256": sha256_bytes(json.dumps(files, sort_keys=True).encode()),
    }


# --------------------------------------------------------------------------
# Blinding scan
# --------------------------------------------------------------------------

def scan_blinding(stage_dir: Path, pr_number=None, leak_terms=(), extra_texts=None):
    """Scan everything a reviewer can read for leakage.

    Content a reviewer can see falls in two classes.
    * Authored for this change: issue.md, the prompts, and the added lines of
      diff.patch (every line of the diff for hard terms). Any hit fails.
    * Ambient: the post-merge source tree under after/. It is identical for every
      change in the repository, and anything the change itself wrote also appears
      in diff.patch. Hits there are counted and listed for the human, never failed.

    HARD terms are process metadata (PR number, branch, trailers). ARM terms hint
    at which process produced the change.

    extra_texts: {name: text} for prompts that are also sent to reviewers.
    """
    hard_pats = {k: re.compile(v, re.I) for k, v in HARD_TERMS.items()}
    if pr_number is not None:
        hard_pats["pr-number"] = re.compile(rf"(?<!\d){re.escape(str(pr_number))}(?!\d)")
    for t in leak_terms:
        if t:
            hard_pats[f"leak:{t}"] = re.compile(re.escape(t), re.I)
    arm_pats = {k: re.compile(v, re.I) for k, v in ARM_TERMS.items()}

    hard, arm_fail = [], []
    ambient: dict = {}

    def note_ambient(kind: str, term: str, name: str):
        d = ambient.setdefault(f"{kind}:{term}", {"hits": 0, "files": {}})
        d["hits"] += 1
        d["files"][name] = d["files"].get(name, 0) + 1

    def scan_text(name: str, text: str):
        in_tree = name.startswith(TREE_WARN_ONLY_PREFIX) or name.startswith("<path>after/")
        is_diff = name == "diff.patch"
        for i, line in enumerate(text.splitlines(), 1):
            for term, pat in hard_pats.items():
                if pat.search(line):
                    if in_tree:
                        note_ambient("hard", term, name)
                    else:
                        hard.append({"term": term, "file": name, "line": i, "text": line.strip()[:160]})
            if is_diff and not (line.startswith("+") and not line.startswith("+++")):
                continue  # only lines the change added are authored content
            for term, pat in arm_pats.items():
                if pat.search(line):
                    if in_tree:
                        note_ambient("arm", term, name)
                    else:
                        arm_fail.append({"term": term, "file": name, "line": i,
                                         "text": line.strip()[:160]})

    for dirpath, _dn, filenames in os.walk(stage_dir):
        for fn in filenames:
            p = Path(dirpath) / fn
            rel = p.relative_to(stage_dir).as_posix()
            scan_text(rel, p.read_bytes().decode("utf-8", "ignore"))
            scan_text(f"<path>{rel}", rel)  # file and directory names count too
    for name, text in (extra_texts or {}).items():
        scan_text(f"<prompt>{name}", text)
    for d in ambient.values():  # keep lists compact
        d["files"] = dict(sorted(d["files"].items(), key=lambda kv: -kv[1])[:6])
    return {"hard": hard, "arm_fail": arm_fail, "ambient_tree_hits": ambient,
            "ok": not hard and not arm_fail}


# --------------------------------------------------------------------------
# Minimal JSON-Schema validator (type, enum, required, properties,
# additionalProperties, items, minimum, maximum, minLength)
# --------------------------------------------------------------------------

def _type_ok(v, t: str) -> bool:
    if t == "object":
        return isinstance(v, dict)
    if t == "array":
        return isinstance(v, list)
    if t == "string":
        return isinstance(v, str)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "null":
        return v is None
    raise ValueError(f"unsupported schema type {t}")


def validate(instance, schema: dict, path: str = "$") -> list:
    errs: list = []
    t = schema.get("type")
    if t is not None and not _type_ok(instance, t):
        return [f"{path}: expected {t}, got {type(instance).__name__}"]
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: {instance!r} not in {schema['enum']}")
    if isinstance(instance, str) and "minLength" in schema and len(instance) < schema["minLength"]:
        errs.append(f"{path}: shorter than {schema['minLength']}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errs.append(f"{path}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errs.append(f"{path}: {instance} > maximum {schema['maximum']}")
    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errs.append(f"{path}: missing required '{req}'")
        props = schema.get("properties", {})
        for k, v in instance.items():
            if k in props:
                errs.extend(validate(v, props[k], f"{path}.{k}"))
            elif schema.get("additionalProperties") is False:
                errs.append(f"{path}: unexpected property '{k}'")
    if isinstance(instance, list) and "items" in schema:
        for i, v in enumerate(instance):
            errs.extend(validate(v, schema["items"], f"{path}[{i}]"))
    return errs


def extract_json_object(text: str):
    """Pull the first JSON object out of model text (tolerates fences/prose)."""
    if text is None:
        return None
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    dec = json.JSONDecoder()
    idx = s.find("{")
    while idx != -1:
        try:
            obj, _end = dec.raw_decode(s[idx:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        idx = s.find("{", idx + 1)
    return None


# --------------------------------------------------------------------------
# Grade rules and aggregation (spec: rubric.md)
# --------------------------------------------------------------------------

def compute_grade(ac_statuses, severity_counts, test_rating, scope_significances):
    """Deterministic 1-5 grade. Inputs are already verified/discarded.

    ac_statuses: iterable of met/partial/not_met/not_assessable
    severity_counts: {"blocker": n, "major": n, "minor": n}
    """
    ac = list(ac_statuses)
    blockers = severity_counts.get("blocker", 0)
    majors = severity_counts.get("major", 0)
    not_met = ac.count("not_met")
    partial = ac.count("partial")
    if blockers >= 1 or not_met >= 1:
        return 1
    if majors >= 3 or partial >= 2:
        return 2
    if majors == 2 or partial == 1 or test_rating == "inadequate":
        return 3
    if majors == 1 or test_rating == "partial" or "significant" in list(scope_significances):
        return 4
    return 5


def claim_key(kind: str, ident: str) -> str:
    return f"{kind}:{ident}"


def claims_to_verify(review: dict, cap: int):
    """Ordered claims (most severe first) needing a verification run."""
    claims = []
    for f in review["findings"]:
        if f["severity"] in ("blocker", "major"):
            prio = 0 if f["severity"] == "blocker" else 2
            claims.append((prio, claim_key("finding", f["id"]), {
                "type": "finding", "id": f["id"], "claimed_severity": f["severity"],
                "file": f["file"], "line": f["line"], "title": f["title"],
                "description": f["description"], "evidence": f["evidence"],
            }))
    for a in review["acs"]:
        if a["status"] in ("not_met", "partial"):
            prio = 1 if a["status"] == "not_met" else 3
            claims.append((prio, claim_key("ac", a["id"]), {
                "type": "acceptance_criterion", "id": a["id"], "text": a["text"],
                "claimed_status": a["status"], "evidence": a["evidence"],
            }))
    claims.sort(key=lambda c: c[0])
    return [(k, body) for _p, k, body in claims][:cap]


def apply_verification(review: dict, verifications: dict):
    """Recompute one reviewer's result after discarding unverified claims.

    verifications: {claim_key: validated verification dict or None}
    """
    verified = {s: 0 for s in SEVERITIES}
    reported_unverified_minor = 0
    discarded = []
    for f in review["findings"]:
        key = claim_key("finding", f["id"])
        if f["severity"] == "minor":
            reported_unverified_minor += 1
            continue
        v = verifications.get(key)
        if v is None:
            discarded.append({"id": f["id"], "severity": f["severity"], "reason": "not_verified"})
        elif v["verdict"] == "confirmed" and v["confirmed_severity"] in SEVERITIES:
            verified[v["confirmed_severity"]] += 1
        elif v["verdict"] == "confirmed":
            discarded.append({"id": f["id"], "severity": f["severity"], "reason": "confirmed_as_not_a_defect"})
        else:
            reason = v["verdict"] + ("_needs_execution" if v.get("needs_execution") else "")
            discarded.append({"id": f["id"], "severity": f["severity"], "reason": reason})
    eff_ac = []
    for a in review["acs"]:
        st = a["status"]
        if st in ("partial", "not_met"):
            v = verifications.get(claim_key("ac", a["id"]))
            if v is None or v["verdict"] == "unverifiable":
                st_eff = "not_assessable"
            elif v["verdict"] == "refuted":
                st_eff = "met"
            else:
                st_eff = st
            if st_eff != st:
                discarded.append({"id": a["id"], "severity": f"ac:{st}",
                                  "reason": (v["verdict"] if v else "not_verified")})
            st = st_eff
        eff_ac.append(st)
    scope = [s["significance"] for s in review["unrequested_scope"]]
    grade = compute_grade(eff_ac, verified, review["test_adequacy"]["rating"], scope)
    return {
        "grade": grade,
        "reviewer_reported_grade": review["grade"],
        "verified": verified,
        "reported_minor": reported_unverified_minor,
        "discarded": discarded,
        "acs_met": eff_ac.count("met"),
        "acs_total": len(eff_ac),
        "acs_not_assessable": eff_ac.count("not_assessable"),
        "ac_statuses": eff_ac,
        "test_adequacy": review["test_adequacy"]["rating"],
        "significant_scope": sum(1 for s in scope if s == "significant"),
    }


def median_grade(grades):
    g = [x for x in grades if x is not None]
    if not g:
        return None
    m = statistics.median(g)
    return int(m) if float(m).is_integer() else m


def aggregate(per_reviewer: list) -> dict:
    """per_reviewer: list of apply_verification() dicts (None for failed runs)."""
    valid = [r for r in per_reviewer if r is not None]
    grades = [r["grade"] for r in valid]
    return {
        "grade": median_grade(grades),
        "n_valid_reviewers": len(valid),
        "n_reviewers": len(per_reviewer),
        "per_reviewer_grades": [r["grade"] if r else None for r in per_reviewer],
        "per_reviewer_reported_grades": [r["reviewer_reported_grade"] if r else None for r in per_reviewer],
        "verified_by_severity": [r["verified"] if r else None for r in per_reviewer],
        "acs_met": [f"{r['acs_met']}/{r['acs_total']}" if r else None for r in per_reviewer],
        "acs_met_median": median_grade([r["acs_met"] for r in valid]),
        "acs_total_median": median_grade([r["acs_total"] for r in valid]),
    }


TABLE_COLUMNS = [
    "label", "issue", "merge_sha", "grade", "reviewer_grades", "reviewer_reported_grades",
    "verified_blocker", "verified_major", "verified_minor_reported",
    "discarded_blocker_major", "acs_met", "n_valid_reviewers", "model", "cli_version", "graded_at",
]


def table_row(result: dict) -> dict:
    agg = result["aggregate"]
    pr = result["per_reviewer"]

    def col(f):
        return "|".join("-" if r is None else str(f(r)) for r in pr)

    return {
        "label": result["label"], "issue": result.get("issue", ""),
        "merge_sha": result["merge_sha"][:10], "grade": agg["grade"],
        "reviewer_grades": "|".join("-" if g is None else str(g) for g in agg["per_reviewer_grades"]),
        "reviewer_reported_grades": "|".join("-" if g is None else str(g) for g in agg["per_reviewer_reported_grades"]),
        "verified_blocker": col(lambda r: r["verified"]["blocker"]),
        "verified_major": col(lambda r: r["verified"]["major"]),
        "verified_minor_reported": col(lambda r: r["verified"]["minor"] + r["reported_minor"]),
        "discarded_blocker_major": col(lambda r: len([d for d in r["discarded"] if not d["severity"].startswith("ac:")])),
        "acs_met": "|".join("-" if a is None else a for a in agg["acs_met"]),
        "n_valid_reviewers": agg["n_valid_reviewers"],
        "model": result["model_alias"], "cli_version": result["cli_version"],
        "graded_at": result["graded_at"],
    }


def render_markdown(rows: list) -> str:
    head = "| " + " | ".join(TABLE_COLUMNS) + " |\n"
    sep = "| " + " | ".join("---" for _ in TABLE_COLUMNS) + " |\n"
    body = "".join("| " + " | ".join(str(r[c]) for c in TABLE_COLUMNS) + " |\n" for r in rows)
    return head + sep + body


def write_table(rows: list, csv_path: Path, md_path: Path) -> None:
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TABLE_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    md_path.write_text(render_markdown(rows), encoding="utf-8")


# --------------------------------------------------------------------------
# Headless claude runs
# --------------------------------------------------------------------------

def find_claude(explicit=None) -> str:
    cands = [explicit] if explicit else []
    cands += [shutil.which("claude"), str(Path.home() / ".local/bin/claude"),
              str(Path.home() / ".claude/local/claude"), "/usr/local/bin/claude"]
    for c in cands:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return str(Path(c))
    raise SystemExit("claude CLI not found; pass --claude /absolute/path/to/claude")


def claude_version(claude: str) -> str:
    r = subprocess.run([claude, "--version"], capture_output=True, text=True, timeout=60)
    return r.stdout.strip() or r.stderr.strip()


SETTINGS_JSON = json.dumps({
    "disableAllHooks": True,
    "autoMemoryEnabled": False,
    "claudeMdExcludes": ["**/CLAUDE.md", "**/CLAUDE.local.md", "**/.claude/rules/**"],
}, sort_keys=True)


def build_argv(claude: str, model: str, effort: str, system_prompt: str, stage_dir: Path,
               max_budget_usd: float) -> list:
    return [
        claude, "-p", "--model", model, "--effort", effort,
        "--no-session-persistence", "--disable-slash-commands", "--restricted",
        "--tools", READONLY_TOOLS,
        "--setting-sources", "local", "--strict-mcp-config",
        "--settings", SETTINGS_JSON,
        "--add-dir", str(stage_dir),
        "--max-budget-usd", str(max_budget_usd),
        "--output-format", "json",
        "--system-prompt", system_prompt,
    ]


def child_env() -> dict:
    env = dict(os.environ)
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    return env


def run_process(argv: list, cwd: Path, stdin_text: str, timeout: int):
    """Run one child to completion in its own process group; kill the group on timeout."""
    start = time.time()
    proc = subprocess.Popen(argv, cwd=str(cwd), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, start_new_session=True,
                            env=child_env())
    try:
        out, err = proc.communicate(stdin_text, timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, err = proc.communicate()
        timed_out = True
    return {"returncode": proc.returncode, "stdout": out, "stderr": err,
            "timed_out": timed_out, "seconds": round(time.time() - start, 1)}


def parse_cli_json(stdout: str):
    """Return (result_event dict or None). Handles object or event-array output."""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    if isinstance(data, list):
        for ev in reversed(data):
            if isinstance(ev, dict) and ev.get("type") == "result":
                return ev
        return None
    return data if isinstance(data, dict) else None


def usage_of(ev: dict) -> dict:
    u = (ev or {}).get("usage", {}) or {}
    return {
        "input_tokens": u.get("input_tokens", 0),
        "cache_creation_input_tokens": u.get("cache_creation_input_tokens", 0),
        "cache_read_input_tokens": u.get("cache_read_input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
        "total_cost_usd": (ev or {}).get("total_cost_usd", 0.0) or 0.0,
        "models": sorted(((ev or {}).get("modelUsage") or {}).keys()),
        "num_turns": (ev or {}).get("num_turns"),
        "duration_ms": (ev or {}).get("duration_ms"),
    }


def add_usage(a: dict, b: dict) -> dict:
    keys = ["input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
            "output_tokens", "total_cost_usd"]
    out = {k: (a.get(k, 0) or 0) + (b.get(k, 0) or 0) for k in keys}
    out["models"] = sorted(set(a.get("models", [])) | set(b.get("models", [])))
    return out


def fill(template: str, **kw) -> str:
    for k, v in kw.items():
        template = template.replace("{{" + k + "}}", v)
    return template


def execute_role(role: str, run_dir: Path, ctx: dict, system_prompt: str, user_prompt: str,
                 schema: dict) -> dict:
    """One reviewer or verifier run with a single retry on bad output.

    Returns {"ok": bool, "parsed": dict|None, "usage": dict, "attempts": n, "seconds": s}.
    Resumable: a stored result.json short-circuits.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    done = run_dir / "result.json"
    if ctx["resume"] and done.exists():
        return json.loads(done.read_text())
    (run_dir / "system_prompt.txt").write_text(system_prompt, encoding="utf-8")
    (run_dir / "user_prompt.txt").write_text(user_prompt, encoding="utf-8")
    argv = build_argv(ctx["claude"], ctx["model"], ctx["effort"], system_prompt, ctx["stage_dir"],
                      ctx["max_budget_usd"])
    shown = list(argv)
    shown[shown.index("--system-prompt") + 1] = f"<system_prompt.txt sha256={sha256_bytes(system_prompt.encode())[:16]}>"
    cwd = ctx["cwd"]
    entries = sorted(os.listdir(cwd))
    if entries:
        raise RuntimeError(f"neutral cwd {cwd} is not empty: {entries}")
    received = {
        "role": role, "argv": shown, "cwd": str(cwd), "cwd_entries": entries,
        "add_dir": str(ctx["stage_dir"]),
        "add_dir_top_level": sorted(os.listdir(ctx["stage_dir"])),
        "add_dir_file_count": ctx["manifest_file_count"],
        "inputs_manifest_sha256": ctx["manifest_sha256"],
        "tools": READONLY_TOOLS.split(","),
        "settings_json": json.loads(SETTINGS_JSON),
        "env_overrides": {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"},
        "system_prompt_sha256": sha256_bytes(system_prompt.encode()),
        "stdin_sha256": sha256_bytes(user_prompt.encode()),
        "stdin_is_file": "user_prompt.txt",
    }
    (run_dir / "received.json").write_text(json.dumps(received, indent=2), encoding="utf-8")

    total_usage: dict = {}
    parsed = None
    t0 = time.time()
    attempts = 0
    errors: list = []
    for attempt in (1, 2):
        attempts = attempt
        r = run_process(argv, cwd, user_prompt, ctx["timeout"])
        (run_dir / f"attempt{attempt}.stdout.json").write_text(r["stdout"], encoding="utf-8")
        (run_dir / f"attempt{attempt}.stderr.txt").write_text(r["stderr"], encoding="utf-8")
        ev = parse_cli_json(r["stdout"])
        total_usage = add_usage(total_usage, usage_of(ev))
        if r["timed_out"]:
            errors.append(f"attempt {attempt}: timed out after {ctx['timeout']}s")
            continue
        if ev is None or ev.get("is_error"):
            errors.append(f"attempt {attempt}: cli error rc={r['returncode']}")
            continue
        obj = extract_json_object(ev.get("result"))
        if obj is None:
            errors.append(f"attempt {attempt}: no JSON object in output")
            continue
        verrs = validate(obj, schema)
        if verrs:
            errors.append(f"attempt {attempt}: schema: " + "; ".join(verrs[:5]))
            continue
        parsed = obj
        break
    result = {"ok": parsed is not None, "parsed": parsed, "usage": total_usage,
              "attempts": attempts, "seconds": round(time.time() - t0, 1), "errors": errors}
    done.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def fetch_issue(gh_repo: str, number: int):
    r = subprocess.run(["gh", "issue", "view", str(number), "--repo", gh_repo,
                        "--json", "title,body"], capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"gh issue view failed: {r.stderr.strip()}")
    d = json.loads(r.stdout)
    return d["title"], d["body"] or ""


def load_prompts():
    p = HERE / "prompts"
    rubric = (HERE / "rubric.md").read_text(encoding="utf-8")
    rs = json.loads((HERE / "schemas/review.schema.json").read_text())
    vs = json.loads((HERE / "schemas/verification.schema.json").read_text())
    return {
        "review_schema": rs, "verify_schema": vs,
        "reviewer_system": fill((p / "reviewer_system.txt").read_text(), RUBRIC=rubric,
                                SCHEMA=json.dumps(rs, indent=2)),
        "reviewer_task": (p / "reviewer_task.txt").read_text(),
        "verifier_system": fill((p / "verifier_system.txt").read_text(), RUBRIC=rubric,
                                SCHEMA=json.dumps(vs, indent=2)),
        "verifier_task": (p / "verifier_task.txt").read_text(),
    }


def do_stage(args, out: Path, prompts: dict):
    label = args.label
    sid = opaque_id(label, args.merge_commit)
    pr_dir = out / label
    pr_dir.mkdir(parents=True, exist_ok=True)
    stage_dir = out / "_stage" / sid
    if args.issue_file:
        raw = Path(args.issue_file).read_text(encoding="utf-8")
        title, _, body = raw.partition("\n")
        title = title.lstrip("# ").strip()
    else:
        title, body = fetch_issue(args.gh_repo, args.issue)
    extra = tuple(args.strip_prefix or ())
    manifest = stage_inputs(Path(args.repo_path), args.merge_commit, title, body, stage_dir, extra)
    manifest["label"] = label
    manifest["stage_dir"] = str(stage_dir)
    manifest["opaque_id"] = sid
    task_texts = {
        "reviewer_system": prompts["reviewer_system"], "reviewer_task": prompts["reviewer_task"],
        "verifier_system": prompts["verifier_system"], "verifier_task": prompts["verifier_task"],
    }
    leak = list(args.leak_term or [])
    scan = scan_blinding(stage_dir, pr_number=args.pr_number, leak_terms=leak, extra_texts=task_texts)
    manifest["blinding_scan"] = scan
    (pr_dir / "inputs_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest, stage_dir, scan, title


def claims_run(ctx, prompts, tag, claims, run_root):
    """Verify claims (parallel up to ctx['parallel']). Returns {key: validated dict|None}."""
    results = {}

    def one(item):
        key, body = item
        d = run_root / f"verify_{re.sub(r'[^A-Za-z0-9_.-]', '_', key)}"
        user = fill(prompts["verifier_task"], ISSUE_PATH=str(ctx["stage_dir"] / "issue.md"),
                    DIFF_PATH=str(ctx["stage_dir"] / "diff.patch"),
                    TREE_PATH=str(ctx["stage_dir"] / "after"),
                    CLAIM_JSON=json.dumps(body, indent=2, sort_keys=True))
        res = execute_role(f"verifier:{tag}:{key}", d, ctx, prompts["verifier_system"], user,
                           prompts["verify_schema"])
        return key, res

    with concurrent.futures.ThreadPoolExecutor(max_workers=ctx["parallel"]) as ex:
        for key, res in ex.map(one, claims):
            results[key] = res
    return results


def do_grade(args):
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    prompts = load_prompts()
    claude = find_claude(args.claude)
    version = claude_version(claude)
    manifest, stage_dir, scan, title = do_stage(args, out, prompts)
    log(f"staged {manifest['tree']['files']} files; hard hits={len(scan['hard'])} "
        f"arm hits outside tree={len(scan['arm_fail'])}")
    if not scan["ok"] and not args.ignore_scan:
        log("blinding scan FAILED; see inputs_manifest.json. Aborting before any model call.")
        return 3
    cwd = out / "_cwd"
    cwd.mkdir(exist_ok=True)
    pr_dir = out / args.label
    ctx = {
        "claude": claude, "model": args.model, "effort": args.effort, "stage_dir": stage_dir,
        "cwd": cwd, "timeout": args.timeout, "max_budget_usd": args.max_budget_usd,
        "resume": not args.no_resume, "parallel": args.parallel,
        "manifest_file_count": len(manifest["files"]), "manifest_sha256": manifest["files_sha256"],
    }
    t0 = time.time()
    n = args.reviewers
    review_runs = {}

    def one_review(i):
        user = fill(prompts["reviewer_task"], ISSUE_PATH=str(stage_dir / "issue.md"),
                    DIFF_PATH=str(stage_dir / "diff.patch"), TREE_PATH=str(stage_dir / "after"))
        res = execute_role(f"reviewer:{i}", pr_dir / "runs" / f"reviewer_{i}", ctx,
                           prompts["reviewer_system"], user, prompts["review_schema"])
        log(f"reviewer {i}: ok={res['ok']} attempts={res['attempts']} {res['seconds']}s "
            f"cost=${res['usage'].get('total_cost_usd', 0):.2f}")
        return i, res

    with concurrent.futures.ThreadPoolExecutor(max_workers=ctx["parallel"]) as ex:
        for i, res in ex.map(one_review, range(1, n + 1)):
            review_runs[i] = res
    t_reviews = time.time() - t0

    per_reviewer, verif_detail, total_usage = [], {}, {}
    for i in range(1, n + 1):
        total_usage = add_usage(total_usage, review_runs[i]["usage"])
    t1 = time.time()
    for i in range(1, n + 1):
        res = review_runs[i]
        if not res["ok"]:
            per_reviewer.append(None)
            continue
        review = res["parsed"]
        claims = claims_to_verify(review, args.max_verifications)
        skipped = (len([f for f in review["findings"] if f["severity"] in ("blocker", "major")])
                   + len([a for a in review["acs"] if a["status"] in ("not_met", "partial")])) - len(claims)
        log(f"reviewer {i}: {len(claims)} claims to verify (skipped over cap: {skipped})")
        vres = claims_run(ctx, prompts, f"r{i}", claims, pr_dir / "runs" / f"reviewer_{i}")
        vmap = {}
        for key, vr in vres.items():
            total_usage = add_usage(total_usage, vr["usage"])
            vmap[key] = vr["parsed"] if vr["ok"] else None
        verif_detail[i] = {k: {"ok": v["ok"], "verdict": (v["parsed"] or {}).get("verdict"),
                               "confirmed_severity": (v["parsed"] or {}).get("confirmed_severity"),
                               "needs_execution": (v["parsed"] or {}).get("needs_execution"),
                               "seconds": v["seconds"]} for k, v in vres.items()}
        per_reviewer.append(apply_verification(review, vmap))
        log(f"reviewer {i}: grade={per_reviewer[-1]['grade']} (reported {review['grade']}) "
            f"verified={per_reviewer[-1]['verified']}")
    t_verify = time.time() - t1

    agg = aggregate(per_reviewer)
    result = {
        "label": args.label, "issue": args.issue, "merge_sha": manifest["merge_sha"],
        "model_alias": args.model, "effort": args.effort, "cli_version": version,
        "claude_path": claude, "graded_at": dt.datetime.now().isoformat(timespec="seconds"),
        "resolved_models": total_usage.get("models", []),
        "aggregate": agg, "per_reviewer": per_reviewer, "verification": verif_detail,
        "usage_total": total_usage,
        "timing_seconds": {"reviewers": round(t_reviews, 1), "verification": round(t_verify, 1),
                           "total": round(time.time() - t0, 1)},
        "reviewer_errors": {str(i): review_runs[i]["errors"] for i in review_runs if review_runs[i]["errors"]},
        "blinding_scan_ok": scan["ok"],
        "inputs_manifest_sha256": manifest["files_sha256"],
    }
    (pr_dir / "grade.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    row = table_row(result)
    write_table([row], pr_dir / "row.csv", pr_dir / "row.md")
    log(f"grade={agg['grade']} reviewers={agg['per_reviewer_grades']} -> {pr_dir / 'grade.json'}")
    return 0


def do_table(args):
    rows = []
    for p in args.grade_json:
        rows.append(table_row(json.loads(Path(p).read_text())))
    write_table(rows, Path(args.csv), Path(args.md))
    return 0


def do_stage_cmd(args):
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    prompts = load_prompts()
    manifest, stage_dir, scan, _t = do_stage(args, out, prompts)
    print(json.dumps({"stage_dir": str(stage_dir), "files": manifest["tree"]["files"],
                      "scan_ok": scan["ok"], "hard": scan["hard"][:10],
                      "arm_fail": scan["arm_fail"][:10],
                      "ambient_tree_hits": scan["ambient_tree_hits"]}, indent=2))
    return 0 if scan["ok"] else 3


def add_common(p):
    p.add_argument("--repo-path", required=True, help="local clone of the repository (read only)")
    p.add_argument("--merge-commit", required=True, help="merge (squash) commit sha")
    p.add_argument("--label", required=True,
                   help="output sub-directory name; never shown to reviewers")
    p.add_argument("--issue", type=int, help="linked issue number")
    p.add_argument("--gh-repo", help="owner/name for `gh issue view` (read only)")
    p.add_argument("--issue-file", help="offline alternative: first line is the title, rest the body")
    p.add_argument("--pr-number", type=int, help="used only for the leakage scan")
    p.add_argument("--leak-term", action="append", help="extra literal term to scan for (e.g. branch name)")
    p.add_argument("--strip-prefix", action="append", help="extra repo-relative path to strip")
    p.add_argument("--out", required=True, help="output directory (the only place written to)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage", help="stage inputs and run the blinding scan only")
    add_common(s)
    s.set_defaults(fn=do_stage_cmd)
    g = sub.add_parser("grade", help="stage, review, verify, aggregate")
    add_common(g)
    g.add_argument("--claude", help="absolute path to the claude CLI")
    g.add_argument("--model", default="opus")
    g.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    g.add_argument("--reviewers", type=int, default=3)
    g.add_argument("--parallel", type=int, default=1, choices=[1, 2])
    g.add_argument("--timeout", type=int, default=2400, help="seconds per headless run")
    g.add_argument("--max-budget-usd", type=float, default=15.0, help="per headless run safety cap")
    g.add_argument("--max-verifications", type=int, default=15, help="claims verified per reviewer")
    g.add_argument("--no-resume", action="store_true")
    g.add_argument("--ignore-scan", action="store_true", help="continue despite a failed blinding scan")
    g.set_defaults(fn=do_grade)
    t = sub.add_parser("table", help="merge grade.json files into one table")
    t.add_argument("grade_json", nargs="+")
    t.add_argument("--csv", required=True)
    t.add_argument("--md", required=True)
    t.set_defaults(fn=do_table)
    args = ap.parse_args(argv)
    if args.cmd in ("stage", "grade") and not (args.issue_file or (args.gh_repo and args.issue)):
        ap.error("give --issue-file, or --gh-repo with --issue")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
