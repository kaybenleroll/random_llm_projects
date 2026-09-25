#!/usr/bin/env python3
"""Unit check of limits.classify/decide. NOTE: every sample string below is an ASSUMED format, not an observed one
(no real usage limit was ever hit); only the rate_limit_event field names come from observed smoke output."""
import time, datetime
from limits import classify, decide
now = datetime.datetime(2026, 9, 25, 1, 0, 0).timestamp()
def ev(status, typ, resets):
    return [{"type": "rate_limit_event", "rate_limit_info": {"status": status, "rateLimitType": typ, "resetsAt": resets}}]
cases = [
 # (name, text, events, expected kind, expected action)
 ("ok event allowed", "", ev("allowed", "five_hour", now + 3600), None, None),
 ("normal text", "Here is my review of the plan...", None, None, None),
 ("transient 429 no limit words", "API Error: 429 overloaded_error", None, None, None),
 ("struct 5h rejected +2h", "", ev("rejected", "five_hour", now + 7200), "window", "sleep"),
 ("struct weekly rejected", "", ev("rejected", "seven_day", now + 3 * 86400), "weekly", "halt"),
 ("struct 5h reset >6h", "", ev("rejected", "five_hour", now + 7 * 3600), "window", "halt"),
 ("text 5-hour resets 3am", "5-hour limit reached · resets 3am (Europe/Dublin)", None, "window", "sleep"),
 ("text hit your limit resets 3am", "You've hit your limit · resets 3am (Europe/Dublin)", None, "unknown", "sleep"),
 ("text weekly", "You've hit your weekly limit · resets Sep 30 at 3am", None, "weekly", "halt"),
 ("text 7-day", "Claude usage limit reached. Your 7-day limit resets Oct 1, 9am", None, "weekly", "halt"),
 ("text epoch pipe", "Claude AI usage limit reached|%d" % (now + 5400), None, "unknown", "sleep"),
 ("text resets in 2h15m", "Usage limit reached, resets in 2 hours 15 minutes", None, "window", "sleep"),
 ("text unstated reset", "You've hit your session limit", None, "window", "poll30"),
 ("text unknown far date", "Usage limit reached. Resets Sep 27 at 3pm", None, "unknown", "halt"),
]
bad = 0
for name, text, events, kind, act in cases:
    cl = classify(text, events, now)
    if cl is None:
        got = (None, None); detail = ""
    else:
        a, v = decide(cl, now)
        a = "poll30" if (a == "sleep" and v == 1800 and not cl["reset_epoch"]) else a
        got = (cl["kind"], a); detail = "sleep=%s reset_in_h=%s" % (round(v/60) if a != "halt" and isinstance(v,(int,float)) else v, round((cl["reset_epoch"]-now)/3600,2) if cl["reset_epoch"] else None)
    ok = got == (kind, act)
    bad += not ok
    print("%s  %-32s -> %s %s" % ("PASS" if ok else "FAIL", name, got, detail))
# unstated poll exhaustion
cl = classify("You've hit your session limit", None, now)
print("PASS" if decide(cl, now, waited_s=6*3600)[0] == "halt" else "FAIL", " unstated wait exhausted -> halt")
print("RESULT: %d failures" % bad)
raise SystemExit(bad)
