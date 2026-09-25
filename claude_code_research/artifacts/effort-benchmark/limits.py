"""Usage-limit detection + gate for the harness. Python 3 stdlib only.

classify(text, events, now) -> None | {"kind": "window"|"weekly"|"unknown", "reset_epoch": float|None, "source": str, "msg": str}
decide(cl, now, waited_s)   -> ("sleep", seconds) | ("halt", reason)

Structured signal (OBSERVED format, from rate_limit_event in smoke runs): rate_limit_info = {status, resetsAt (epoch),
rateLimitType ('five_hour' / 'seven_day' ...)}. In all smoke runs status was 'allowed'; a limited value ('rejected' etc.)
has NOT been observed. Text formats below are ASSUMED, not observed; see test_limits.py.
"""
import re, time, threading, datetime, os

HALT_HORIZON_S = 6 * 3600     # reset further away than this -> halt
UNSTATED_POLL_S = 30 * 60     # reset time not stated -> poll every 30 min
MAX_UNSTATED_WAIT_S = 6 * 3600

LIMIT_PAT = re.compile(r"usage limit|hit your (?:[\w\- ]{0,20})?limit|limit reached|(?:5|five)[- ]hour limit|"
                       r"weekly limit|session limit|limit will reset|out of extra usage|"
                       r"rate.?limit[^\n]{0,80}resets?", re.I)
WEEKLY_PAT = re.compile(r"weekly|7[- ]day|seven[- ]day|this week|per week", re.I)
WINDOW_PAT = re.compile(r"5[- ]hour|five[- ]hour|session limit|resets? in (?:about )?\d+ ?(?:hours?|hrs?|h|minutes?|mins?)", re.I)
BAD_STATUS = {"rejected", "blocked", "exceeded", "limited", "denied"}


def _epoch_in_text(text):
    m = re.search(r"limit reached\s*[|∣]\s*(\d{9,11})", text, re.I) or re.search(r"resetsAt\D{0,5}(\d{9,11})", text)
    return float(m.group(1)) if m else None


def _parse_reset(text, now):
    """Best-effort reset time (epoch) from prose: 'resets 3am (Europe/Dublin)', 'resets Sep 30 at 3:30pm',
    'resets in 2 hours 15 minutes'. None if unstated/unparseable."""
    e = _epoch_in_text(text)
    if e:
        return e
    m = re.search(r"resets? in (?:about )?(?:(\d+) ?(?:hours?|hrs?|h))?[ ,and]*(?:(\d+) ?(?:minutes?|mins?|m))?", text, re.I)
    if m and (m.group(1) or m.group(2)):
        return now + int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60
    m = re.search(r"resets?\s+(?:(?P<mon>[A-Z][a-z]{2,8})\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?,?\s+(?:at\s+)?)?"
                  r"(?P<h>\d{1,2})(?::(?P<mi>\d{2}))?\s*(?P<ap>am|pm)(?:\s*\((?P<tz>[\w/+\-]+)\))?", text, re.I)
    if not m:
        return None
    try:
        tz = None
        if m.group("tz"):
            import zoneinfo
            tz = zoneinfo.ZoneInfo(m.group("tz"))
        cur = datetime.datetime.fromtimestamp(now, tz)
        h = int(m.group("h")) % 12 + (12 if m.group("ap").lower() == "pm" else 0)
        mi = int(m.group("mi") or 0)
        if m.group("mon"):
            mon = datetime.datetime.strptime(m.group("mon")[:3], "%b").month
            t = cur.replace(month=mon, day=int(m.group("day")), hour=h, minute=mi, second=0, microsecond=0)
            if t < cur:
                t = t.replace(year=t.year + 1)
        else:
            t = cur.replace(hour=h, minute=mi, second=0, microsecond=0)
            if t <= cur:
                t += datetime.timedelta(days=1)
        return t.timestamp()
    except Exception:
        return None


def classify(text, events=None, now=None):
    now = now or time.time()
    # 1) structured rate_limit_event with a non-allowed status
    for e in (events or []):
        info = e.get("rate_limit_info") if isinstance(e, dict) and e.get("type") == "rate_limit_event" else None
        if info and str(info.get("status", "allowed")).lower() in BAD_STATUS:
            rt = str(info.get("rateLimitType", "")).lower()
            kind = "weekly" if ("seven" in rt or "week" in rt) else "window" if "five" in rt or "hour" in rt else "unknown"
            return {"kind": kind, "reset_epoch": info.get("resetsAt"), "source": "rate_limit_event",
                    "msg": "status=%s type=%s" % (info.get("status"), rt)}
    # 2) text (stderr / result text / api error fields)
    if not text or not LIMIT_PAT.search(text):
        return None
    kind = "weekly" if WEEKLY_PAT.search(text) else "window" if WINDOW_PAT.search(text) else "unknown"
    return {"kind": kind, "reset_epoch": _parse_reset(text, now), "source": "text", "msg": text.strip()[:300]}


def decide(cl, now=None, waited_s=0):
    now = now or time.time()
    if cl["kind"] == "weekly":
        return "halt", "weekly limit: " + cl["msg"]
    r = cl.get("reset_epoch")
    if r:
        wait = r - now
        if wait > HALT_HORIZON_S:
            return "halt", "reset %.1f h away (> 6 h): %s" % (wait / 3600, cl["msg"])
        return "sleep", max(60.0, wait + 60)         # +60 s margin past the stated reset
    if waited_s >= MAX_UNSTATED_WAIT_S:
        return "halt", "no stated reset after %.1f h of 30-min polling: %s" % (waited_s / 3600, cl["msg"])
    return "sleep", UNSTATED_POLL_S


class LimitGate:
    """Shared by all worker threads. handle() blocks (sleeping) or flips halted."""
    def __init__(self, on_state=lambda s: None, stop_file=None):
        self.halted = None          # reason string once halted
        self.lock = threading.Lock()
        self.on_state = on_state
        self.stop_file = stop_file

    def handle(self, cl, waited_s):
        """Returns 'retry' (slept; call again) or 'halt'."""
        with self.lock:
            if self.halted:
                return "halt"
        act, val = decide(cl, waited_s=waited_s)
        if act == "halt":
            with self.lock:
                self.halted = self.halted or val
            self.on_state("HALTING: " + val)
            return "halt"
        until = time.time() + val
        self.on_state("SLEEPING for usage-limit reset until %s (%s)" % (time.strftime("%H:%M:%S", time.localtime(until)), cl["msg"][:120]))
        while time.time() < until:
            if self.halted or (self.stop_file and os.path.exists(self.stop_file)):
                return "halt"
            time.sleep(min(60, max(1, until - time.time())))
        self.on_state("RUNNING (resumed after limit sleep)")
        return "retry"
