# Issue #57 Phase 3 — reviewer effort tier vs real-defect recall (analysis)

## Context

Issue #57 asks whether stress-test reviewer effort tier (Opus medium/high/max) drives real
defect-finding quality, or whether the repeated-rounds pattern (not per-pass effort) is what
actually costs tokens. Phase 1-2 ran a 4-arm x n=5 benchmark: Arms A/B/C are Opus at
medium/high/max effort respectively, reviewing the same synthetic, defect-injected target
document (13 known injected defects, no seeding-purpose leakage) with the stress-test skill;
Arm D is a Fable-model comparison arm with no effort parameter. Each of the 20 review passes
was scored by a blind judge (LLM) against the 13-item answer key, with no arm/tier identity
exposed to the judge. This note reports the Phase 3 analysis of those 20 judged passes.

## Data quality check

Recomputed `recall_count` for every pass directly from its `key_items` array (`found:true`
count) rather than trusting the judge's self-reported `recall_count`, and checked
`total_key_items`/array length against the expected 13.

- All 20 passes: `key_items` array length = 13, `total_key_items` = 13. Correct throughout.
- Two judge self-reporting errors found (stated `recall_count` off by one from the actual
  found-count):
  - **B3**: judge stated `recall_count=6`, but only 5 `key_items` entries are `found:true`.
  - **D4**: judge stated `recall_count=6`, but only 5 `key_items` entries are `found:true`.
  - All tables below use the **recomputed** recall (counted directly from `key_items`), not
    the judge's stated number, for every pass — including these two.
- `extra_findings[].verdict` took only one value across all 20 passes: `"genuine-novel"`. No
  pass produced a finding the judge marked spurious/non-genuine. Spurious-extra-finding count
  is therefore 0 for every rep in every arm — reported as such below, not omitted.
- No missing records: 20/20 expected (armId x rep) combinations present, one each for
  A1-A5, B1-B5, C1-C5, D1-D5.

## Per-arm results

Recall = recomputed found-count / 13 key items.

### Arm A — Opus, medium effort

| rep | recall | genuine-novel | spurious | pass_status |
|---|---|---|---|---|
| 1 | 7/13 | 5 | 0 | RERUN_NEEDED |
| 2 | 7/13 | 8 | 0 | RERUN_NEEDED |
| 3 | 6/13 | 8 | 0 | RERUN_NEEDED |
| 4 | 7/13 | 5 | 0 | RERUN_NEEDED |
| 5 | 6/13 | 5 | 0 | RERUN_NEEDED |

Recall mean: 6.60/13 (50.8%). Range: **6-7/13**. Genuine-novel mean: 6.20. Spurious mean: 0.
Status: RERUN_NEEDED x 5.

### Arm B — Opus, high effort

| rep | recall | genuine-novel | spurious | pass_status |
|---|---|---|---|---|
| 1 | 6/13 | 6 | 0 | RERUN_NEEDED |
| 2 | 6/13 | 7 | 0 | RERUN_NEEDED |
| 3 | 5/13 | 6 | 0 | RERUN_NEEDED |
| 4 | 5/13 | 8 | 0 | RERUN_NEEDED |
| 5 | 7/13 | 9 | 0 | RERUN_NEEDED |

Recall mean: 5.80/13 (44.6%). Range: **5-7/13**. Genuine-novel mean: 7.20. Spurious mean: 0.
Status: RERUN_NEEDED x 5.

### Arm C — Opus, max effort

| rep | recall | genuine-novel | spurious | pass_status |
|---|---|---|---|---|
| 1 | 4/13 | 7 | 0 | RERUN_NEEDED |
| 2 | 8/13 | 8 | 0 | RERUN_NEEDED |
| 3 | 6/13 | 5 | 0 | RERUN_NEEDED |
| 4 | 7/13 | 9 | 0 | RERUN_NEEDED |
| 5 | 6/13 | 9 | 0 | RERUN_NEEDED |

Recall mean: 6.20/13 (47.7%). Range: **4-8/13**. Genuine-novel mean: 7.60. Spurious mean: 0.
Status: RERUN_NEEDED x 5.

### Arm D — Fable, no effort parameter (reported separately, not ranked against Opus tiers)

