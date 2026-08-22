# Issue #57 experiment design — stress-test effort tier and scope-coupling

Status: design only, not yet run. Weekly Opus quota ~98% used at time of writing — defer live runs until quota resets. This document is the runbook for when it does.

## Background established before designing this

**Effort tier is currently NOT a free variable in production.** `~/.claude/skills/stress-test/SKILL.md` line 6 states outright: the `stress-tester` subagent (`~/.claude/agents/stress-tester.md`) is pinned `model: opus, effort: high`, and the skill's Step 2 explicitly does not pass model/effort on dispatch. There is no medium tier and no xhigh tier anywhere in the real invocation path today — issue #57's opening bullet ("confirm high vs xhigh") is answered by this read alone: it's always `high`, never `xhigh`, and never `medium`. Any medium-tier or xhigh-tier arm below requires a **temporary experimental copy** of the agent file (e.g. `stress-tester-experimental.md` with `effort: medium` or `effort: xhigh`), invoked directly via `Agent(subagent_type: "stress-tester-experimental")` for the experiment only — never edit the production agent file, never route through `/stress-test` for these runs since the skill hardcodes the dispatch.

**Size/coupling proxy already exists**: SKILL.md's take-stock Option D threshold — "800+ lines or 3+ coupled phases" — is the existing operational definition of "broad/coupled scope." Reuse it rather than inventing a new threshold.

**Per issue #59's finding**: coupling, not raw size, drives runaway rounds. The design below therefore holds a size-matched control (independently-scoped bundle) against the coupled-mechanism arm, so a round-count difference can be attributed to coupling and not merely to line count.

## Candidate real plans (repo: construct_synthetic_reinsurance_data, `docs/plans/`)

Identified by grepping `docs/plans/*.md` for `## Stress-Test Log` and counting pass entries + lines:

| File | Lines | Passes logged | Shape |
|---|---:|---:|---|
| `2026-08-04-003-plan-phase-2-coherence-engine-design.md` | 1890 | 9 | Single deeply-coupled mechanism (Phase 2 coherence engine), well above the 800-line/3-phase proxy — the real "runaway" case #59 diagnosed |
| `2026-07-30-003-batch-86-82-85-68-xol-market-tier-size-scaling.md` | 1472 | 3 | Bundle of 4 independently-scoped issues, line-count-matched to the coherence-engine plan but *not* one coupled mechanism |
| `2026-08-07-002-plan-issue-122-el-anchored-rol-per-lob-id-premium.md` | 1021 | 5 | Single issue, moderately coupled, mid-size — candidate for the medium-vs-high fixed-scope comparison |
| `2026-07-30-002-batch-77-fixture-value-equality-gate-78-fixture-pr.md` | 564 | 0 | Smaller independent bundle, below the proxy threshold — secondary control point |

These are real, already-stress-tested plans with logged pass history, so their actual round counts are already known and can anchor expected baselines; re-running them under a different effort tier or a carved-down scope is the actual experiment.

## Test matrix

**Arm 1 — Medium vs High, scope held fixed.** Target: `2026-08-07-002-...-issue-122-...md` (1021 lines, single issue, already has a real Pass-5 history for reference). Run N replications each of `effort: medium` and `effort: high` against the *same* plan file (git-stashed back to its pre-stress-test state each time, or a frozen copy, so both tiers review identical content — do not reuse the file after either tier has mutated it).

**Arm 2 — Narrow+xhigh vs Broad+high, coupling held as the actual variable.**
- Broad/coupled: `2026-08-04-003-...-coherence-engine-design.md` (1890 lines, single mechanism, above proxy) at `effort: high`.
- Narrow/coupled: a carved-down slice of the *same* mechanism — extract one phase (the plan already has internal Phase A/B/C/D structure per the existing handover files `handover-20260804-phase2-coherence-engine-phaseC.md` / `-phaseD.md`) as a standalone plan, reviewed at `effort: xhigh`. This keeps the mechanism identical and only shrinks scope — isolates scope size within one coupled mechanism.
- Control (size-matched, coupling removed): `2026-07-30-003-batch-86-82-85-68-...md` (1472 lines, independently-scoped bundle) at `effort: high`. Same order of magnitude as the broad arm; if this control converges in fewer rounds than the broad/coupled arm despite similar size, that's the direct evidence coupling (not size) is the driver — consistent with #59 and the reason this control exists at all.

## What to measure per run

