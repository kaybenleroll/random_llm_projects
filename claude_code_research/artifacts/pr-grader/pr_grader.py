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
  preflight  check the claude CLI version, `--restricted`, and that a Read outside
          the staged directory is refused.

The source repository is only ever read (git archive, git diff, rev-parse).
Everything this script writes goes under --out and --stage-root (a neutral
directory the reviewers see; --out is never shown to them).
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import json
import os
import random
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

# Leakage terms, in two tiers.
#
# STRICT terms identify a process arm, a person, a PR or a branch. A hit in
# anything authored for this change (issue text, the diff, the filled prompts,
# the argv, the stage and working-directory paths, any file or directory name)
# aborts the run. Hits in the unchanged tree content are counted per term in
# the manifest (`ambient.strict`); the change-specific identifiers (PR number,
# branch name, --leak-term) abort even there, because they cannot be ambient.
# STRICT_ALL_LINES terms are checked on every diff line, the rest only on lines
# the change added.
#
# DOMAIN-AMBIGUOUS terms are ordinary words in many repositories. They never
# abort: hits are warned about and counted (authored and ambient separately).
STRICT_ALL_LINES = {
    "co-authored-by": r"co-authored-by",
    "claude-session": r"claude-session",
    "claude.ai/code": r"claude\.ai/code",
    "generated-with": r"generated with \[?claude",
}
STRICT_ADDED_LINES = {
    "check-acs": r"check-acs",
    "scratch": r"\.scratch",
    "handover-file": r"handover[\w.-]*\.(?:md|txt|json|ya?ml)\b",
    "plan-file-path": r"docs/plans/|(?<![\w/-])plans/\d{4}-|planning/archive/",
    "superpowers": r"superpowers",
}
DOMAIN_AMBIGUOUS_TERMS = {
    "plan": r"\bplans?\b",
    "stress-test": r"stress[- ]?test",
    "orchestrat": r"orchestrat",
    "subagent": r"sub-?agent",
    "claude.md": r"claude\.md",
}
# Path names that must never exist in the staged tree whatever their content.
STRICT_PATHNAME_TERMS = {
    "handover-filename": r"handover",
}
# Words that are never treated as project/user identifiers when they occur as
# a component of the output, repository or working path.
GENERIC_PATH_WORDS = {
    "home", "tmp", "var", "usr", "run", "user", "opt", "srv", "mnt", "media", "root",
    "workspace", "workspaces", "projects", "output", "outputs", "results", "work", "code",
    "src", "data", "repos", "repo", "git", "local", "share", "lib", "bin", "etc", "dev",
    ".claude", ".git", "worktrees",
}
MIN_CLAUDE_VERSION = (2, 1, 292)
DEFAULT_STAGE_ROOT_NAME = "pgrade"
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

_GLOB_CHARS = set("*?[")


def _glob_to_regex(pat: str) -> "re.Pattern":
    out, i = [], 0
    while i < len(pat):
        c = pat[i]
        if pat.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pat.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("".join(out))


_PATTERN_CACHE: dict = {}


def match_strip_pattern(relpath: str, pattern: str) -> bool:
    """True if a repo-relative POSIX path is selected by one strip pattern.

    Patterns are root-relative. A plain path selects that file or everything
    below that directory. `*` matches within one path component, `**` across
    components (`**/name` matches `name` at any depth). A pattern also selects
    a path if it selects any leading directory of it.
    """
    pat = pattern.strip().strip("/")
    if not pat:
        return False
    rx = _PATTERN_CACHE.get(pat)
    if rx is None:
        rx = _PATTERN_CACHE[pat] = _glob_to_regex(pat)
    parts = PurePosixPath(relpath).parts
    for n in range(1, len(parts) + 1):
        if rx.fullmatch("/".join(parts[:n])):
            return True
    return False


def parse_strip_list(text: str):
    """Strip-list file: one root-relative path or glob per line; `#` comments."""
    pats = []
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].strip()
        if line and not line.startswith("#"):
            pats.append(line)
    return pats


def load_strip_list(path) -> list:
    return parse_strip_list(Path(path).read_text(encoding="utf-8"))


def is_stripped(relpath: str, extra_prefixes=()) -> bool:
    """True if a repo-relative POSIX path must not reach the reviewers.

    extra_prefixes: repo-specific strip patterns (see match_strip_pattern).
    """
    p = PurePosixPath(relpath)
    parts = p.parts
    if any(part in STRIP_COMPONENTS for part in parts):
        return True
    if p.name in STRIP_BASENAMES:
        return True
    if p.name == ".env" or (p.name.startswith(".env.") and not p.name.endswith(".example")):
        return True
    for prefix in tuple(DEFAULT_STRIP_PREFIXES) + tuple(extra_prefixes):
        if match_strip_pattern(relpath, prefix):
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
        pre = prefix.strip().strip("/")
        if pre and not (_GLOB_CHARS & set(pre)):
            pats.append(re.compile(re.escape(pre) + r"(?:/[^\s)`'\"\]]*)?"))
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
    pattern_hits = {pat: 0 for pat in extra_prefixes}
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
            if m.isfile():
                for pat in pattern_hits:
                    if match_strip_pattern(rel, pat):
                        pattern_hits[pat] += 1
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
            "stripped_sample": sorted(stripped)[:40], "skipped_symlinks_or_special": skipped_links,
            "strip_pattern_matches": pattern_hits,
            "strip_patterns_unmatched": sorted(k for k, v in pattern_hits.items() if v == 0)}


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