| rep | recall | genuine-novel | spurious | pass_status |
|---|---|---|---|---|
| 1 | 5/13 | 5 | 0 | RERUN_NEEDED |
| 2 | 6/13 | 5 | 0 | RERUN_NEEDED |
| 3 | 6/13 | 4 | 0 | RERUN_NEEDED |
| 4 | 5/13 | 5 | 0 | RERUN_NEEDED |
| 5 | 6/13 | 5 | 0 | RERUN_NEEDED |

Recall mean: 5.60/13 (43.1%). Range: **5-6/13**. Genuine-novel mean: 4.80. Spurious mean: 0.
Status: RERUN_NEEDED x 5.

## Decision rule verdict (pre-registered: separate only if n=5 recall ranges don't overlap)

| Pair | Range A | Range B | Result |
|---|---|---|---|
| A (medium) vs B (high) | 6-7 | 5-7 | **Overlap — no detectable difference at n=5** |
| A (medium) vs C (max) | 6-7 | 4-8 | **Overlap — no detectable difference at n=5** |
| B (high) vs C (max) | 5-7 | 4-8 | **Overlap — no detectable difference at n=5** |

All three pairwise Opus-tier comparisons overlap. Per the fixed decision rule, none of the
three effort tiers is separable from the others on real-defect recall at n=5. Point estimates
are not meaningfully ordered either — mean recall was highest for medium (50.8%), then max
(47.7%), then high (44.6%); this ordering is noise-consistent with fully overlapping ranges,
not evidence of a medium > max > high ordering.

## Sanity threshold check

Requirement: Arm B (high) mean recall ≥ 30% of 13 (≥ ~3.9/13).

Arm B mean recall = 5.80/13 (44.6%) ≥ 3.9/13. **PASS.** The harness is producing recall well
above the floor that would indicate a broken prompt/judge pipeline, so the other arms'
near-identical results are read as a genuine null result, not a broken measurement.

## Known limitations (stated, not papered over)

- **Per-pass wall-clock not reliably captured; per-pass tokens WERE recovered post hoc
  (and the earlier reconciliation failure was a measurement bug, since fixed).**
  The Workflow scripting API doesn't expose per-`agent()` usage/timing to the script body —
  only an aggregate total across the whole run (~2.66M tokens across all 40 agent calls).
  An earlier pass at recomputing per-agent tokens from the raw transcript JSONL files
  (`~/.claude/projects/.../subagents/workflows/wf_6e9950c6-d45/agent-*.jsonl`) summed
  `input_tokens + cache_creation_input_tokens + cache_read_input_tokens + output_tokens`
  across every turn after deduplicating by `requestId`, giving a 40-call total of
  5,030,931 — roughly 1.9x the ~2.66M aggregate, with no tested alternative reconciling
  either. **That was a bug in the recomputation, not a discrepancy in the Workflow tool's
  own number.** Root cause: prompt-cache usage is cumulative per conversation — each
  turn's `cache_read_input_tokens` already includes everything cached in earlier turns —
  so summing every turn's full usage block re-adds already-counted context once per
  subsequent turn (worse with more turns: ~1.6x inflation on a 2-turn agent, ~15x on a
  12-turn agent).

  Fix, validated against 6 ground-truth `subagent_tokens` values from this session's
  standalone (non-Workflow) Agent-tool calls (each with an authoritative harness-reported
  total): the correct per-agent token count is the **last unique-`requestId` turn's
  `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`, excluding that
  turn's own `output_tokens`** — the final turn's input-side fields alone already carry
  the full cumulative context size, and the final output is never fed back into a later
  turn. All 6 ground-truth agents matched to within 0.2% (e.g. official 105,080 vs.
  formula 104,929; official 35,167 vs. formula 35,155 — full table in
  `claude_code_research/.scratch/experiment-57/scores/token-breakdown-notes.md`).
  Applying the corrected formula to the 40-call Workflow run gives a total of
  **2,659,244** — matching the Workflow tool's own ~2.66M aggregate to within 0.03%.
  The Workflow tool's number was right all along.

  Per-arm, per-role token counts (mean of n=5, corrected formula; `tokens` is a
  context-size metric — see caveat below — `mean output tokens` is the correctly-summed
  generation cost):

  | Arm | Role | Mean tokens (context) | Mean output tokens | Mean wall time (s) |
  |---|---|---|---|---|
  | A (opus/medium) | review | 46,536 | 10,110 | 139.7 |
  | A (opus/medium) | judge | 86,529 | 5,654 | 61.7 |
  | B (opus/high) | review | 46,543 | 17,812 | 240.2 |
  | B (opus/high) | judge | 87,371 | 5,824 | 66.0 |
  | C (opus/max) | review | 46,543 | 30,651 | 401.0 |
  | C (opus/max) | judge | 89,227 | 7,468 | 83.2 |
  | D (fable) | review | 46,530 | 8,884 | 121.7 |
  | D (fable) | judge | 82,569 | 4,080 | 48.2 |

  Caveat: because the corrected formula excludes the final turn's own `output_tokens`,
  the `tokens` column is a context-size figure (total prompt tokens processed over the
  run), not a full cost figure — it's now nearly identical across arms (~46.53k on the
  review pass) since the same ~55KB target document dominates context regardless of
  effort tier. **Higher effort tiers still cost more overall** — that shows up entirely
  in `output_tokens`, which climbs medium(10.1k) → high(17.8k) → max(30.7k) review-pass
  output, a 3x increase, unaffected by this fix. Wall time scales even more sharply
  (140s → 240s → 401s, ~2.9x). So the null result on recall (below) was not free:
  max-effort review passes cost ~3x the output tokens and ~2.9x the wall time of medium
  for no detected recall gain. For a fuller per-pass cost estimate, use
  `tokens + output_tokens` together, not `tokens` alone. Judge-side tokens are noisier
  (driven by review-text length fed to the judge, plus at least one long outlier run per
  arm in C and D) and don't cleanly track reviewer effort tier. Full 40-row breakdown
  (`armId,rep,role,agentId,tokens,tokens_old_buggy,output_tokens,thinking_tokens,
  wall_seconds`) is at `claude_code_research/.scratch/experiment-57/scores/token-breakdown.csv`
  (`tokens_old_buggy` kept for provenance only — do not use in analysis). Wall-clock time
  was recoverable from transcript timestamps for these 40 calls (first-to-last message delta
  per agent, included above/in the CSV) — so wall time was never an unrecovered gap.
