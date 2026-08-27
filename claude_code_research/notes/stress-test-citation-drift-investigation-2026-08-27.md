# Stress-test citation-drift investigation — 2026-08-27 (CORRECTED)

**This file was rewritten after a methodology error in the original survey was caught
by the user and re-verified. See "Correction" section below — it supersedes the
original "process is broken" conclusion.**

## Trigger

A single plan (issue #4291, `poc_planning_tool`) ran 6-7 `/stress-test` passes without
converging (as of the original investigation); the reviewer diagnosed the loop as
driven by a "Canonical Facts" table (numbered `CF-N` citations to external source line
numbers/counts) generating new stale citations faster than review could correct them,
and hypothesized this as a general design gap in the `/stress-test` skill's finding
taxonomy. Full original hypothesis document:
`.scratch/stress-test-citation-drift-investigation-prompt.md`.

## Original result (citation-drift hypothesis): not supported

Two independent codebases surveyed (`poc_planning_tool`/`claude_code_research` locally,
`sea3r_automation` on s3rbase), ~1,080 findings, 7-day window. Design findings
dominated everywhere (80-91%) independent of Canonical-Facts-table use; the two
lineages that used a full CF table disagreed with each other on citation share (38%
vs 10%), directly contradicting a CF-table-causes-citation-drift correlation. This part
of the conclusion still stands — see git history of this file for full detail if
needed.

## Correction: the "non-convergence" claim was a measurement artifact

The original survey also claimed "zero terminal verdicts (CLEAN/ACCEPTED) across all
13 s3rbase lineages in the week" and several local lineages "never converged" — this
was used to argue the whole stress-test process is broken, independent of the citation
hypothesis. **The user correctly challenged this**: some plans span multiple sessions
(context-window handoffs), and the survey grouped findings by individual session
transcript file, which cannot see a continuation that landed in a different session.

Re-verification (widened to 2026-08-01–2026-08-27, both machines) found:

- **#4291 itself converged** — Option C take-stock resolved 2026-08-27, in a successor
  plan file (`bubbly-mixing-clover.md`) the original survey never saw.
- #4357, #4381, and two other local lineages ("queue-review-fix", the FRT-rule plan)
  all reached ACCEPTED-equivalent terminal states, most followed by the GitHub issue
  closing within hours.
- s3rbase: at least 4 of the 13 "unconverged" lineages actually reached CLEAN/ACCEPTED,
  3 of them inside the original 7-day window.
- Corpus-wide (this repo's own `artifacts/stress-test-corpus-audit/parse_stress_test_logs.py`,
  re-run fresh, 155 lineages): CLEAN 80, ACCEPTED 11, RERUN_NEEDED 50, RESTRUCTURE 8.
  Of the RERUN_NEEDED-tagged ones, a prior corroborated measurement estimates ~78% are
  actually already-shipped with the log simply not updated — 5/5 hand-checked this
  round were in fact resolved.

  **Correction (2026-08-27, post-fix of kaybenleroll/random_llm_projects#76):** the
  figures immediately above were themselves undercounted by the exact parser bug this
  investigation went on to diagnose (below) — the tool didn't recognize the
  SKILL.md-prescribed `TAKE-STOCK RESOLVED — Option C` terminal template. After the
  fix, the corpus-wide distribution is **CLEAN 80, ACCEPTED 14, RERUN_NEEDED 47,
  RESTRUCTURE 8** (156 lineages; small lineage-count drift vs. the 155 above is from
  new plan files created since, not from the fix). `q_per_pass.csv` — the per-pass
  finding/restatement statistics — is byte-identical before and after, so the E1
  restatement figures cited in SKILL.md are unaffected by this correction.

**Conclusion: convergence is not broken.** The earlier "zero terminal verdicts" /
"process is broken" claim is retracted.

## What's real: verdict-vocabulary and cross-session lineage tracking are fragile

The reason both surveys (and even this repo's own dedicated audit tool) undercounted
convergence is a genuine, confirmed gap:

1. **The six-status verdict vocabulary (CLEAN/ACCEPTED/RESTRUCTURE/RERUN_NEEDED/
   UNSETTLED/PREMATURE) is not consistently used at terminal state.** Real terminal
   entries observed in the wild: "TAKE-STOCK RESOLVED — Option C", "STATUS: LANDED",
   "Direct fix (main thread, no dispatch)". None match the canonical tags. This fools
   both a naive transcript scan and the project's own purpose-built parser — meaning
   **the E1 empirical-basis statistics in SKILL.md (33.6% restatement share at pass
   7+, N=251) were likely computed on the same undercounting logic and should be
   distrusted until re-run with vocabulary normalization.**
2. **Cross-session plan continuation has no structured link.** A plan-mode session
   resumed after a context-window handoff gets a new, randomly-named plan file; the
   only pointer back to the prior file is hand-written prose at the top of the new
   file ("This file continues `~/.claude/plans/drifting-rolling-hinton.md`..."). No
   session-id, parent-session, or plan-id field exists anywhere in the schema.
   Filename co-occurrence in a transcript is not proof of continuation, and its
   absence is not proof of a break — only the prose lineage note is reliable, and nothing
   currently audits it.

These are real, both-machine-confirmed findings, and arguably more actionable than the
original citation-drift hypothesis: they undermine the project's own confidence in its
stress-test telemetry, not just one plan's convergence speed.

## Not yet re-verified

The "folds don't stick" finding (same defect re-flagged near-verbatim across passes,
observed via finding *text* not verdict tags) was not re-checked against the corrected
lineage boundaries. Less likely to share this specific bug (it doesn't depend on
verdict-tag parsing), but shouldn't be treated as confirmed until it is.

## Minor unrelated finding (correction 2026-08-27)

s3rbase dispatch `be485a91` (#1149 pass 5) returned verdict `CLEAN` with 7 active
findings. **This was originally characterized here as "CLEAN should be incompatible
with any nonzero finding count" — that invariant is wrong.** Per
`~/.claude/agents/stress-tester.md`, CLEAN does not require zero findings ("Suggestions
may exist"; the verdict reflects state *after* `Resolution` is applied, not the raw
finding count). The actual rule: a run that reported blocking findings but folded
every one of them *in the same pass*, with nothing deferred, may legitimately log
CLEAN. `be485a91`'s own Recommended Action text — "Fold these seven, then dispatch
pass 6" — states the findings were *not* folded in-pass, so it's still a genuine
verdict-integrity bug, just for a different, narrower reason than originally claimed.

## Recommended follow-up

- ~~Re-run the E1/corpus-audit statistics with vocabulary normalization~~ **Done**:
  `kaybenleroll/random_llm_projects#76` fixed `parse_stress_test_logs.py`'s handling
  of the `TAKE-STOCK RESOLVED — Option <A|C|D>` template (SKILL.md-prescribed, not the
  ad-hoc drift originally assumed). Corrected corpus distribution above. `E1`'s
  restatement statistics are unaffected (verified byte-identical `q_per_pass.csv`
  before/after) — no further re-run needed for those. `"LANDED"` / `"Direct fix... no
  dispatch"` style phrasings were not addressed by #76 (scoped out — no corpus
  instances found this pass) and remain open if they recur.
- Filed as `kaybenleroll/dotfiles#26`: enforce canonical verdict vocabulary at the
  source (SKILL.md/stress-tester.md), including the corrected CLEAN-requires-in-pass-
  fold invariant above, so future logs don't need parser-side special-casing at all.
- Filed as `kaybenleroll/dotfiles#27`: cross-session plan continuation structured
  lineage pointer (e.g. a `Supersedes:` field) rather than relying on prose a scanner
  has to parse correctly.
- Re-verify the fold-failure/recurrence finding independently before acting on it —
  still open, not actioned.

## Coverage caveats

- Neither re-verification agent had budget to hand-check every RERUN_NEEDED/RESTRUCTURE-
  tagged lineage in the full corpus (58 on the local machine alone) — the 78%-resolved
  estimate is extrapolated from a small hand-checked sample (5/5), not a full audit.
- s3rbase stretch-goal discovery of untracked lineages was not exhaustive.
- Two local lineages referenced in the original writeup ("busy-wait-guard plan",
  "pre-cap-count spec") turned out to have no traceable stress-test plan-file lineage
  at all on re-check — likely proportionality-gate-exempt trivial changes that never
  went through the formal plan+stress-test pipeline, not a data-loss case. Flagged as
  an attribution gap in the original writeup, not a process problem.
