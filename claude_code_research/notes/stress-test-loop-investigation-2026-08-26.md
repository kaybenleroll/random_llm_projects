# Stress-test loop investigation — 2026-08-26

## Original question

Why do some `/stress-test` lineages loop for many passes without findings
folding in cleanly? Specifically: is there a detectable "fold work
incomplete" signal that could gate a pass from being logged as resolved
when it wasn't, before the next pass wastes an Opus review re-discovering
the same gap?

## Three gate designs attempted, all killed by evidence

1. **Free-text detection of incomplete-fold language.** A regex over the
   terminal Stress-Test Log entry's body, matching phrases like "not
   folded", "still open", "deferred", "handed off", "placeholder". Killed:
   measured against the corpus, this tripped **66.5%** of lineages that
   actually terminated CLEAN/ACCEPTED — the language shows up routinely
   inside findings write-ups describing *what a finding says* and inside
   legitimate `Resolution:` prose, not just genuinely-incomplete entries.
   An FP rate that high makes it unusable as a hard block.

2. **Unimplementable placeholder detection with no defined token.** A
   proposal to detect "this field still holds its dispatch-time placeholder
   text, fold work never actually started" — but the placeholder mechanic
   in `SKILL.md` doesn't fix a literal string; it's "whatever the
   invoking agent wrote before backfilling." No consistent token exists to
   grep for across the corpus, so the check can't be built as specified.

3. **Causal claim for a fold-check gate, refuted by tracing stalled
   lineages.** The working hypothesis was that lineages stuck at
   `RERUN_NEEDED` with no closing entry represent work that died inside the
   stress-test loop — the gate's target failure mode. Traced 18 such
   lineages by hand against issue/PR history: **0 had actually died in the
   loop.** 78% had a corresponding issue or PR closed within
   hours-to-days of the last log entry — the work shipped and the log was
   simply never updated with a closing entry. The premise the gate was
   meant to fix does not describe what's actually happening in the corpus.

## Corpus-wide findings that survived

Measured across N=251 lineages (local + s3rbase plan snapshots):

- **61.8% terminal success** (CLEAN + ACCEPTED = 155/251); 5.2% gated
  (RESTRUCTURE/UNSETTLED/PREMATURE = 13/251); the remainder non-concluding
  in the log (mostly shipped-but-unlogged per the tracing above, not
  abandoned).
- **Restatement share climbs sharply after pass 5, not gradually from
  pass 1.** Restatement-flagged bullet share by pass: 3.7% (pass 1), 3.1%
  (pass 2), 4.0% (pass 3), 4.7% (pass 4), 9.4% (pass 5), 18.8% (pass 6),
  33.6% (pass 7+). The jump is concentrated in the tail, which is what
  motivated the pass-4 `RESTRUCTURE` enforcement rule already in
  `SKILL.md` (kept as-is; only its cited statistic was corrected — see
  below).
- **Severity bar is well-calibrated even at the final pass**: 72% of
  findings at pass 7+ are still BLOCKING+SUBSTANTIVE severity, not
  degraded into cosmetic nitpicking as the loop lengthens — the reviewer
  isn't padding late passes with trivia, the tail genuinely still finds
  real (if often restated) issues.
- Only 6/251 lineages (2.4-2.56% depending on denominator) exceed 7
  passes.
- Only 4/14 runaway (7-10 pass) lineages have ≥800 content lines (10/14
  fall below the 800-line proxy) — so the Option D size/coupling proxy
  enriches for runaways (~28.6% vs ~4.2% base rate) without runaways
  "concentrating" there, which is what the prior `SKILL.md` prose falsely
  claimed.
- Only 3/14 runaway lineages carry 2+ `COUNTER RESET` markers — a real
  signal (~12x lift over the corpus's 1.7% base rate) but not the
  "dominant failure pattern" the prior prose asserted.

## What shipped instead

No new gate. Given the three gate designs above were all unworkable or
falsified, the session pivoted to correcting `SKILL.md` and
`stress-tester.md` prose that had drifted from what the corpus actually
supports:

- Deleted or replaced every empirically false or unverifiable inline claim
  (the pass-4 rule's "172 plans, 4.4%" figure, the size-proxy
  "concentrated" claim, the COUNTER RESET "dominant failure pattern"
  claim, a dangling citation to a nonexistent CLAUDE.md section, leaked
  authoring-context prose, a stale "Step" citation) with mechanism-based
  justification plus a durable `[E<n>]` citation into a new
  `## Empirical Basis` appendix in each file.
- Established the `## Empirical Basis` appendix convention itself:
  `E<n> · measured/verified <date> · N=... · <figure> · src: ... ·
  re-measure; do not quote live` — so a future audit can tell at a glance
  which numbers are policy constants, which are live duplications of
  another file, and which are dated snapshots due for re-measurement.
- Promoted the corpus-parsing tooling (`.scratch/stlog/*.py` in this
  session) into `claude_code_research/artifacts/stress-test-corpus-audit/`
  as a portable, parameterized runbook — see that directory's own
  `README.md` for usage; it is written to be runnable from a fresh session
  on another machine, with no reference to this investigation.
- No threshold, cap, or verdict-routing value in either skill file
  changed — this was a citation and prose-accuracy pass only, not a
  behavioral change to the stress-test mechanism.

## Where the source data lives

The raw per-block and per-lineage CSVs behind the figures above are
session-local (`.scratch/stlog/blocks.csv`, `.scratch/stlog/lineages.csv`)
and not committed — they're reproducible from any future staged corpus via
`artifacts/stress-test-corpus-audit/parse_stress_test_logs.py`.
