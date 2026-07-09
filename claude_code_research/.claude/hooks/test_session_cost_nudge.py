#!/usr/bin/env python3
"""
Unit tests for session-cost-nudge.py.

Invokes the hook as a real subprocess (feeding stdin JSON, checking stdout /
exit code / stderr) so the tests exercise the true UserPromptSubmit contract.

All fixtures live in isolated temp dirs under the system temp *only for this
test process*; the hook's `.scratch/` resolves inside each temp cwd, so the
project's real .scratch/ state is never touched.
"""

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOOK = Path(__file__).resolve().parent / "session-cost-nudge.py"

_results = []


def check(scenario: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    _results.append((scenario, condition))
    line = f"[{status}] {scenario}"
    if detail:
        line += f"  -- {detail}"
    print(line)


# ---- fixture builders -------------------------------------------------------

def assistant_usage_line(input_tokens=0, cache_read=0, cache_creation=0) -> str:
    return json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "ok"}],
            "usage": {
                "input_tokens": input_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_creation,
                "output_tokens": 10,
            },
        },
    })


def user_line(text="hello") -> str:
    return json.dumps({"type": "user", "message": {"role": "user", "content": text}})


def tool_result_line(text="result") -> str:
    # A trailing user/tool_result line carrying no usage object.
    return json.dumps({
        "type": "user",
        "message": {"role": "user", "content": [{"type": "tool_result", "content": text}]},
    })


def write_transcript(cwd: Path, name: str, lines) -> Path:
    tp = cwd / name
    tp.write_text("\n".join(lines) + "\n")
    return tp


# ---- hook invocation --------------------------------------------------------

def run_hook(transcript_path: Path, session_id: str, cwd: Path, proc_cwd: Path):
    payload = json.dumps({
        "transcript_path": str(transcript_path),
        "session_id": session_id,
        "cwd": str(cwd),
    })
    # proc_cwd deliberately differs from the JSON cwd to prove the hook resolves
    # .scratch/ from the JSON cwd, not the process working directory.
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload, capture_output=True, text=True, timeout=30, cwd=str(proc_cwd),
    )
    return r.returncode, r.stdout, r.stderr


# ---- tests ------------------------------------------------------------------