- **Single, unreplicated judge.** Each pass was scored once by one LLM judge call with no
  inter-rater or repeated-judging check; judge scoring noise is not distinguished from
  reviewer-quality noise in the numbers above (the two found off-by-one self-reporting errors,
  see Data quality check, are consistent with this being a real but small effect).
- **Realism tradeoff.** The target is a synthetic, defect-injected document built specifically
  for this benchmark, not a real production plan/PR; findings may not transfer to organically-
  occurring defects in real review targets.
- **Fable model/effort unverified.** Arm D's exact model identity and effort configuration
  were not independently verified beyond the `st-arm-d.md` agent file's stated (lack of)
  effort parameter — treat Arm D's numbers as directional only, not as a controlled
  comparison against the Opus tiers.
- **n=5 per arm.** The decision rule was fixed in advance specifically because n=5 is too
  small to support anything beyond a range-overlap check; this is not a study capable of
  detecting a small-to-moderate true effect size.

## Answer to issue #57's question

At n=5 per arm, on this synthetic target, **Opus effort tier (medium/high/max) shows no
detectable effect on real-defect recall** — all three pairwise range comparisons overlap, and
mean recall differences (44.6%-50.8%) are small and not ordered in the direction "higher
effort tier finds more real defects." The sanity check confirms the harness itself is working
(Arm B clears the 30% floor by a wide margin), so this reads as a genuine null result for
effort tier as a lever, at least in the range medium-to-max, not a broken measurement.

Effort tier is not free, though: recovered per-pass token/timing data (see Known limitations)
shows medium→max costs ~3x the output tokens and ~2.9x more wall time on the review pass
alone, with no recall gain to show for it — so this is a genuine negative cost/quality
tradeoff, not just a null effect.

This is consistent with issue #57's original suspicion: the *repeated-rounds* pattern (not
per-pass effort level) is the more likely driver of stress-test's token cost and of any
quality gains from re-running review, since bumping effort tier alone did not move recall in
this benchmark. This run does not test the repeated-rounds hypothesis directly — that remains
open — but it does rule out "just crank effort tier higher" as a substitute for it, within the
limitations above (n=5, single judge, synthetic target).

Spurious extra-findings were zero across all 20 passes at every tier, including Fable — at
least on this target, none of the four configurations produced findings the judge scored as
non-genuine, so effort tier's absence of effect on recall is not offset by an effort-tier
effect on false-positive rate either.
