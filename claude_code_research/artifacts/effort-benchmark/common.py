"""Shared helpers for the reviewer-quality-vs-effort harness. Python 3 stdlib only."""
import glob, json, os, re, signal, subprocess, sys, time, tempfile
import limits
import reconstruct

ROOT = os.path.dirname(os.path.abspath(__file__))
CWD = os.path.join(ROOT, "cwd")          # clean, empty working dir (own git root, no CLAUDE.md)
RUNS = os.path.join(ROOT, "runs")
JUDGMENTS = os.path.join(ROOT, "judgments")
LOGS = os.path.join(ROOT, "logs")
INPUTS = os.path.join(ROOT, "inputs")
SCHEDULE = os.path.join(ROOT, "schedule.json")

OPUS, SONNET = "claude-opus-5-5", "claude-sonnet-5"
# arm name -> (model id, effort). Baseline (cheapest) arm per model listed in BASELINE.
ARMS = {
    "opus-medium":   (OPUS, "medium"),
    "opus-high":     (OPUS, "high"),
    "opus-xhigh":    (OPUS, "xhigh"),
    "opus-max":      (OPUS, "max"),
    "sonnet-medium": (SONNET, "medium"),
    "sonnet-high":   (SONNET, "high"),
    "sonnet-xhigh":  (SONNET, "xhigh"),
    "sonnet-max":    (SONNET, "max"),
}
BASELINE = {"opus": "opus-medium", "sonnet": "sonnet-medium"}
# Follow-up cells (2026-09-25 max-effort diagnosis). Kept OUT of ARMS on purpose: analyze.py/analysis2.py/make_schedule.py iterate
# ARMS, so adding them there would change the overnight analysis. Definitions only; nothing here is run automatically.
# Spec keys: model, effort, budget (USD per review call), prompt_variant, max_output_tokens.
EXTRA_ARMS = {
    "opus-5-5-max-cap10": {"model": "claude-opus-5-5", "effort": "max", "budget": "4.5", "prompt_variant": "cap10", "max_output_tokens": "128000"},
    "sonnet-5-max-cap10": {"model": "claude-sonnet-5", "effort": "max", "budget": "4.5", "prompt_variant": "cap10", "max_output_tokens": "128000"},
    "opus-5-max":         {"model": "claude-opus-5",   "effort": "max", "budget": "4.5", "prompt_variant": None,    "max_output_tokens": "128000"},
}
# Prompt variants: the default (None / "default") prompt is review_prompt.txt byte-for-byte; a variant only appends a line.
PROMPT_VARIANTS = {
    "default": "",
    "cap10": "List at most 10 findings, most important first, then stop.",
}
JUDGES = {
    "j-opus-medium":  (OPUS, "medium"),
    "j-sonnet-high":  (SONNET, "high"),
}
N_KEY = 13
MAX_OUTPUT_TOKENS = "128000"  # same cap for every arm (CC clamps to the model limit; 64000 was hit by max arms in smoke v1)
# Per-call spend guard (--max-budget-usd): a pass that hits a full max_tokens turn (~$2.9 Opus / ~$1.5 Sonnet at 128k)
# is stopped after that turn instead of CC auto-resuming for several more 64k-128k turns.
BUDGET_USD = {("review", OPUS): "2.8", ("review", SONNET): "1.4", ("judge", OPUS): "1.5", ("judge", SONNET): "0.75"}
BUDGET_ENV = "EFFORT_BUDGET_USD_REVIEW"   # env override for REVIEW calls only (precedence: flag/arg > env > arm spec > BUDGET_USD)


def arm_spec(arm):
    """Normalised spec for any defined arm (original ARMS or EXTRA_ARMS). Original arms keep the default budget/prompt."""
    if arm in ARMS:
        m, e = ARMS[arm]
        return {"model": m, "effort": e, "budget": None, "prompt_variant": None, "max_output_tokens": None}
    if arm in EXTRA_ARMS:
        return dict(EXTRA_ARMS[arm])
    raise KeyError(arm)


def all_arm_names():
    return list(ARMS) + list(EXTRA_ARMS)


def resolve_budget(role, model, override=None, arm_budget=None):
    if override:
        return str(override)
    if role == "review" and os.environ.get(BUDGET_ENV):
        return os.environ[BUDGET_ENV]
    if arm_budget:
        return str(arm_budget)
    return BUDGET_USD[(role, model)]


def build_review_prompt(variant=None):
    """review_prompt.txt unchanged for the default; a variant appends its line after the document."""
    base = open(os.path.join(INPUTS, "review_prompt.txt")).read()
    if variant in (None, "", "default"):
        return base
    return base.rstrip("\n") + "\n\n" + PROMPT_VARIANTS[variant] + "\n"

# Env vars inherited from a parent Claude Code session that must not reach the child.
STRIP_ENV = ["CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_MESSAGING_SOCKET",
             "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_CODE_BRIDGE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
             "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_SESSION_ATTENDED", "CLAUDE_EFFORT", "AI_AGENT",
             "CLAUDE_PID", "CLAUDE_CODE_EXECPATH", "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE",
             "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH", "CLAUDE_CODE_EFFORT_LEVEL"]