def neutral_id(label: str, sha: str, n: int = 10) -> str:
    """Opaque directory name made of letters only (a digit run could collide with a PR number)."""
    h = opaque_id(label, sha)
    return "".join("abcdefghijklmnop"[int(c, 16)] for c in h[:n])


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

def scan_blinding(stage_dir: Path, pr_number=None, leak_terms=(), extra_texts=None,
                  max_ambient_strict=None):
    """Scan everything a reviewer can read for leakage.

    Content falls in two classes.
    * Authored for this change: issue.md, diff.patch, the filled prompts and
      argv, the stage and working-directory paths (everything in `extra_texts`),
      and every file or directory name. STRICT hits abort; DOMAIN-AMBIGUOUS hits
      are warned about and counted.
    * Ambient: the post-merge source tree under after/. It is identical for every
      change in the repository; anything the change wrote also appears in
      diff.patch. Strict hits there are counted per term (and listed by file) but
      abort only for change-specific identifiers (branch name, --leak-term, a PR
      reference such as `#4742` or `PR 4742`); domain-ambiguous hits are counted.
      `max_ambient_strict` optionally makes a total of strict ambient hits above
      the limit abort too.

    extra_texts: {name: text} for everything else a reviewer receives.
    Returns a dict with `ok`, `strict_fail`, `warn_authored`, `ambient`
    ({"strict": ..., "domain_ambiguous": ...}) and `counts` per category.
    """
    ident = {}
    if pr_number is not None:
        ident["pr-number"] = re.compile(rf"(?<!\d){re.escape(str(pr_number))}(?!\d)")
    for t in leak_terms:
        if t:
            ident[f"leak:{t}"] = re.compile(re.escape(t), re.I)
    tree_ident = {k: v for k, v in ident.items() if k != "pr-number"}
    if pr_number is not None:
        n = re.escape(str(pr_number))
        tree_ident["pr-reference"] = re.compile(
            rf"(?:#|\bpull/|\bpr[ _-]?){n}(?!\d)|\bpull request {n}(?!\d)", re.I)
    strict_all = {k: re.compile(v, re.I) for k, v in STRICT_ALL_LINES.items()}
    strict_added = {k: re.compile(v, re.I) for k, v in STRICT_ADDED_LINES.items()}
    strict_name = {k: re.compile(v, re.I) for k, v in STRICT_PATHNAME_TERMS.items()}
    domain = {k: re.compile(v, re.I) for k, v in DOMAIN_AMBIGUOUS_TERMS.items()}

    strict_fail, warn_authored = [], []
    ambient = {"strict": {}, "domain_ambiguous": {}}
    warn_counts: dict = {}

    def note_ambient(cat: str, term: str, name: str):
        d = ambient[cat].setdefault(term, {"hits": 0, "files": {}})
        d["hits"] += 1
        d["files"][name] = d["files"].get(name, 0) + 1

    def fail(term, name, i, line):
        strict_fail.append({"term": term, "file": name, "line": i, "text": line.strip()[:160]})

    def scan_text(name: str, text: str):
        is_path = name.startswith("<path>")
        shown = name[len("<path>"):] if is_path else name
        in_tree = shown.startswith(TREE_WARN_ONLY_PREFIX)
        is_diff = name == "diff.patch"
        for i, line in enumerate(text.splitlines(), 1):
            if in_tree and not is_path:
                for term, pat in tree_ident.items():
                    if pat.search(line):
                        fail(term, name, i, line)
                for term, pat in {**strict_all, **strict_added}.items():
                    if pat.search(line):
                        note_ambient("strict", term, name)
                for term, pat in domain.items():
                    if pat.search(line):
                        note_ambient("domain_ambiguous", term, name)
                continue
            for term, pat in ident.items():
                if pat.search(line):
                    fail(term, name, i, line)
            for term, pat in strict_all.items():
                if pat.search(line):
                    fail(term, name, i, line)
            added_only_ok = (not is_diff) or (line.startswith("+") and not line.startswith("+++"))
            if is_path:
                for term, pat in {**strict_added, **strict_name}.items():
                    if pat.search(line):
                        fail(term, name, i, line)
            elif added_only_ok:
                for term, pat in strict_added.items():
                    if pat.search(line):
                        fail(term, name, i, line)
            if is_path and in_tree:
                for term, pat in domain.items():
                    if pat.search(line):
                        note_ambient("domain_ambiguous", term, name)
            elif added_only_ok and not name.endswith(":argv>"):  # argv is the runner's own constants
                for term, pat in domain.items():
                    if pat.search(line):
                        warn_counts[term] = warn_counts.get(term, 0) + 1
                        if len(warn_authored) < 50:
                            warn_authored.append({"term": term, "file": name, "line": i,
                                                  "text": line.strip()[:160]})

    for dirpath, _dn, filenames in os.walk(stage_dir):
        for fn in filenames:
            p = Path(dirpath) / fn
            rel = p.relative_to(stage_dir).as_posix()
            scan_text(rel, p.read_bytes().decode("utf-8", "ignore"))
            scan_text(f"<path>{rel}", rel)  # file and directory names count too
    for name, text in (extra_texts or {}).items():
        scan_text(name if name.startswith("<") else f"<prompt>{name}", text)
    for cat in ambient.values():
        for d in cat.values():  # keep lists compact
            d["files"] = dict(sorted(d["files"].items(), key=lambda kv: -kv[1])[:6])
    counts = {
        "strict_fail": len(strict_fail),
        "warn_authored": sum(warn_counts.values()),
        "warn_authored_by_term": dict(sorted(warn_counts.items())),
        "ambient_strict": sum(d["hits"] for d in ambient["strict"].values()),
        "ambient_strict_by_term": {k: v["hits"] for k, v in sorted(ambient["strict"].items())},
        "ambient_domain_ambiguous": sum(d["hits"] for d in ambient["domain_ambiguous"].values()),
        "ambient_domain_ambiguous_by_term": {k: v["hits"] for k, v in
                                             sorted(ambient["domain_ambiguous"].items())},
    }
    over_limit = max_ambient_strict is not None and counts["ambient_strict"] > max_ambient_strict
    return {"strict_fail": strict_fail, "warn_authored": warn_authored, "ambient": ambient,
            "counts": counts, "max_ambient_strict": max_ambient_strict,
            "ambient_strict_over_limit": over_limit,
            "ok": not strict_fail and not over_limit}


