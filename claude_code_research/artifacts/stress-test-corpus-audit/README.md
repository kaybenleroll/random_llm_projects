# Stress-Test Corpus Audit — tooling

Two standalone Python scripts for measuring how a corpus of `## Stress-Test
Log`-carrying plan files actually behaves: pass counts to convergence,
per-pass finding/restatement yield, verdict distribution, and (as a
cautionary example, not something to trust blind) how a proposed
regex-based pre-dispatch gate would perform against real terminal entries.

Both scripts require only the Python 3 standard library — no pip install.

## What each script measures

**`parse_stress_test_logs.py`** — parses every `### ` header block inside
each file's `## Stress-Test Log` section into a structured row (date, time,
model, pass number, verdict, findings count, restatement-flagged bullet
count, ...), then rolls those up per plan file ("lineage") into a terminal
verdict and total pass count. Produces:
- `blocks.csv` — one row per `### ` header block
- `lineages.csv` — one row per plan file, with its terminal verdict/type and total pass count
- `q_per_pass.csv` — per-pass-number aggregate findings and restatement-flag rate
- `q_ship_dates.csv` — only written if `--ship-dates` is passed; before/after comparison across named dates
- `summary.txt` — human-readable printout of everything above

**`check_placeholder_bullet.py`** — takes a candidate regex meant to detect
"this terminal entry shows fold work left incomplete" and reports its hit
rate separately against (a) lineages that terminated CLEAN/ACCEPTED (a hit
here is a false positive) and (b) lineages that never reached a terminal
verdict (a hit here is, at best, a true positive — see the caveat below
before treating it as one). Use this to sanity-check any such gate BEFORE
wiring it into a workflow, not after.

## How to run

### 1. Stage the corpus (read-only copies, never the live plan directory)

Single machine:
```bash
mkdir -p staging/local
cp ~/.claude/plans/*.md staging/local/
```

Two machines (adjust host and remote path to your setup):
```bash
mkdir -p staging/local staging/remote
cp ~/.claude/plans/*.md staging/local/
ssh <remote-host> 'tar -C ~/.claude/plans -cf - .' | tar -C staging/remote -xf -
```

Any number of subdirectories under `staging/` works — each becomes a
"machine" label in the output. A single-subdirectory staging tree is just
as valid as a multi-machine one.

### 2. Parse

```bash
python3 parse_stress_test_logs.py staging --out-dir out
cat out/summary.txt
```

Optional before/after comparison across named dates (e.g. when a process
change shipped) — pass a JSON file:
```bash
cat > ship_dates.json <<'EOF'
{"my_change_2026-01-01": "2026-01-01"}
EOF
python3 parse_stress_test_logs.py staging --out-dir out --ship-dates ship_dates.json
```

### 3. (Optional) sanity-check a proposed placeholder/incomplete-fold gate

Edit `PLACEHOLDER_RE` at the top of `check_placeholder_bullet.py` to match
the actual trigger language you're evaluating, then:
```bash
python3 check_placeholder_bullet.py staging --lineages-csv out/lineages.csv
```
Read the false-positive-check block first. A gate with a high hit rate
against CLEAN/ACCEPTED-terminal lineages is not usable as a hard block no
matter how well it scores on the non-concluding set — in one real
development run, a starting-point regex covering "not folded / still open
/ deferred / handed off / placeholder text" hit **66.5%** of terminal
CLEAN/ACCEPTED lineages, because that language shows up routinely inside
findings write-ups (describing *what a finding says*, not the pass's own
fold status) and inside legitimate `Resolution:` prose — not just in
genuinely-incomplete entries.

## Known caveats

- **Entry ordering (newest-first vs oldest-first) varies by file — resolve
  by entry timestamp, not file/list position.** Some plan authors write new
  log entries at the top of the `## Stress-Test Log` section, others append
  at the bottom. Neither script assumes one convention: the terminal entry
  is chosen by pairwise `(date, time, pass_num)` comparison across every
  verdict-bearing block, falling back to file position only as the very
  last tiebreak when none of those differ (see `later()` /
  `pick_terminal()` in `parse_stress_test_logs.py`).

- **Arrow-suffix verdicts: the verdict is the token AFTER the arrow.** A
  header like `RERUN_NEEDED → addressed, CLEAN` records the pass's outcome
  *after* fold-in — `extract_verdict()` searches for a verdict token to the
  right of the arrow first, falling back to the left only if nothing valid
  follows it.

- **A "take-stock" keyword appearing in prose must not misclassify a real
  pass block.** A header can legitimately say something like "take-stock
  triggered, escalating to Pass 5" while still being pass 5's own
  findings-bearing, verdict-carrying entry. `classify_and_parse_header()`
  checks for a parsed pass number *and* a verdict token together, and
  short-circuits to `PASS` before applying the keyword-exclusion filter —
  if you extend the exclusion list, preserve that ordering or you will
  silently drop real pass entries whose header happens to mention
  take-stock, override, evidence, spike, or any of the other exclusion
  keywords in passing.

- **A take-stock RESOLUTION entry (as opposed to prose merely mentioning
  take-stock) is a SKILL.md-prescribed terminal marker, not a pass, and is
  handled by a dedicated `TAKE_STOCK_RESOLVED` block type.** SKILL.md's
  literal template is `### <date HH:MM> — TAKE-STOCK RESOLVED — Option
  <A|C|D> at Pass <N>`. **Option C is terminal** (ACCEPTED-equivalent —
  "Accept the known gaps ... stop stress-testing"); **Options A, B, D all
  continue** the loop. The check lives immediately after the
  pass_num-and-verdict short-circuit and immediately before `EXCLUDE_RE`
  (which would otherwise swallow it as a plain `MARKER`, discarding its
  pass number), and only fires when the header carries **no** canonical
  verdict token already — several real lineages depend on an existing,
  more-informed `ACCEPTED_STANDALONE` path (e.g. `— Take-stock resolution
  — ACCEPTED`) that must keep winning over the option-letter heuristic.
  The entry's `pass_num` (parsed from "at Pass N") is kept for
  chronological tie-breaking in `later()`/`pick_terminal()` but is
  type-gated out of every pass-count and per-pass statistic — **anyone
  aggregating `blocks.csv` by `pass_num` without also filtering on `type`
  will double-count a resolved pass.** `later()` additionally ranks a
  `TAKE_STOCK_RESOLVED` block above the same-numbered pass it resolves
  when date, time, and pass_num all tie (relevant only for date-only logs
  with no `HH:MM`) — without this, the position-independence this script
  otherwise guarantees would silently break for that one case.

- **A terminal `RERUN_NEEDED` verdict usually means the work shipped and
  the log was simply never updated with a closing entry — not that the
  lineage died inside the stress-test loop.** This is the single most
  important caveat for anyone building a gate off "lineage never reached
  CLEAN/ACCEPTED." In a sample of 18 non-concluding lineages (terminal
  entry `RERUN_NEEDED`, no closing entry), 0 had actually stalled or died
  inside the review loop — 78% had a corresponding GitHub issue/PR closed
  within hours-to-days of the last log entry. The practical implication:
  before treating "non-concluding in the log" as a proxy for "abandoned" or
  "problematic," cross-check a sample of your own non-concluding lineages
  against your issue/PR history the same way. A gate built on the
  unverified assumption will target a failure mode that mostly doesn't
  exist.