# Isolation flags. NOT --bare: --bare never reads OAuth/keychain, so subscription auth fails ("Not logged in").
ISOLATION_FLAGS = ["--setting-sources", "", "--tools", "", "--strict-mcp-config",
                   "--disable-slash-commands"]


def log(msg, path=None):
    line = time.strftime("%Y-%m-%d %H:%M:%S") + " " + msg
    print(line, flush=True)
    os.makedirs(os.path.dirname(path or os.path.join(LOGS, "harness.log")), exist_ok=True)
    with open(path or os.path.join(LOGS, "harness.log"), "a") as f:
        f.write(line + "\n")


def atomic_write(path, text):
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def child_env(max_output_tokens=None):
    env = {k: v for k, v in os.environ.items() if k not in STRIP_ENV}
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(max_output_tokens or MAX_OUTPUT_TOKENS)
    return env


def ensure_cwd():
    os.makedirs(CWD, exist_ok=True)
    if not os.path.isdir(os.path.join(CWD, ".git")):
        subprocess.run(["git", "init", "-q", CWD], check=True)


def transcript_efforts(session_id):
    """Effort values recorded on the assistant lines of the session transcript (independent evidence)."""
    for p in glob.glob(os.path.expanduser("~/.claude/projects/*/%s.jsonl" % session_id)):
        vals = {}
        try:
            for l in open(p):
                try:
                    d = json.loads(l)
                except ValueError:
                    continue
                if d.get("type") == "assistant" and "effort" in d:
                    vals[str(d["effort"])] = vals.get(str(d["effort"]), 0) + 1
        except OSError:
            pass
        return {"path": p, "effort_counts": vals}
    return None


TIMEOUT_S = {"review": 2400, "judge": 900}   # review: 40 min wall clock per attempt
GATE = None   # limits.LimitGate, set by orchestrate.py; None => limit results just fail the call (single-run CLI use)