def main():
    root = Path(tempfile.mkdtemp(prefix="nudge-test-"))
    proc_cwd = root  # neutral process cwd

    # (a) below 150k -> silent, exit 0, no stdout
    cwd = root / "a"; cwd.mkdir()
    tp = write_transcript(cwd, "t.jsonl", [user_line(), assistant_usage_line(input_tokens=100_000)])
    rc, out, err = run_hook(tp, "sess-a", cwd, proc_cwd)
    check("(a) below 150k -> silent", rc == 0 and out.strip() == "" and err.strip() == "",
          f"rc={rc} out={out!r} err={err!r}")

    # (b)+(c)+(d) escalation lifecycle in one cwd/session (latch is stateful)
    cwd = root / "bcd"; cwd.mkdir()
    sid = "sess-bcd"
    # (b) first crossing of rung 1 (100k+30k+21k = 151k) -> rung-1, state=1
    tp = write_transcript(cwd, "t.jsonl",
                          [user_line(), assistant_usage_line(100_000, 30_000, 21_000)])
    rc, out, err = run_hook(tp, sid, cwd, proc_cwd)
    state_file = cwd / ".scratch" / f".session-nudge-{sid}.json"
    state_ok = state_file.exists() and json.loads(state_file.read_text()).get("highest_rung_fired") == 1
    check("(b) >=150k first crossing -> rung-1 msg + state=1",
          rc == 0 and "150k" in out and state_ok, f"out={out.strip()!r} state_ok={state_ok}")

    # (c) same session, still rung 1 (160k) -> silent (edge-trigger holds)
    tp = write_transcript(cwd, "t.jsonl", [user_line(), assistant_usage_line(input_tokens=160_000)])
    rc, out, err = run_hook(tp, sid, cwd, proc_cwd)
    check("(c) same rung re-invoke -> silent", rc == 0 and out.strip() == "",
          f"out={out!r}")

    # (d) advance to rung 2 (301k) -> rung-2 msg, state=2
    tp = write_transcript(cwd, "t.jsonl", [user_line(), assistant_usage_line(input_tokens=301_000)])
    rc, out, err = run_hook(tp, sid, cwd, proc_cwd)
    state_ok = json.loads(state_file.read_text()).get("highest_rung_fired") == 2
    check("(d) advance to >=300k -> rung-2 msg + state=2",
          rc == 0 and "300k" in out and "/new-session" in out and state_ok,
          f"out={out.strip()!r} state_ok={state_ok}")

    # (d2) advance to rung 3 (501k) -> strong-recommendation msg, state=3
    tp = write_transcript(cwd, "t.jsonl", [user_line(), assistant_usage_line(input_tokens=501_000)])
    rc, out, err = run_hook(tp, sid, cwd, proc_cwd)
    state_ok = json.loads(state_file.read_text()).get("highest_rung_fired") == 3
    check("(d2) advance to >=500k -> rung-3 strong msg + state=3",
          rc == 0 and "500k" in out and "Strongly" in out and state_ok,
          f"out={out.strip()!r} state_ok={state_ok}")

    # (e) malformed transcript -> silent exit, no crash, no traceback on stderr
    cwd = root / "e"; cwd.mkdir()
    tp = write_transcript(cwd, "t.jsonl", ["{not valid json", "}{ broken", "\x00\x01garbage"])
    rc, out, err = run_hook(tp, "sess-e", cwd, proc_cwd)
    check("(e) malformed transcript -> silent, no traceback",
          rc == 0 and out.strip() == "" and "Traceback" not in err,
          f"rc={rc} out={out!r} err={err!r}")

    # (f) trailing non-assistant line; earlier assistant usage 151k -> found via backward walk
    cwd = root / "f"; cwd.mkdir()
    tp = write_transcript(cwd, "t.jsonl", [
        user_line(),
        assistant_usage_line(input_tokens=151_000),
        tool_result_line("a big tool result with no usage field"),
        user_line("follow-up prompt"),
    ])
    rc, out, err = run_hook(tp, "sess-f", cwd, proc_cwd)
    check("(f) trailing non-usage line -> backward walk finds earlier usage",
          rc == 0 and "150k" in out, f"out={out.strip()!r}")

    # (g) .scratch/ absent -> hook creates it and persists
    cwd = root / "g"; cwd.mkdir()
    assert not (cwd / ".scratch").exists()
    tp = write_transcript(cwd, "t.jsonl", [assistant_usage_line(input_tokens=151_000)])
    rc, out, err = run_hook(tp, "sess-g", cwd, proc_cwd)
    created = (cwd / ".scratch").is_dir() and (cwd / ".scratch" / "nudge-events.jsonl").exists()
    check("(g) .scratch/ absent -> created + persisted",
          rc == 0 and "150k" in out and created, f"created={created}")

    # (h) NO assistant-with-usage line at all -> cost 0, silent, no spurious rung-1
    cwd = root / "h"; cwd.mkdir()
    tp = write_transcript(cwd, "t.jsonl", [user_line(), tool_result_line(), user_line("prompt")])
    rc, out, err = run_hook(tp, "sess-h", cwd, proc_cwd)
    no_state = not (cwd / ".scratch" / ".session-nudge-sess-h.json").exists()
    check("(h) no usage line at all -> silent, no rung-1, no state",
          rc == 0 and out.strip() == "" and no_state, f"out={out!r} no_state={no_state}")

    # (i) large multi-MB transcript; usage line sits BEHIND a >256KB trailing line
    #     so the bounded tail read must enlarge to find it. Assert found + fast.
    cwd = root / "i"; cwd.mkdir()
    big_trailer = tool_result_line("X" * 300_000)         # ~300KB trailing, no usage
    filler = [user_line("filler " + "y" * 200) for _ in range(12_000)]  # ~few MB
    lines = filler + [assistant_usage_line(input_tokens=301_000)] + [big_trailer]
    tp = write_transcript(cwd, "t.jsonl", lines)
    size_mb = tp.stat().st_size / (1024 * 1024)
    t0 = time.time()
    rc, out, err = run_hook(tp, "sess-i", cwd, proc_cwd)
    elapsed = time.time() - t0
    check("(i) large transcript, usage behind big trailer -> found via enlarge, fast",
          rc == 0 and "300k" in out and elapsed < 1.0,
          f"size={size_mb:.1f}MB elapsed={elapsed*1000:.0f}ms out={out.strip()[:40]!r}")

    # session isolation: two session_ids -> two independent state files
    cwd = root / "iso"; cwd.mkdir()
    tp1 = write_transcript(cwd, "t1.jsonl", [assistant_usage_line(input_tokens=151_000)])  # rung 1
    tp2 = write_transcript(cwd, "t2.jsonl", [assistant_usage_line(input_tokens=301_000)])  # rung 2
    rc1, out1, _ = run_hook(tp1, "iso-A", cwd, proc_cwd)
    rc2, out2, _ = run_hook(tp2, "iso-B", cwd, proc_cwd)
    fa = cwd / ".scratch" / ".session-nudge-iso-A.json"
    fb = cwd / ".scratch" / ".session-nudge-iso-B.json"
    indep = (fa.exists() and fb.exists()
             and json.loads(fa.read_text())["highest_rung_fired"] == 1
             and json.loads(fb.read_text())["highest_rung_fired"] == 2)
    check("(iso) two session_ids -> independent state files & rungs",
          "150k" in out1 and "300k" in out2 and indep,
          f"indep={indep}")

    # ---- summary ----
    passed = sum(1 for _, ok in _results if ok)
    total = len(_results)
    print(f"\n{passed}/{total} scenarios passed")
    # cleanup temp fixtures
    import shutil
    shutil.rmtree(root, ignore_errors=True)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
