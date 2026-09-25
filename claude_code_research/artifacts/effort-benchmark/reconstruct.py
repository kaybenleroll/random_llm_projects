#!/usr/bin/env python3
"""Reconstruct review text + per-run accounting from a run's events (raw.json) and/or its session transcript.

Why: `claude -p --output-format json` returns result.result == '' when the budget guard (error_max_budget_usd) or an
error subtype ends the run, even though assistant turns carried text; and result.usage.output_tokens is ONE turn only
(modelUsage[model].outputTokens is the all-turn total). The transcript (~/.claude/projects/*/<session>.jsonl) is the
authoritative record: one line per content block, every line of a message repeats the message's final usage and
stop_reason, and all lines of one API request share a requestId ("last line wins", dedupe by requestId).
The raw events carry the same blocks but only a partial (streaming-time) usage figure, so they are used for text and,
when no transcript exists, for an approximate token total taken from result.modelUsage.

CLI:
  reconstruct.py <arm> <n> [--write]      backfill from runs/<arm>/<n>.raw.json (+ transcript); --write saves
                                          runs/<arm>/<n>.review.md (only if absent) and <n>.recovered.json
  reconstruct.py --transcript <path|session_id>   print the metadata of one transcript
"""
import glob, json, os, sys

MIN_TEXT_CHARS = 200          # below this, a "review" is not judgeable


def _norm_blocks(content):
    if isinstance(content, str):
        return [("text", content)]
    out = []
    for b in content or []:
        t = b.get("type")
        if t == "text":
            out.append(("text", b.get("text") or ""))
        elif t == "thinking":
            out.append(("thinking", b.get("thinking") or ""))
        else:
            out.append((t or "other", ""))
    return out


def _assistant_lines_from_transcript(path):
    lines = []
    with open(path) as f:
        for l in f:
            try:
                d = json.loads(l)
            except ValueError:
                continue
            if d.get("type") != "assistant" or not isinstance(d.get("message"), dict):
                continue
            m = d["message"]
            u = m.get("usage") or {}
            lines.append({"key": d.get("requestId") or m.get("id"), "msg_id": m.get("id"),
                          "block_idx": d.get("apiBlockIndex"), "stop_reason": m.get("stop_reason"),
                          "out": u.get("output_tokens"), "think": (u.get("output_tokens_details") or {}).get("thinking_tokens"),
                          "blocks": _norm_blocks(m.get("content")), "ts": d.get("timestamp"), "usage_final": True})
    return lines


def _assistant_lines_from_events(events):
    lines = []
    for e in events:
        if e.get("type") != "assistant" or not isinstance(e.get("message"), dict):
            continue
        m = e["message"]
        u = m.get("usage") or {}
        lines.append({"key": e.get("request_id") or e.get("requestId") or m.get("id"), "msg_id": m.get("id"),
                      "block_idx": None, "stop_reason": m.get("stop_reason"),
                      "out": u.get("output_tokens"), "think": (u.get("output_tokens_details") or {}).get("thinking_tokens"),
                      "blocks": _norm_blocks(m.get("content")), "ts": e.get("timestamp"), "usage_final": False})
    return lines


def _turns(lines):
    """Group lines by requestId (first-seen order). Message-level fields: last line wins. Blocks: all distinct lines."""
    order, T = [], {}
    for ln in lines:
        k = ln["key"]
        if k not in T:
            order.append(k)
            T[k] = {"request_id": k, "msg_id": ln["msg_id"], "stop_reason": None, "output_tokens": None,
                    "thinking_tokens": None, "blocks": [], "usage_final": ln["usage_final"], "ts": ln["ts"], "_seen": set()}
        t = T[k]
        if ln["stop_reason"] is not None:
            t["stop_reason"] = ln["stop_reason"]
        if ln["out"] is not None:
            t["output_tokens"] = ln["out"]
        if ln["think"] is not None:
            t["thinking_tokens"] = ln["think"]
        sig = (ln["block_idx"], ln["msg_id"]) if ln["block_idx"] is not None else None
        if sig is not None and sig in t["_seen"]:
            continue                      # same content block written twice
        if sig is not None:
            t["_seen"].add(sig)
        t["blocks"].extend(ln["blocks"])
    return [T[k] for k in order]


def find_transcript(session_id):
    for p in glob.glob(os.path.expanduser("~/.claude/projects/*/%s.jsonl" % session_id)):
        return p
    return None


def find_transcript_by_prompt(prompt, t0_epoch, window_s=180, cwd_hint="effort-20260924-cwd"):
    """Last-resort lookup when no result event exists (e.g. killed on timeout): the transcript whose first user message
    equals the prompt and whose first timestamp is nearest to the call start. Under parallel jobs with an identical
    prompt this is ambiguous, so the caller gets (path, n_candidates)."""
    import datetime
    cands = []
    for p in glob.glob(os.path.expanduser("~/.claude/projects/*%s*/*.jsonl" % cwd_hint)):
        try:
            if os.path.getmtime(p) < t0_epoch - 5:
                continue
            with open(p) as f:
                first_user = ts = None
                for l in f:
                    d = json.loads(l)
                    if d.get("type") == "user" and first_user is None:
                        c = (d.get("message") or {}).get("content")
                        first_user = c if isinstance(c, str) else None
                        ts = d.get("timestamp")
                        break
            if first_user == prompt and ts:
                t = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                if abs(t - t0_epoch) <= window_s:
                    cands.append((abs(t - t0_epoch), p))
        except (OSError, ValueError):
            continue
    cands.sort()
    return (cands[0][1], len(cands)) if cands else (None, 0)