def derive_leak_terms(*paths, extra=()):
    """Identifier words that must never reach a reviewer: the user name, the home
    directory name, and every non-generic component of the given paths (output,
    repository, runner and working directories). Returns (core, derived): `core`
    (user and home names, `.scratch`) is checked everywhere, `derived` (path
    components and any extra terms) on everything the runner itself composes.
    """
    core = {".scratch"}
    for who in (os.environ.get("USER"), os.environ.get("LOGNAME"), Path.home().name):
        if who and who.lower() not in GENERIC_PATH_WORDS:
            core.add(who)
    try:
        import getpass
        core.add(getpass.getuser())
    except Exception:  # noqa: BLE001
        pass
    derived = set()
    for pth in paths:
        for part in Path(str(pth)).parts:
            low = part.lower().strip("/")
            if len(low) >= 5 and low not in GENERIC_PATH_WORDS and not low.isdigit() \
                    and not re.fullmatch(r"[0-9a-f]{6,}", low):
                derived.add(part)
    derived |= {t for t in extra if t}
    core = {t for t in core if t and len(t) >= 3}
    return sorted(core), sorted(derived - set(core))


def scan_reviewer_inputs(fields: dict, core_terms=(), derived_terms=(), soft_fields=()):
    """Case-insensitive scan of everything a reviewer is handed: filled prompts,
    argv (minus the executable), stage and working-directory paths, PWD.

    fields: {name: text}. soft_fields: names checked against core terms only
    (reviewer-authored text such as a claim, where a path word may be ordinary
    prose). Core terms match as substrings, derived terms as whole tokens. Returns a list of {"term", "field"} hits.
    """
    hits = []
    for name, text in fields.items():
        low = (text or "").lower()
        for t in core_terms:  # user name, `.scratch`: any substring counts
            if t.lower() in low:
                hits.append({"term": t, "field": name})
        if name in soft_fields:
            continue
        for t in derived_terms:  # project and path words: whole tokens only ("fixtures" is not "fixture")
            if re.search(rf"(?<![a-z0-9]){re.escape(t.lower())}(?![a-z0-9])", low):
                hits.append({"term": t, "field": name})
    return hits


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

ASSESSABLE_STATUSES = ("met", "partial", "not_met")
LOW_CONFIDENCE_FRACTION = 0.8
LOW_CONFIDENCE_CAP = 4


def assessable_fraction(ac_statuses) -> float:
    """Assessable ACs (met, partial, not_met) over all ACs; 0.0 when there are no ACs."""
    ac = list(ac_statuses)
    if not ac:
        return 0.0
    return round(sum(1 for a in ac if a in ASSESSABLE_STATUSES) / len(ac), 4)


def grade_details(ac_statuses, severity_counts, test_rating, scope_significances,
                  unresolved_severe=0):
    """Deterministic 1-5 grade with its caps. Inputs are already verified/discarded.

    ac_statuses: iterable of met/partial/not_met/not_assessable
    severity_counts: {"blocker": n, "major": n, "minor": n}
    unresolved_severe: blocker/major findings the verifier could not resolve
        (unverifiable or not verified). They are not counted as defects, but
        they stop the grade rising above 4 and flag low confidence.

    The grade is the minimum of every cap that applies (rubric.md):
      blockers/not_met: 2+ blockers, or a blocker with a not_met AC, or 3+ not_met -> 1;
                        exactly one blocker -> 2; two not_met -> 2; one not_met -> 3
      3+ major or 2+ partial -> 2; 2 major, 1 partial or inadequate tests -> 3
      1 major, partial tests or significant unrequested scope -> 4
      assessable_fraction < 0.8 (or no ACs), or an unresolved blocker/major -> 4
      otherwise 5
    """
    ac = list(ac_statuses)
    blockers = severity_counts.get("blocker", 0)
    majors = severity_counts.get("major", 0)
    not_met = ac.count("not_met")
    partial = ac.count("partial")
    frac = assessable_fraction(ac)
    caps = []

    if blockers >= 2 or (blockers >= 1 and not_met >= 1) or not_met >= 3:
        caps.append((1, "blockers/not_met"))
    elif blockers == 1 or not_met == 2:
        caps.append((2, "one blocker or two not_met ACs"))
    elif not_met == 1:
        caps.append((3, "one not_met AC without a blocker"))
    if majors >= 3 or partial >= 2:
        caps.append((2, "three majors or two partial ACs"))
    if majors == 2 or partial == 1 or test_rating == "inadequate":
        caps.append((3, "two majors, one partial AC or inadequate tests"))
    if majors == 1 or test_rating == "partial" or "significant" in list(scope_significances):
        caps.append((4, "one major, partial tests or significant unrequested scope"))
    low_confidence = frac < LOW_CONFIDENCE_FRACTION
    if low_confidence:
        caps.append((LOW_CONFIDENCE_CAP, f"assessable_fraction {frac} < {LOW_CONFIDENCE_FRACTION}"))
    if unresolved_severe:
        low_confidence = True
        caps.append((LOW_CONFIDENCE_CAP, "unresolved blocker/major claim"))
    grade = min([c for c, _ in caps] + [5])
    return {"grade": grade, "assessable_fraction": frac, "low_confidence": low_confidence,
            "caps": [f"{c}: {why}" for c, why in caps if c == grade]}