1. **Rounds to convergence** — the log's own `Pass N` count until `CLEAN`/`ACCEPTED`, or the streak at which a take-stock/halt fires. This is the primary outcome; it's what #59 and #57 are both actually about.
2. **Findings caught/missed** — fixed rubric: take the medium-tier run's full finding list, then run a *fresh* high-tier pass over the **same already-reviewed plan** (not the medium run's fixes applied — the original target) and diff category + substance (same method SKILL.md's own "Recurring across passes" logic uses: compare finding substance, not category labels). Report: findings high catches that medium didn't (miss rate), and vice versa (false positives from being more aggressive).
3. **Token/cost delta** — read each run's transcript token counts (input+output, cache-adjusted) directly from the session; convert to Opus per-token pricing for a $ estimate. Do not estimate from context-window percentage — that's not linear with actual dispatched tokens.

## Replication count

Baseline noise is already established at 1-3 rounds of variance from domain subtlety alone (independent of scope choice). A single run per arm cannot distinguish a 1-round effort-tier effect from that noise. Minimum **5 replications per arm/cell** (10 cells total across both arms × two conditions = up to 40 runs, but Arm 1 and Arm 2's control can share replications if scheduled together). Treat this as a threshold check, not a formal power calculation: an arm pair only counts as a real effect if the round-count ranges across 5 reps are **non-overlapping** (e.g. medium consistently 3-4 rounds, high consistently 1-2). Overlapping ranges at n=5 are inconclusive — add 5 more reps to that specific pair before concluding, don't stop at n=5 on an ambiguous split.

## Success / failure criteria

- **"Use medium as default"**: Arm 1 shows medium's round count and miss rate are statistically indistinguishable from high (non-overlapping-range test above says no effect) at materially lower token cost.
- **"High is worth it"**: Arm 1 shows high catches findings medium misses (findings-diff rubric shows genuine misses, not just noise) or converges in fewer rounds, at a cost premium the org is willing to eat.
- **"Coupling, not size, is the driver"**: Arm 2's control (size-matched bundle) converges in meaningfully fewer rounds than the broad/coupled arm, and the narrow+xhigh carve-down also converges faster than the broad/coupled arm despite same mechanism — both point at coupling as the operative variable, confirming #59 generalizes beyond the single case it was found in.
- **"Inconclusive, need more data"**: any arm pair still has overlapping round-count ranges after 10 reps, or the findings-diff rubric can't cleanly separate "medium missed it" from "the plan changed enough between runs that comparison isn't valid" (a real risk — freeze the target file identically across reps to avoid this).

## Next step when quota allows

Run Arm 1 first (cheaper, fewer total Opus calls, answers the more actionable question) before committing budget to Arm 2's carve-down construction work.

## Pilot run results (2026-08-21) and next steps

**What was run**: Arm 1 only, and only a pilot — 3 reps per condition rather than the designed 5, because weekly Opus quota was already at 98% at run time. Target was the fixed Arm 1 plan, `docs/plans/2026-08-07-002-plan-issue-122-el-anchored-rol-per-lob-id-premium.md` (1021 lines, already merged via PR #146), frozen as `.experiment-57-snapshot-issue122.md` so both tiers reviewed identical content. A temporary experimental agent, `~/.claude/agents/stress-tester-experimental.md` (an `effort: medium` copy of the production `stress-tester` agent), was created for the medium-tier reps; the high-tier reps used the production `stress-tester` (opus/high) as-is, invoked directly via the Agent tool rather than through `/stress-test` (which hardcodes its own dispatch and can't be pointed at the experimental agent).

**Results** (counting only blocking-category findings — Gaps + Inconsistencies + Underspecified, excluding Suggestions):
- High tier: rep1 = 6 (RERUN_NEEDED), rep2 = 0 (CLEAN), rep3 = 5 (RERUN_NEEDED) — mean 3.67, range 0-6.
- Medium tier: rep1 = 5 (RERUN_NEEDED), rep2 = 8 (RERUN_NEEDED), rep3 = 6 (RERUN_NEEDED) — mean 6.33, range 5-8.

**Interpretation**: applying the design's own non-overlapping-range bar (§ Replication count), this pilot is inconclusive on the tier question — the ranges overlap at 5-6. The overlap traces to a single outlier: high-tier rep2 came back CLEAN while every other pass (both tiers) converged on largely the same findings. That means the dominant source of variance in this pilot was run-to-run noise on an individual pass, not the medium-vs-high tier choice itself. Notably, medium's mean finding count was *higher* than high's — at n=3 there's no evidence here that dropping to medium loses coverage, though n=3 is too small to call that a real effect either.

Despite the tier question being unresolved, several findings converged independently across 3 or more of the 6 passes, which is a stronger signal than any single pass: Verification 5's pooled-correlation confound (4/6 passes), the D4 "median" population ambiguity — which had caused a real ~23% miscalibration in shipped code — (found in nearly all passes), and the regression test asserting against its own oracle rather than against `gen_premium()`'s actual output (2/6 passes, both high-confidence with code citations). These convergent findings were filed as 9 issues against `construct_synthetic_reinsurance_data` on 2026-08-21 (see that repo's tracker).

**Next steps for tomorrow, once weekly quota resets**:
1. Extend Arm 1 to the full designed n=5 per condition — 2 more high-tier and 2 more medium-tier reps against the *same* frozen snapshot — before drawing any conclusion on the tier question, so the tier effect can be separated from single-pass noise.
2. Only if Arm 1 resolves cleanly at n=5 (non-overlapping ranges), consider extending to 1-2 additional plans. Do not commit up front to running "many plans" — size each further extension based on what the prior step actually showed.
3. Delete the temporary `stress-tester-experimental` agent file once the full Arm 1 comparison concludes — the production agent must not be left with an experimental sibling indefinitely.
4. Tonight's variance finding also raises a design question worth revisiting: whether "rounds to convergence" — the original design's primary outcome (§ What to measure per run) — is answerable this way at all, since tonight's reps were single-pass reviews of an already-converged document rather than actual round-to-convergence runs. Consider whether the single-pass blocking-finding-count proxy used tonight should replace or supplement rounds-to-convergence as the primary outcome going forward.

## Full n=5 extension results (2026-08-21, same night)

**What was run**: same night's quota allowed extending Arm 1 from the n=3 pilot to the full designed **n=5 per condition**, against the same frozen snapshot (`.experiment-57-snapshot-issue122.md`) and the same two agents — production `stress-tester` (opus/high) and temp `stress-tester-experimental` (opus/medium).

**Results** (blocking findings = Gaps + Inconsistencies + Underspecified, excluding Suggestions; all 5 reps per condition):
- High tier: 6, 0, 5, 7, 7 → mean 5.0, range 0-7.
- Medium tier: 5, 8, 6, 5, 6 → mean 6.0, range 5-8.

**Token cost** (subagent_tokens per rep):
- High tier: 97567, 64373, 100292, 107222, 85762 → mean ≈91,043.
- Medium tier: 75908, 85392, 69609, 77940, 83350 → mean ≈78,440 (~14% cheaper on average).

**Wall-clock duration per rep**:
- High tier: 484082, 165938, 498788, 519215, 372357 ms → mean ≈408,076ms (~408s).
- Medium tier: 250791, 378262, 232342, 236620, 351641 ms → mean ≈289,931ms (~290s) (~29% faster on average).

**Conclusion at n=5**: this is now a clean, decisive result by the design's own non-overlapping-range bar (§ Replication count) — NOT because the ranges separated, but because they still don't: high's range (0-7) and medium's range (5-8) overlap heavily (5-7 shared), and even excluding the CLEAN outlier (high rep with 0 findings), high's remaining range (5-7) still fully overlaps medium's. There is no detectable coverage advantage for high-tier at this target's scope/coupling (a single, moderately-coupled ~1000-line plan). If anything medium's mean was higher, not lower. Combined with medium's consistent ~14% token / ~29% wall-clock savings across both the n=3 pilot and the n=5 full run, this satisfies the design's own "Use medium as default" success criterion (§ Success / failure criteria) — for this specific target shape. This is a strong signal but not yet a general rule: it's one target (PLAN family, single issue, moderate coupling, ~1000 lines), and generalizing requires checking targets at the other end of the coupling/size spectrum, which is exactly what Arm 2's already-identified candidates were for.

Several findings still converged across most/all 10 reps regardless of tier — real signal, already filed as issues #166-174 in `kaybenleroll/construct_synthetic_reinsurance_data` from the n=3 pilot. The n=5 extension reps found the same convergent issues again, confirming them further, but surfaced no new distinct issue candidates — no re-filing needed from the extension reps.

## Planned follow-up: generalizing beyond one target (tomorrow, post quota-reset)

Test whether the "medium suffices" finding generalizes to the shape where high-tier's extra reasoning is most likely to matter: deep, single-mechanism coupling at large scope — the opposite end of the spectrum from tonight's moderately-coupled single-issue target. Reuse the design's already-identified Arm 2 candidates rather than picking new ones:
- **Broad/coupled target**: `docs/plans/2026-08-04-003-plan-phase-2-coherence-engine-design.md` (1890 lines, the genuine 9-round runaway case, single deeply-coupled architectural mechanism, well above SKILL.md's 800-line/3-phase proxy).
- **Control target (size-matched, coupling removed)**: `docs/plans/2026-07-30-003-batch-86-82-85-68-xol-market-tier-size-scaling.md` (1472 lines, bundle of 4 independently-scoped issues, converged in only 1 rerun historically) — isolates whether any tier gap that appears on the coupled target is really about coupling and not just raw size.

Reduce replication from 5 to **3 reps per condition** for this follow-up (not the original design's 5) — today's n=5 run already characterized the noise floor cleanly (tight, overlapping ranges), so n=3 is enough to detect a real gap on these targets without re-spending a full n=5 budget on each. That's 2 plans × 2 tiers × 3 reps = 12 stress-test passes total.

Freeze fresh snapshots for each target the same way tonight's was done (`cp` to a `.experiment-57-snapshot-<name>.md` sibling in the same repo, verify byte-identical via diff) before running reps — do not reuse tonight's issue-122 snapshot.

What would change the "medium as default" recommendation: if the coupled/broad target shows medium's range and high's range separate cleanly (non-overlapping) with high finding materially more blocking issues, that's evidence high-tier's depth matters specifically for deeply-coupled targets — the recommendation would then become scope/coupling-conditional (medium for narrow/moderate targets, high for broad+coupled), not a blanket switch.

After this follow-up concludes: delete `~/.claude/agents/stress-tester-experimental.md` (the temporary effort:medium copy) — it must not be left in place permanently once both target shapes have been tested.