def reconstruct(events=None, transcript_path=None):
    """Return (text, meta). text = text blocks of the LAST turn that produced any (a resume turn that restarts the
    answer supersedes a cut-off earlier one); meta has per-turn accounting summed over all turns, deduped by requestId."""
    result = next((e for e in reversed(events or []) if e.get("type") == "result"), None)
    session = (result or {}).get("session_id") or next((e.get("session_id") for e in (events or []) if e.get("session_id")), None)
    if transcript_path is None and session:
        transcript_path = find_transcript(session)
    tlines = _assistant_lines_from_transcript(transcript_path) if transcript_path and os.path.exists(transcript_path) else []
    elines = _assistant_lines_from_events(events or [])
    lines, source = (tlines, "transcript") if tlines else (elines, "events" if elines else "none")
    turns = _turns(lines)
    # text always taken from whichever source has it (events and transcript carry identical blocks)
    tt = _turns(tlines) if tlines else []
    et = _turns(elines) if elines else []
    text_turns_src = tt if any(b[0] == "text" and b[1] for t in tt for b in t["blocks"]) else et if et else tt
    per_turn, text, text_turn = [], "", None
    for i, t in enumerate(turns):
        th = sum(len(b[1]) for b in t["blocks"] if b[0] == "thinking")
        tx = sum(len(b[1]) for b in t["blocks"] if b[0] == "text")
        per_turn.append({"turn": i + 1, "request_id": t["request_id"], "output_tokens": t["output_tokens"],
                         "thinking_tokens": t["thinking_tokens"], "stop_reason": t["stop_reason"],
                         "thinking_chars": th, "text_chars": tx,
                         "block_types": [b[0] for b in t["blocks"]], "usage_final": t["usage_final"]})
    for i, t in enumerate(text_turns_src):
        s = "".join(b[1] for b in t["blocks"] if b[0] == "text")
        if s.strip():
            text, text_turn = s, i
    usage = (result or {}).get("usage") or {}
    mu = (result or {}).get("modelUsage") or {}
    mu_out = sum((v or {}).get("outputTokens") or 0 for v in mu.values()) if mu else None
    mu_think = sum((v or {}).get("thinkingTokens") or 0 for v in mu.values()) if mu else None
    approx = source != "transcript"
    if not approx and all(t["output_tokens"] is not None for t in turns):
        total_out = sum(t["output_tokens"] for t in turns)
        total_think = sum(t["thinking_tokens"] or 0 for t in turns)
    else:
        total_out, total_think = mu_out, mu_think        # all-turn totals reported by the CLI itself
        approx = True
    subtype = (result or {}).get("subtype")
    last_stop = turns[-1]["stop_reason"] if turns else None
    text_stop = turns[text_turn]["stop_reason"] if (text_turn is not None and text_turn < len(turns)) else None
    err = bool(result and (result.get("is_error") or (subtype not in (None, "success"))))
    meta = {
        "source": source, "transcript": transcript_path, "session_id": session,
        "turns": len(turns), "per_turn": per_turn,
        "per_turn_output_tokens": [t["output_tokens"] for t in turns],
        "per_turn_stop_reason": [t["stop_reason"] for t in turns],
        "total_output_tokens": total_out, "total_thinking_tokens": total_think,
        "total_tokens_approximate": approx,
        "result_usage_output_tokens": usage.get("output_tokens"),          # one turn only
        "modelusage_output_tokens": mu_out,
        "thinking_chars": sum(p["thinking_chars"] for p in per_turn),
        "text_chars": len(text), "text_turn": None if text_turn is None else text_turn + 1,
        "text_turn_stop_reason": text_stop,
        "text_cut": text_stop == "max_tokens",
        "last_turn_stop_reason": last_stop,
        "result_subtype": subtype, "result_is_error": (result or {}).get("is_error"),
        "terminal_reason": (result or {}).get("terminal_reason") if result else "no_result_event",
        "truncated": bool(last_stop == "max_tokens" or text_stop == "max_tokens" or err or result is None),
    }
    return text, meta


def usable(text):
    return len((text or "").strip()) >= MIN_TEXT_CHARS


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if "--transcript" in sys.argv:
        p = a[0] if os.path.exists(a[0]) else find_transcript(a[0])
        text, meta = reconstruct(None, p)
        meta.pop("per_turn")
        print(json.dumps(meta, indent=1), "\ntext chars:", len(text))
        return
    from common import RUNS, atomic_write
    arm, n = a[0], int(a[1])
    d = os.path.join(RUNS, arm)
    events = json.load(open(os.path.join(d, "%d.raw.json" % n)))
    text, meta = reconstruct(events)
    print(json.dumps({k: v for k, v in meta.items() if k != "per_turn"}, indent=1))
    print("text chars:", len(text), "usable:", usable(text))
    if "--write" in sys.argv and usable(text):
        rp = os.path.join(d, "%d.review.md" % n)
        if os.path.exists(rp):
            print("review.md exists, not overwritten")
        else:
            atomic_write(rp, text)
        atomic_write(os.path.join(d, "%d.recovered.json" % n),
                     json.dumps({"arm": arm, "n": n, "status": "truncated", "recovered_from": meta["source"],
                                 "review_chars": len(text), "meta": meta}, indent=1))
        print("wrote", rp, "and recovered.json")


if __name__ == "__main__":
    main()