def compute_grade(ac_statuses, severity_counts, test_rating, scope_significances,
                  unresolved_severe=0):
    return grade_details(ac_statuses, severity_counts, test_rating, scope_significances,
                         unresolved_severe)["grade"]


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

    Claims the verifier could not resolve (`unverifiable`) or that were never
    verified (`not_verified`: failed run or over the cap) are counted in
    `unresolved_claims`; they never silently raise the grade (see grade_details).
    """
    verified = {s: 0 for s in SEVERITIES}
    reported_unverified_minor = 0
    discarded = []
    unresolved = {"unverifiable": 0, "not_verified": 0}
    unresolved_severe = 0
    for f in review["findings"]:
        key = claim_key("finding", f["id"])
        if f["severity"] == "minor":
            reported_unverified_minor += 1
            continue
        v = verifications.get(key)
        if v is None:
            discarded.append({"id": f["id"], "severity": f["severity"], "reason": "not_verified"})
            unresolved["not_verified"] += 1
            unresolved_severe += 1
        elif v["verdict"] == "confirmed" and v["confirmed_severity"] in SEVERITIES:
            verified[v["confirmed_severity"]] += 1
        elif v["verdict"] == "confirmed":
            discarded.append({"id": f["id"], "severity": f["severity"], "reason": "confirmed_as_not_a_defect"})
        else:
            reason = v["verdict"] + ("_needs_execution" if v.get("needs_execution") else "")
            discarded.append({"id": f["id"], "severity": f["severity"], "reason": reason})
            if v["verdict"] == "unverifiable":
                unresolved["unverifiable"] += 1
                unresolved_severe += 1
    eff_ac = []
    for a in review["acs"]:
        st = a["status"]
        if st in ("partial", "not_met"):
            v = verifications.get(claim_key("ac", a["id"]))
            if v is None or v["verdict"] == "unverifiable":
                st_eff = "not_assessable"
                unresolved["not_verified" if v is None else "unverifiable"] += 1
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
    gd = grade_details(eff_ac, verified, review["test_adequacy"]["rating"], scope, unresolved_severe)
    return {
        "grade": gd["grade"],
        "assessable_fraction": gd["assessable_fraction"],
        "low_confidence": gd["low_confidence"],
        "grade_caps": gd["caps"],
        "unresolved_claims": unresolved["unverifiable"] + unresolved["not_verified"],
        "unresolved_breakdown": unresolved,
        "unresolved_severe_findings": unresolved_severe,
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
    fracs = [r["assessable_fraction"] for r in valid]
    med_frac = round(float(statistics.median(fracs)), 4) if fracs else None
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
        "assessable_fraction": med_frac,
        "per_reviewer_assessable_fraction": [r["assessable_fraction"] if r else None
                                             for r in per_reviewer],
        "low_confidence": bool(valid) and (med_frac < LOW_CONFIDENCE_FRACTION
                                           or any(r["low_confidence"] for r in valid)),
        "unresolved_claims": [r["unresolved_claims"] if r else None for r in per_reviewer],
        "unresolved_claims_total": sum(r["unresolved_claims"] for r in valid),
    }


TABLE_COLUMNS = [
    "label", "issue", "merge_sha", "grade", "reviewer_grades", "reviewer_reported_grades",
    "verified_blocker", "verified_major", "verified_minor_reported",
    "discarded_blocker_major", "acs_met", "assessable_fraction", "unresolved_claims",
    "low_confidence", "n_valid_reviewers", "model", "cli_version", "graded_at",
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
        "assessable_fraction": agg["assessable_fraction"],
        "unresolved_claims": "|".join("-" if u is None else str(u) for u in agg["unresolved_claims"]),
        "low_confidence": agg["low_confidence"],
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


class GraderError(RuntimeError):
    """Base class for refusals that must stop a run with a clear message."""
    exit_code = 4


class LeakError(GraderError):
    exit_code = 3


class StaleResultError(GraderError):
    exit_code = 4


def parse_version(text: str):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(x) for x in m.groups()) if m else None


def check_cli(claude: str, help_text=None, version_text=None) -> dict:
    """Static preflight: minimum CLI version and the `--restricted` flag in --help.

    help_text/version_text may be passed in (tests); otherwise the CLI is asked.
    """
    if version_text is None:
        version_text = claude_version(claude)
    if help_text is None:
        r = subprocess.run([claude, "--help"], capture_output=True, text=True, timeout=60)
        help_text = r.stdout + r.stderr
    ver = parse_version(version_text)
    problems = []
    if ver is None:
        problems.append(f"cannot parse a version from {version_text!r}")
    elif ver < MIN_CLAUDE_VERSION:
        problems.append("claude CLI " + ".".join(map(str, ver)) + " is older than the minimum "
                        + ".".join(map(str, MIN_CLAUDE_VERSION)))
    has_restricted = re.search(r"(?m)^\s+--restricted\b", help_text or "") is not None
    if not has_restricted:
        problems.append("`--restricted` is not listed in `claude --help`; without it the file tools "
                        "are not confined to the staged inputs")
    return {"version": version_text, "min_version": ".".join(map(str, MIN_CLAUDE_VERSION)),
            "restricted_flag": has_restricted, "problems": problems, "ok": not problems}


CONTEXT_PROBE_TASK = (
    "Do not read any files. Quote verbatim, from everything in your context (system prompt, "
    "environment or working-directory information, any memory, account or settings text), every "
    "absolute path, directory name, user name, e-mail address, host name, project name or "
    "repository name you can see, other than the paths {stage}/issue.md, {stage}/diff.patch and "
    "{stage}/after. List them as lines; write NONE if there are none.")


def judge_context_probe(result_text: str, core_terms) -> list:
    """Identifying core terms (user name, `.scratch`) a model reports seeing in its own context."""
    low = (result_text or "").lower()
    return sorted(t for t in core_terms if t and t.lower() in low)


def judge_read_probe(result_text: str, inside_canary: str, outside_canary: str):
    """A Read inside the stage must return its canary; a Read outside must not."""
    text = result_text or ""
    problems = []
    if inside_canary not in text:
        problems.append("the read inside the staged directory did not return its contents")
    if outside_canary in text:
        problems.append("a read OUTSIDE the staged directory returned its contents (not confined)")
    return problems


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


def child_env(cwd=None, config_dir=None) -> dict:
    """Environment for a reviewer. PWD is reset so the parent's directory is not inherited.

    config_dir: optional CLAUDE_CONFIG_DIR for a neutral account (see RUNBOOK, "Known residual leak").
    """
    env = dict(os.environ)
    if config_dir:
        env["CLAUDE_CONFIG_DIR"] = str(config_dir)
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    env.pop("OLDPWD", None)
    if cwd is not None:
        env["PWD"] = str(cwd)
    return env


def run_process(argv: list, cwd: Path, stdin_text: str, timeout: int, config_dir=None):
    """Run one child to completion in its own process group; kill the group on timeout."""
    start = time.time()
    proc = subprocess.Popen(argv, cwd=str(cwd), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, start_new_session=True,
                            env=child_env(cwd, config_dir))
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


def input_hashes(ctx: dict, system_prompt: str, user_prompt: str, schema: dict) -> dict:
    """Everything a stored result depends on. A resumed result must match all of it."""
    return {
        "prompt_sha256": sha256_bytes((system_prompt + "\0" + user_prompt).encode()),
        "inputs_manifest_sha256": ctx["manifest_sha256"],
        "model": ctx["model"], "effort": ctx["effort"],
        "schema_sha256": sha256_bytes(json.dumps(schema, sort_keys=True).encode()),
    }


def check_stored_result(stored: dict, current: dict, done: Path) -> None:
    """Refuse a stored result whose prompt or input hashes differ from the current run."""
    old = stored.get("input_hashes")
    if not isinstance(old, dict):
        raise StaleResultError(
            f"stale stored result {done}: it carries no input hashes (written by an older "
            f"version). Re-run with --no-resume, or delete the file, to regenerate it.")
    diffs = sorted(k for k in current if old.get(k) != current[k])
    if diffs:
        raise StaleResultError(
            f"stale stored result {done}: {', '.join(diffs)} changed since it was written "
            f"(stored {old.get('prompt_sha256', '?')[:12]} vs current {current['prompt_sha256'][:12]} "
            f"for the prompt). Refusing to reuse it. Re-run with --no-resume, or delete the "
            f"result file, to regenerate it.")


def reviewer_fields(argv: list, system_prompt: str, user_prompt: str, stage_dir, cwd, env: dict) -> dict:
    """Everything a reviewer process is handed that is not file content.

    argv[0] (the CLI executable) is not visible to the model and is excluded.
    """
    return {
        "argv": "\n".join(str(a) for a in argv[1:]),
        "system_prompt": system_prompt, "user_prompt": user_prompt,
        "stage_dir": str(stage_dir), "cwd": str(cwd), "env_PWD": env.get("PWD", ""),
    }


def execute_role(role: str, run_dir: Path, ctx: dict, system_prompt: str, user_prompt: str,
                 schema: dict) -> dict:
    """One reviewer or verifier run with a single retry on bad output.

    Returns {"ok": bool, "parsed": dict|None, "usage": dict, "attempts": n, "seconds": s}.
    Resumable: a stored result.json short-circuits, but only if its prompt and
    input hashes match this run (else StaleResultError).
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    done = run_dir / "result.json"
    argv = build_argv(ctx["claude"], ctx["model"], ctx["effort"], system_prompt, ctx["stage_dir"],
                      ctx["max_budget_usd"])
    cwd = ctx["cwd"]
    hashes = input_hashes(ctx, system_prompt, user_prompt, schema)
    fields = reviewer_fields(argv, system_prompt, user_prompt, ctx["stage_dir"], cwd, child_env(cwd))
    soft = ("user_prompt",) if role.startswith("verifier") else ()
    leaks = scan_reviewer_inputs(fields, ctx.get("leak_core", ()), ctx.get("leak_derived", ()), soft)
    if leaks:
        raise LeakError(f"{role}: identifying terms in what the reviewer would receive: {leaks}")
    if ctx["resume"] and done.exists():
        stored = json.loads(done.read_text())
        check_stored_result(stored, hashes, done)
        return stored
    (run_dir / "system_prompt.txt").write_text(system_prompt, encoding="utf-8")
    (run_dir / "user_prompt.txt").write_text(user_prompt, encoding="utf-8")
    shown = list(argv)
    shown[shown.index("--system-prompt") + 1] = f"<system_prompt.txt sha256={sha256_bytes(system_prompt.encode())[:16]}>"
    entries = sorted(os.listdir(cwd))
    if entries:
        raise RuntimeError(f"neutral cwd {cwd} is not empty: {entries}")
    received = {
        "role": role, "argv": shown, "cwd": str(cwd), "cwd_entries": entries,
        "env_PWD": child_env(cwd)["PWD"],
        "add_dir": str(ctx["stage_dir"]),
        "add_dir_top_level": sorted(os.listdir(ctx["stage_dir"])),
        "add_dir_file_count": ctx["manifest_file_count"],
        "inputs_manifest_sha256": ctx["manifest_sha256"],
        "tools": READONLY_TOOLS.split(","),
        "settings_json": json.loads(SETTINGS_JSON),
        "env_overrides": {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "PWD": str(cwd)},
        "system_prompt_sha256": sha256_bytes(system_prompt.encode()),
        "stdin_sha256": sha256_bytes(user_prompt.encode()),
        "stdin_is_file": "user_prompt.txt",
        "leak_scan": {"core_terms": len(ctx.get("leak_core", ())),
                      "derived_terms": len(ctx.get("leak_derived", ())), "hits": leaks},
        "input_hashes": hashes,
    }
    (run_dir / "received.json").write_text(json.dumps(received, indent=2), encoding="utf-8")

    total_usage: dict = {}
    parsed = None
    t0 = time.time()
    attempts = 0
    errors: list = []
    for attempt in (1, 2):
        attempts = attempt
        r = run_process(argv, cwd, user_prompt, ctx["timeout"], ctx.get("config_dir"))
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
              "attempts": attempts, "seconds": round(time.time() - t0, 1), "errors": errors,
              "input_hashes": hashes}
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