def call_claude(prompt, model, effort, role="review", timeout=None, budget=None, max_output_tokens=None, allow_partial=False):
    """One headless, tool-less, isolated call. Returns dict (never raises on CLI failure).
    allow_partial (review calls): when the run ends in a budget-guard stop / max_tokens / error subtype, the text is
    reconstructed from the events/transcript (reconstruct.py) and a usable partial review gets status 'truncated'
    (ok=True, flagged) instead of 'failed'. Judge calls never accept partial output."""
    ensure_cwd()
    timeout = timeout or TIMEOUT_S[role]
    budget = resolve_budget(role, model, budget)
    cmd = ["claude", "-p", "--model", model, "--effort", effort, "--output-format", "json"] + ISOLATION_FLAGS + ["--max-budget-usd", budget]
    t0_epoch = time.time()
    t0 = time.monotonic()
    timed_out = False
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            cwd=CWD, env=child_env(max_output_tokens), start_new_session=True)
    try:
        out, err = proc.communicate(prompt, timeout=timeout)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)     # kill the whole process group, not just the parent
        except OSError:
            pass
        try:
            out, err = proc.communicate(timeout=30)
        except Exception:
            out, err = "", ""
        rc, err = -9, (err or "") + "TIMEOUT after %ss (killed)" % timeout
    wall = time.monotonic() - t0
    res = {"cmd": cmd, "exit_code": rc, "wall_s": round(wall, 2), "stderr": err[-2000:], "ok": False, "timeout": timed_out,
           "budget_usd": budget, "max_output_tokens": str(max_output_tokens or MAX_OUTPUT_TOKENS), "status": "failed"}
    try:
        events = json.loads(out)
    except ValueError:
        res["error"] = "TIMEOUT (killed)" if timed_out else "unparseable stdout"
        res["stdout_head"] = out[:500]
        cl = limits.classify(err + "\n" + out[:2000], None)
        if cl and not timed_out:
            res["limit"] = cl
        if allow_partial:                 # no result event: try the session transcript (matched by prompt + start time)
            try:
                tp, ncand = reconstruct.find_transcript_by_prompt(prompt, t0_epoch)
                if tp:
                    txt, meta = reconstruct.reconstruct(None, tp)
                    meta["transcript_match_candidates"] = ncand
                    res["recon"] = meta
                    if reconstruct.usable(txt):
                        res.update({"text": txt, "text_source": "reconstructed", "status": "truncated", "ok": True,
                                    "terminal": True, "session_id": meta.get("session_id"), "truncated": True,
                                    "terminal_reason": "no_result_event"})
            except Exception as e:        # reconstruction must never mask the original failure
                res["recon_error"] = repr(e)
        return res
    if isinstance(events, dict):
        events = [events]
    res["events"] = events
    cl = limits.classify("", events)          # structured rate_limit_event with a non-allowed status
    result = next((e for e in reversed(events) if e.get("type") == "result"), None)
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    rl = [e.get("rate_limit_info") for e in events if e.get("type") == "rate_limit_event"]
    text_fallback, recon = "", None
    try:
        text_fallback, recon = reconstruct.reconstruct(events)
    except Exception as e:
        res["recon_error"] = repr(e)
    if recon is not None:
        res["recon"] = recon
    if result is None:
        res["error"] = "no result event"
        if allow_partial and reconstruct.usable(text_fallback):
            res.update({"text": text_fallback, "text_source": "reconstructed", "status": "truncated", "ok": True,
                        "terminal": True, "truncated": True, "terminal_reason": "no_result_event",
                        "session_id": (recon or {}).get("session_id")})
        return res
    usage = result.get("usage") or {}
    det = usage.get("output_tokens_details") or {}
    res.update({
        "session_id": result.get("session_id"),
        "text": result.get("result") or "",
        "is_error": result.get("is_error"),
        "stop_reason": result.get("stop_reason"),
        "terminal_reason": result.get("terminal_reason"),
        "num_turns": result.get("num_turns"),
        "result_subtype": result.get("subtype"),
        "usage": {
            "input_tokens": usage.get("input_tokens"),
            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
            "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "thinking_tokens": det.get("thinking_tokens"),
        },
        "cost_usd": result.get("total_cost_usd"),
        "duration_ms": result.get("duration_ms"),
        "duration_api_ms": result.get("duration_api_ms"),
        "model_reported": init.get("model"),
        "init": {k: init.get(k) for k in ("tools", "skills", "slash_commands", "agents", "mcp_servers",
                                          "memory_paths", "apiKeySource", "permissionMode",
                                          "per_turn_effort_active", "claude_code_version")},
        "rate_limit": rl[-1] if rl else None,
    })
    # terminal = deterministic failure that a retry would only repeat at full cost (token cap or budget guard hit)
    res["terminal"] = ("budget" in str(result.get("subtype")).lower() or "budget" in str(result.get("terminal_reason")).lower()
                       or result.get("stop_reason") == "max_tokens")
    res["ok"] = (rc == 0 and not result.get("is_error") and bool(res["text"].strip()))
    res["text_source"] = "result" if res["text"].strip() else "none"
    if res["ok"]:
        res["status"] = "ok"
    if allow_partial and recon is not None:
        # all-turn totals from the transcript (result.usage.output_tokens is one turn only)
        res["total_output_tokens"] = recon.get("total_output_tokens")
        res["total_thinking_tokens"] = recon.get("total_thinking_tokens")
        if not res["text"].strip() and reconstruct.usable(text_fallback):
            res["text"], res["text_source"] = text_fallback, "reconstructed"
        if res["text"].strip() and reconstruct.usable(res["text"]):
            res["truncated"] = bool(recon.get("truncated")) or not res["ok"]
            res["status"] = "truncated" if res["truncated"] else "ok"
            res["ok"] = True
    if not res["ok"]:
        res["error"] = "cli error: rc=%s is_error=%s terminal=%s text=%r" % (
            rc, result.get("is_error"), result.get("terminal_reason"), res["text"][:200])
        if not res["terminal"]:
            cl = cl or limits.classify("\n".join([res["text"], err, str(result.get("error") or ""), str(result.get("api_error_status") or "")]), None)
            if cl:
                res["limit"] = cl
                res["error"] = "USAGE LIMIT (%s/%s): %s" % (cl["kind"], cl["source"], cl["msg"][:200])
    return res


def with_retries(fn, what, retries=2, backoffs=(30, 90), max_timeouts=2):
    """fn() -> result dict with 'ok'. Retries transient failures at most `retries` times; a wall-clock timeout gets
    ONE kill-and-retry (max_timeouts=2 attempts) then fails. Usage limits do not consume retries: the shared gate
    sleeps (5-hour window) and the call is repeated, or flags a halt (weekly limit / reset > 6 h)."""
    attempts, timeouts, waited, i = [], 0, 0.0, 0
    while True:
        r = fn()
        attempts.append({"attempt": len(attempts) + 1, "ok": r.get("ok"), "error": r.get("error"), "wall_s": r.get("wall_s")})
        if r.get("ok") or r.get("terminal"):
            break
        if r.get("limit"):
            log("%s hit usage limit: %s" % (what, r["limit"]))
            if GATE is None:
                r["limit_halt"] = True
                break
            t0 = time.time()
            act = GATE.handle(r["limit"], waited)
            waited += time.time() - t0
            if act == "halt":
                r["limit_halt"] = True
                break
            if len(attempts) > 40:       # sanity bound on repeated sleeps for one call
                break
            continue
        log("%s attempt %d failed: %s" % (what, len(attempts), r.get("error")))
        if r.get("timeout"):
            timeouts += 1
            if timeouts >= max_timeouts:
                break
        elif i >= retries:
            break
        else:
            i += 1
        time.sleep(backoffs[min(max(i - 1, 0), len(backoffs) - 1)])
    r["attempts"] = attempts
    return r


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
