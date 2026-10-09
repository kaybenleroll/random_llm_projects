# Context baseline measurement (Claude Code)

Measures how many tokens a fresh Claude Code session carries before the first user prompt
(system prompt, tool schemas, CLAUDE.md files, skill/agent listings, memory, MCP instructions),
using existing session transcripts. Read-only; needs only Python 3 (stdlib).

Set `CLAUDE_HOME` to override the config dir (default `~/.claude`). Transcripts are read from
`$CLAUDE_HOME/projects/<cwd-key>/<session>.jsonl`.

## Steps
1. List recent first-request usage across sessions (default 10 rows, or pass N):
   `python3 -I first.py 20`
   Output columns: timestamp, project dir key, session id (8 chars), model, uncached input,
   cache-creation, cache-read. First-request total = sum of the last three numeric columns.
2. Component sizes (characters) for one session, by session-id prefix:
   `python3 -I comp.py <session-prefix>`
   Prints a `USAGE` line (input, created, read) and per-attachment sizes (FILE, SKILL, DEFERRED, AGENTS, MCPI, HOOK).
3. Calibrate chars per token: `python3 -I fit.py <session-prefix> [more prefixes]`
   Prints `(T, chars)`: T = measured first-request total tokens, chars = summed injected-message characters.
   Chars per token = (chars) / (T - cache_read_prefix), where the cache-read prefix is the
   system prompt + built-in tool schemas as shown by `comp.py` USAGE.

Per-component tokens = component chars / calibrated ratio (about 2.7 chars/token observed).
This is an estimate: no offline tokenizer is used.

## Cross-check (required)
Run `/context` in an interactive session started in the same directory and compare the total
with the first-request total from step 1.

## Pass / fail
- PASS: estimated component sum is within 10% of the measured first-request total AND within
  10% of `/context` total for the same directory.
- FAIL: otherwise. Note that the 10% match against the measured total holds by construction
  (the ratio is fitted to it); the `/context` comparison is the independent check.
- Stability check: the fitted chars/token ratio should agree within about 5% across two
  different working directories (observed 2.67 vs 2.68).
- A cache-read prefix that differs by more than a few thousand tokens between directories
  suggests extra (non-deferred) MCP tool schemas; confirm by disabling servers one at a time.

## Limitations
- The system prompt versus built-in tool schema split is not recoverable from transcripts.
- Transcript attachment field names (`instructions`, `skill_listing`, `prompt_snapshot`, ...)
  may change between Claude Code versions; `comp.py`/`fit.py` assume the layout of the
  version they were written against.