def default_stage_root() -> Path:
    return Path(f"/run/user/{os.getuid()}") / DEFAULT_STAGE_ROOT_NAME


def resolve_stage_root(arg, out: Path, repo_path, leak_terms=()):
    """Neutral, user-private directory for the staged inputs and working directories.

    Default /run/user/<uid>/pgrade (uid, not user name). It must exist (or be
    creatable), be writable, and contain no user, project or output-path word.
    Returns (root, core_terms, derived_terms).
    """
    if arg:
        root = Path(arg)
    else:
        root = default_stage_root()
        if not root.parent.is_dir():
            raise GraderError(f"{root.parent} does not exist; pass --stage-root with a neutral, "
                              f"writable absolute path that holds no user, project or arm words")
    if not root.is_absolute():
        raise GraderError(f"--stage-root must be absolute: {root}")
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    if not (os.access(root, os.W_OK) and os.access(root, os.X_OK)):
        raise GraderError(f"stage root {root} is not writable")
    core, derived = derive_leak_terms(out, repo_path, extra=leak_terms)
    hits = scan_reviewer_inputs({"stage_root": str(root)}, core, derived)
    if hits:
        raise LeakError(f"stage root {root} contains identifying terms: {hits}. "
                        f"Choose a neutral --stage-root.")
    return root, core, derived


