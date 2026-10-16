# Compact vs handoff evaluation (2026-10)

Evidence behind the `manage-context` rebalance (kaybenleroll/dotfiles#404, PR #407). Window 2026-08-16 to 2026-10-16, both machines (local and s3rbase), main-thread transcripts only.

## Method

- Script: `ctx_eval.py ROOT [--out DIR] [--from DATE] [--to DATE]`, kept at `.scratch/ctx-eval/scripts/ctx_eval.py` (not promoted to `artifacts/`: it detects the old `new-session` skill by name and is a script, not a portable runbook).
- Run over `~/.claude/projects` on each machine; raw outputs `.scratch/ctx-eval/local-summary.txt` and `s3rbase-summary.txt`.
- Compaction events come from `type: system`, `subtype: compact_boundary` records with `compactMetadata{trigger, preTokens, postTokens, ...}`; the summary turn carries `isCompactSummary`.
- Handoffs are `new-session` skill runs with a linked successor session. Successors and fresh-start baselines exclude the starter prompt from the signal window.
- Comparison window: the next 10 human turns after each event (context size per API call, read-before-edit behaviour, loss-signal regex hits for "again", "remember", "earlier", "we discussed" etc.).

## Results

| | local | s3rbase |
|---|---|---|
| compaction events (all manual) | 27 (24 real, 3 test) | 11 |
| new-session runs / produced handoff / linked successor | 352 / 331 / 310 | 237 / 233 / 223 |
| compaction preTokens median (q1-q3) | 214,362 (165,720-300,770) | 285,493 (210,593-326,211) |
| compaction postTokens median | 16,055 | 24,321 |
| handoff ctx before, median | 310,174 | 336,210 |
| sum ctx over next 10 turns, median: compact / handoff / fresh | 4,015,572 (real) / 9,318,892 / 4,745,546 | 3,402,844 / 11,066,229 / 5,921,882 |
| median ctx per call, next 10 turns: compact / handoff | 95,295 / 157,182 | 139,802 / 193,781 |
| first-call total tokens, median: compact / handoff | 61,305 / 92,274 | 101,643 / 129,320 |
| loss signals per 10 turns, pooled: compact / handoff / fresh | 0.17 (3/177) / 0.30 (78/2592) / 0.44 (29/652) | 0.00 (0/93) / 0.24 (45/1890) / 0.27 (5/186) |
| turns after event, median: compact / handoff | 14.5 / 13.0 | 18 / 13 |
| handoff skill-run cost (sum ctx), median | 1,197,010 | 1,267,988 |
| compaction sessions later running new-session | 19 of 27 | 11 of 11 |

Local compactions ending within 2 turns: 4 of 24 (compact-real); none on s3rbase.

## Caveats

- Observational. The user chose where to compact, so event selection is not random.
- Small n for compaction (24 real local, 11 s3rbase).
- Loss-signal regex is roughly 85-90% false positives (conversational uses of "again"), so quality parity is not established; the rates above are not a quality measure.
- Compaction mostly delays a handoff rather than replacing it (see the last table row), and the 10-turn window omits that later handoff cost.
- Handoff cost figures include the skill run itself (about 1.2M ctx tokens), which the compaction side does not pay but the compaction summarisation call (preTokens) is a separate cost.

## Run classification (skill usage, 21 days to 2026-10-15)

76 `new-session` runs: 48 forced or explicit handoff requests, 28 genuine assessments. All 28 genuine runs returned new-session; 72 of 76 overall returned new-session, 0 continue, 0 compact, 4 undetermined. Six of the genuine runs were the user asking whether to compact (175k-311k tokens). Figures in the issue (88 runs, 23 compactions) did not reproduce.

## AC1 replay (verdicts after the change)

Scripted replay, sonnet, no tools, 3 runs per fixture (f10: 8 runs); first-line verdict compared (`.scratch/ctx-eval/ac1-replay-v2.tsv`).

- 13 fixtures f1-f13: all matched, 3/3 each; f10 8/8.
- 6 recorded "should we compact?" asks (tsv47, 51, 55, 56, 57, 75): all Compact, under an assumed same goal and phase boundary (a model-judgement input, not observed).

## How to re-run

1. On each machine: `python3 ctx_eval.py ~/.claude/projects --from YYYY-MM-DD --to YYYY-MM-DD > summary.txt`.
2. Compare the COMPARISON blocks (compact, compactReal, handoff, fresh-base) and the COMPACTIONS / NEW-SESSION RUNS headers.
3. Update the skill name matched in the script if the handoff skill is now `manage-context` (lines matching `new-session` near the handoff detection).

Re-measure after 10 compactions have occurred under the new policy; compare cost (sum ctx over 10 turns), the share of compactions followed by a handoff, and the verdict mix of `manage-context` runs against the baseline above.