def filled_prompts(prompts: dict, stage_dir: Path) -> dict:
    """The prompts exactly as a reviewer and a verifier are handed them (placeholder claim)."""
    paths = dict(ISSUE_PATH=str(stage_dir / "issue.md"), DIFF_PATH=str(stage_dir / "diff.patch"),
                 TREE_PATH=str(stage_dir / "after"))
    return {
        "reviewer_system": prompts["reviewer_system"],
        "reviewer_task": fill(prompts["reviewer_task"], **paths),
        "verifier_system": prompts["verifier_system"],
        "verifier_task": fill(prompts["verifier_task"], CLAIM_JSON='{"type": "finding"}', **paths),
    }


def do_stage(args, out: Path, prompts: dict):
    label = args.label
    sid = neutral_id(label, args.merge_commit)
    pr_dir = out / label
    pr_dir.mkdir(parents=True, exist_ok=True)
    root, core, derived = resolve_stage_root(getattr(args, "stage_root", None), out,
                                             args.repo_path, args.leak_term or [])
    work = root / sid
    stage_dir = work / "in"
    cwd = work / "cwd"
    if args.issue_file:
        raw = Path(args.issue_file).read_text(encoding="utf-8")
        title, _, body = raw.partition("\n")
        title = title.lstrip("# ").strip()
    else:
        title, body = fetch_issue(args.gh_repo, args.issue)
    extra = list(args.strip_prefix or [])
    if getattr(args, "strip_list", None):
        extra += load_strip_list(args.strip_list)
    extra = tuple(dict.fromkeys(extra))
    manifest = stage_inputs(Path(args.repo_path), args.merge_commit, title, body, stage_dir, extra)
    if cwd.exists():
        shutil.rmtree(cwd)
    cwd.mkdir(parents=True)
    manifest["label"] = label
    manifest["stage_dir"] = str(stage_dir)
    manifest["cwd"] = str(cwd)
    manifest["opaque_id"] = sid
    manifest["strip_list_file"] = getattr(args, "strip_list", None)
    leak = list(args.leak_term or [])
    if getattr(args, "branch", None):
        leak.append(args.branch)
    filled = filled_prompts(prompts, stage_dir)
    argv = build_argv("claude", getattr(args, "model", "opus"), getattr(args, "effort", "high"),
                      filled["reviewer_system"], stage_dir, getattr(args, "max_budget_usd", 15.0))
    fields = reviewer_fields(argv, filled["reviewer_system"], filled["reviewer_task"], stage_dir, cwd,
                             child_env(cwd))
    vfields = reviewer_fields(argv, filled["verifier_system"], filled["verifier_task"], stage_dir, cwd,
                              child_env(cwd))
    extra_texts = {f"<{role}:{k}>": v for role, f in (("reviewer", fields), ("verifier", vfields))
                   for k, v in f.items()}
    scan = scan_blinding(stage_dir, pr_number=args.pr_number, leak_terms=leak,
                         extra_texts=extra_texts,
                         max_ambient_strict=getattr(args, "max_ambient_strict", None))
    rhits = scan_reviewer_inputs({f"{r}:{k}": v for r, f in (("reviewer", fields), ("verifier", vfields))
                                  for k, v in f.items()},
                                 core, sorted(set(derived) | set(leak)))
    scan["reviewer_input_hits"] = rhits
    scan["reviewer_input_terms"] = {"core": core, "derived": derived}
    scan["ok"] = scan["ok"] and not rhits
    manifest["blinding_scan"] = scan
    manifest["leak_core"], manifest["leak_derived"] = core, sorted(set(derived) | set(leak))
    (pr_dir / "inputs_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest, stage_dir, cwd, scan, title


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
    cli = check_cli(claude, version_text=version)
    if not cli["ok"]:
        log("claude CLI preflight FAILED: " + "; ".join(cli["problems"]))
        return 5
    manifest, stage_dir, cwd, scan, title = do_stage(args, out, prompts)
    counts = scan["counts"]
    log(f"staged {manifest['tree']['files']} files; strict hits={counts['strict_fail']} "
        f"reviewer-input hits={len(scan['reviewer_input_hits'])} "
        f"ambient strict={counts['ambient_strict']} ambient domain-ambiguous="
        f"{counts['ambient_domain_ambiguous']} authored warnings={counts['warn_authored']}")
    if not scan["ok"] and not args.ignore_scan:
        log("blinding scan FAILED; see inputs_manifest.json. Aborting before any model call.")
        return 3
    pr_dir = out / args.label
    ctx = {
        "claude": claude, "model": args.model, "effort": args.effort, "stage_dir": stage_dir,
        "cwd": cwd, "timeout": args.timeout, "max_budget_usd": args.max_budget_usd,
        "resume": not args.no_resume, "parallel": args.parallel,
        "manifest_file_count": len(manifest["files"]), "manifest_sha256": manifest["files_sha256"],
        "leak_core": manifest["leak_core"], "leak_derived": manifest["leak_derived"],
        "config_dir": args.config_dir,
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

    try:
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
                f"assessable_fraction={per_reviewer[-1]['assessable_fraction']} "
                f"unresolved={per_reviewer[-1]['unresolved_claims']} "
                f"verified={per_reviewer[-1]['verified']}")
    except GraderError as e:
        log(f"REFUSED: {e}")
        return e.exit_code
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
        "blinding_counts": scan["counts"],
        "inputs_manifest_sha256": manifest["files_sha256"],
    }
    (pr_dir / "grade.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    row = table_row(result)
    write_table([row], pr_dir / "row.csv", pr_dir / "row.md")
    log(f"grade={agg['grade']} assessable_fraction={agg['assessable_fraction']} "
        f"low_confidence={agg['low_confidence']} reviewers={agg['per_reviewer_grades']} "
        f"-> {pr_dir / 'grade.json'}")
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
    try:
        manifest, stage_dir, cwd, scan, _t = do_stage(args, out, prompts)
    except GraderError as e:
        print(f"REFUSED: {e}")
        return e.exit_code
    print(json.dumps({"stage_dir": str(stage_dir), "cwd": str(cwd),
                      "files": manifest["tree"]["files"],
                      "stripped_files": manifest["tree"]["stripped_files"],
                      "strip_patterns_unmatched": manifest["tree"]["strip_patterns_unmatched"],
                      "scan_ok": scan["ok"], "counts": scan["counts"],
                      "strict_fail": scan["strict_fail"][:10],
                      "reviewer_input_hits": scan["reviewer_input_hits"][:10],
                      "warn_authored": scan["warn_authored"][:10],
                      "ambient": scan["ambient"]}, indent=2))
    return 0 if scan["ok"] else 3


def do_preflight(args):
    """CLI version, `--restricted` in --help, and (unless --no-live) a live probe that a
    Read inside the staged directory works and a Read outside it is refused."""
    claude = find_claude(args.claude)
    cli = check_cli(claude)
    print(json.dumps({"claude": claude, **cli}, indent=2))
    problems = list(cli["problems"])
    if not args.no_live and cli["ok"]:
        out = Path(args.out).resolve() if args.out else Path.cwd()
        root, core, derived = resolve_stage_root(args.stage_root, out, out)
        work = root / ("probe" + "".join(random.choice("abcdefghijklmnop") for _ in range(8)))
        inside, outside, cwd = work / "in", work / "outside", work / "cwd"
        for d in (inside, outside, cwd):
            d.mkdir(parents=True)
        in_canary = "IN" + "".join(random.choice("abcdefghijklmnop") for _ in range(16))
        out_canary = "OUT" + "".join(random.choice("abcdefghijklmnop") for _ in range(16))
        (inside / "inside.txt").write_text(in_canary + "\n")
        (outside / "outside.txt").write_text(out_canary + "\n")
        system = ("You are a file-reading probe. Use only the Read tool. Never guess file contents.")
        task = (f"Read the file {inside / 'inside.txt'} and the file {outside / 'outside.txt'}. "
                f"Reply with exactly two lines: `INSIDE=<exact file contents, or REFUSED>` and "
                f"`OUTSIDE=<exact file contents, or REFUSED>`.")
        argv = build_argv(claude, args.model, "low", system, inside, 1.0)
        r = run_process(argv, cwd, task, args.timeout, args.config_dir)
        ev = parse_cli_json(r["stdout"])
        text = (ev or {}).get("result") or ""
        probe_problems = judge_read_probe(text, in_canary, out_canary)
        if ev is None or ev.get("is_error"):
            probe_problems.append(f"probe run failed (rc={r['returncode']})")
        print(json.dumps({"live_probe": {"ok": not probe_problems, "problems": probe_problems,
                                         "seconds": r["seconds"],
                                         "cost_usd": (ev or {}).get("total_cost_usd")}}, indent=2))
        problems += probe_problems
        ctx_prompt = CONTEXT_PROBE_TASK.format(stage=inside)
        r2 = run_process(argv, cwd, ctx_prompt, args.timeout, args.config_dir)
        ev2 = parse_cli_json(r2["stdout"])
        seen = judge_context_probe((ev2 or {}).get("result"), core)
        print(json.dumps({"context_probe": {"identity_terms_seen_in_cli_context": seen,
                                            "run_ok": ev2 is not None and not ev2.get("is_error"),
                                            "cost_usd": (ev2 or {}).get("total_cost_usd")}}, indent=2))
        if seen:
            print("WARNING: the CLI itself puts identifying text (" + ", ".join(seen) + ") in the "
                  "reviewer's context (account e-mail block). The runner cannot remove it; use "
                  "--config-dir with a neutral account or accept and record it. See RUNBOOK.")
        make_tree_writable(work)
        shutil.rmtree(work, ignore_errors=True)
    print("PREFLIGHT " + ("OK" if not problems else "FAILED: " + "; ".join(problems)))
    return 0 if not problems else 5


def add_common(p):
    p.add_argument("--repo-path", required=True, help="local clone of the repository (read only)")
    p.add_argument("--merge-commit", required=True, help="merge (squash) commit sha")
    p.add_argument("--label", required=True,
                   help="output sub-directory name; never shown to reviewers")
    p.add_argument("--issue", type=int, help="linked issue number")
    p.add_argument("--gh-repo", help="owner/name for `gh issue view` (read only)")
    p.add_argument("--issue-file", help="offline alternative: first line is the title, rest the body")
    p.add_argument("--pr-number", type=int, help="used only for the leakage scan")
    p.add_argument("--branch", help="PR branch name; used only for the leakage scan")
    p.add_argument("--leak-term", action="append", help="extra literal term to scan for (e.g. a commit-subject phrase)")
    p.add_argument("--strip-prefix", action="append",
                   help="extra repo-relative path or glob to strip (repeatable)")
    p.add_argument("--strip-list", help="file of repo-specific strip patterns, one per line, `#` comments "
                                        "(see strip-list.example.txt)")
    p.add_argument("--max-ambient-strict", type=int, default=None,
                   help="abort if strict terms hit more than N times in the unchanged tree")
    p.add_argument("--stage-root", help="neutral absolute directory for staged inputs and working "
                                        "directories (default /run/user/<uid>/pgrade); must hold no user, "
                                        "project or arm words")
    p.add_argument("--out", required=True,
                   help="output directory (the only other place written to; never shown to reviewers)")


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
    g.add_argument("--config-dir", help="CLAUDE_CONFIG_DIR for the reviewers: a neutral account's "
                                        "configuration (see RUNBOOK, Known residual leak)")
    g.add_argument("--no-resume", action="store_true")
    g.add_argument("--ignore-scan", action="store_true", help="continue despite a failed blinding scan")
    g.set_defaults(fn=do_grade)
    t = sub.add_parser("table", help="merge grade.json files into one table")
    t.add_argument("grade_json", nargs="+")
    t.add_argument("--csv", required=True)
    t.add_argument("--md", required=True)
    t.set_defaults(fn=do_table)
    pf = sub.add_parser("preflight", help="check CLI version, --restricted, and that a Read outside "
                                          "the staged directory is refused")
    pf.add_argument("--claude", help="absolute path to the claude CLI")
    pf.add_argument("--stage-root", help="neutral absolute directory (default /run/user/<uid>/pgrade)")
    pf.add_argument("--out", help="only used to derive identifying words checked in the stage root")
    pf.add_argument("--config-dir", help="CLAUDE_CONFIG_DIR to probe (as passed to grade)")
    pf.add_argument("--model", default="haiku")
    pf.add_argument("--timeout", type=int, default=300)
    pf.add_argument("--no-live", action="store_true", help="skip the (small) live model probe")
    pf.set_defaults(fn=do_preflight)
    args = ap.parse_args(argv)
    if args.cmd in ("stage", "grade") and not (args.issue_file or (args.gh_repo and args.issue)):
        ap.error("give --issue-file, or --gh-repo with --issue")
    try:
        return args.fn(args)
    except GraderError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return e.exit_code


if __name__ == "__main__":
    sys.exit(main())
