# Effort benchmark (#120): does reasoning effort change plan-review recall?

Date: 2026-09-25. Status: single-task result, exploratory; Bayesian reading leads. Direction from the user: not worried about statistical significance; assess uncertainty intervals, Bayesian where possible, and decide on those. "untraced" = not found in a file I read. Paths are relative to the repo root; `E/` = `claude_code_research/.scratch/experiment-effort-20260924/`.

## Purpose and design
- Question: does `--effort` change how many of 13 seeded defects a tool-less reviewer finds in one synthetic plan (task 1)?
- Opus 5.5 and Sonnet 5 at medium/high/xhigh, n=10 each, default prompt (60 runs). Max arms: Sonnet max n=1 (recovered), plus two n=1 cap10 max arms (Opus, Sonnet). Fable (claude-fable-5-1) low/medium/high/xhigh/max, n=5 each, `cap10` prompt ("List at most 10 findings...").
- Harness: headless `claude -p`, Claude Code 2.1.282, `--setting-sources ""`, `--tools ""`, 2 parallel. Requested effort matched transcript effort in all 60 default-prompt runs (`results.md`).
- Judges: two blind LLM judges (Opus 5.5 medium primary, Sonnet 5 high sensitivity). Agreement 96.8%, kappa 0.94 (`results.md`).

## Method (source: `E/BAYES_RESULTS.md`, `E/bayes_analysis.py`; not re-run here)
- PyMC 6.3.2 NUTS, 4 chains x 1000 draws after 1500 tuning, target_accept 0.92.
- Bernoulli-logit per (run, item) detection: `logit p = mu + A[arm] + b[item] + c[run]`; item difficulty and run intercept hierarchical.
- Priors: mu N(0,2); arm effects independent N(0,1.5) (no smoothing across effort levels); sigma_b HalfN(2.5); sigma_c HalfN(1.5); interaction sigma_d HalfN(1); cap10 prompt delta N(0,1).
- Reported: expected recall (arm mean, /13) with 90% equal-tailed CrI; contrasts as differences of expected recall; P(>0), P(>1 item), P(|diff|<0.5) (ROPE).
- Diagnostics as reported: max R-hat 1.010, min bulk ESS 607, 0 divergences, 25/25 posterior predictive statistics inside 90% intervals; arm-by-item interaction model does not move answers.

## Arm table (primary judge, m1; Fable rows from the Fable-only fit; source `E/BAYES_RESULTS.md` sec. 2)
| arm | prompt | n | mean recall /13 [90% CrI] | mean cost $/run | mean out tokens/run | mean wall s/run |
|---|---|---|---|---|---|---|
| opus-medium | default | 10 | 6.58 [6.20, 6.99] | 0.340 | 14899 | 147 |
| opus-high | default | 10 | 6.50 [6.14, 6.89] | 0.461 | 19979 | 217 |
| opus-xhigh | default | 10 | 7.42 [6.94, 7.91] | 1.029 | 49401 | 472 |
| sonnet-medium | default | 10 | 6.68 [6.30, 7.09] | 0.201 | 17819 | 171 |
| sonnet-high | default | 10 | 7.61 [7.12, 8.11] | 0.325 | 30200 | 286 |
| sonnet-xhigh | default | 10 | 7.33 [6.88, 7.79] | 0.587 | 56368 | 520 |
| sonnet-max (recovered) | default | 1 | 6.79 [5.92, 7.91] | 2.751 | n/a | n/a |
| fable-low | cap10 | 5 | 5.65 [5.17, 6.13] | 0.419 | n/a | n/a |
| fable-medium | cap10 | 5 | 5.48 [4.99, 5.97] | 0.528 | n/a | n/a |
| fable-high | cap10 | 5 | 5.65 [5.18, 6.12] | 0.593 | n/a | n/a |
| fable-xhigh | cap10 | 5 | 6.31 [5.82, 6.82] | 1.191 | n/a | n/a |
| fable-max | cap10 | 5 | 6.15 [5.66, 6.68] | 2.207 | n/a | n/a |

Tokens and wall time: per-arm run means from `results.md` for the six default-prompt arms (`E/results.md`); n/a = not tabulated there. Wall times are under 2-parallel contention.

Also n=1 cap10 max arms: opus-5-5-max-cap10 6.25 [5.43, 7.20] at $1.986; sonnet-5-max-cap10 6.76 [5.90, 7.86] at $1.155 (same source). Bootstrap cost intervals are in the source.
Rounding differences between files: `results.md` (two-judge average) prints 6.6/6.5/7.4/6.8/7.6/7.3; `FABLE_BATCH_RESULTS.md` (Opus judge) prints 6.6/6.5/7.5/6.7/7.7/7.4 for the same six arms. Arm-table numbers above are posterior means from `BAYES_RESULTS.md`, not either raw column.

## Decision contrasts (primary judge, 90% CrI; source `E/BAYES_RESULTS.md` sec. 3a)
| contrast (items of 13) | mean diff [90% CrI] | P(>0) | P(>1 item) |
|---|---|---|---|
| Opus high - medium | -0.09 [-0.62, +0.45] | 0.39 | 0.00 |
| Opus xhigh - high | +0.92 [+0.32, +1.52] | 0.99 | 0.43 |
| Sonnet high - medium | +0.92 [+0.29, +1.56] | 0.99 | 0.42 |
| Sonnet xhigh - high | -0.28 [-0.94, +0.38] | 0.25 | 0.00 |
| Sonnet max(n=1) - xhigh | -0.54 [-1.52, +0.65] | 0.20 | 0.02 |
| Fable high - low | +0.00 [-0.66, +0.66] | 0.50 | 0.01 |
| Fable xhigh - high | +0.66 [+0.02, +1.34] | 0.95 | 0.20 |
| Fable max - xhigh | -0.16 [-0.88, +0.53] | 0.35 | 0.00 |
| Sonnet-high - Opus-high | +1.11 [+0.48, +1.75] | 1.00 | 0.62 |
| Sonnet-xhigh - Opus-xhigh | -0.09 [-0.75, +0.56] | 0.41 | 0.00 |

Judge sensitivity (sec. 3b/3c): contrast means move by at most 0.27 items; Sonnet high - medium weakens to +0.65 [+0.02, +1.30] under the Sonnet judge.

## Cost-effectiveness (source `E/BAYES_RESULTS.md` sec. 5; median extra items per extra $, 90% interval)
- Sonnet medium -> high: +0.92 items for +$0.124; 7.4 [2.3, 13.2]; P(ratio<0) 0.01. The standout step.
- Opus high -> xhigh: +0.92 items for +$0.568; 1.6 [0.6, 2.8]; P(ratio<0) 0.01.
- Opus medium -> high: -0.73 [-6.2, +4.2]; P(ratio<0) 0.61. Not supported.
- Sonnet high -> xhigh: -1.05 [-3.6, +1.5]; P(ratio<0) 0.75. Not supported.
- Fable high -> xhigh: 1.10 [0.03, 2.5], P(ratio<0) 0.05; Fable xhigh -> max: -0.16 [-0.94, +0.57], P(ratio<0) 0.65.
- Sonnet xhigh -> max (n=1): -0.27 [-0.70, +0.30]; P(ratio<0) 0.80.

## What the intervals support and do not
- Support: about +0.9 item (about 7 pp) at Sonnet medium -> high and Opus high -> xhigh; Sonnet-high the best recall and recall-per-dollar arm among well-sampled default-prompt arms; no gain from Sonnet high -> xhigh (P(xhigh worse) 0.75); Opus high indistinguishable from medium (P(|diff|<0.5) 0.86).
- Do not support: any step worth 2+ items (P(>1 item) never above 0.43); any benefit of max; a monotone effort dial. Non-monotone arms (Opus high < medium, Sonnet xhigh < high) are either a real plateau or arm-level noise; these data cannot tell which.
- n=1 arms have intervals about +/-1 item wide; they neither support nor refute max.

## Earlier significance-test summary (source `results.md`, `step4_findings.md`, `step4_tables.md` under `E/`)
Frequentist pass: recall flat at 50.4-58.5%; no comparison survives Holm across 12 (smallest Holm p 0.17); Opus xhigh vs medium +6.5 pp, permutation p=0.067, Holm 0.565. Read literally that is "nothing found". The Bayesian reading is more informative: the corrected tests could not resolve the roughly +0.9 item steps at Sonnet medium -> high and Opus high -> xhigh that the intervals show. Caveat: these intervals are unadjusted for the roughly 12 contrasts inspected, so the two largest are probably optimistic; the two views are consistent, not contradictory.

## Fable result
- 5.5-6.3/13, 1.1-1.3 items below Sonnet-high/Opus-xhigh (CrI about -0.4 to -2.0), but this is model plus prompt confounded: Fable used cap10 at n=5, the Opus/Sonnet arms the default prompt at n=10. The prompt effect is identified only by one n=1 pair; its posterior (+0.12 logit, CrI -1.3 to +1.6) is essentially the prior. Do not read this as a Fable deficit.
- Within Fable (identified): low = medium = high (about 5.6), xhigh +0.66 over high [+0.02, +1.34], max no better than xhigh; max costs 1.9x xhigh ($2.207 vs $1.191).
- Fable spend, summed by script from `cost_usd` in `E/runs-fable-pilot/*/[1-5].json` (25 cells): $24.72 review cost, including the stage-2 pilot's $4.80 (cell 1 of low/high/max, `PILOT_FABLE_RESULTS.md`) and the two other rep-1 cells. Chunk logs: `logs/chunk1.out`, `chunk2.out`, `chunk3.out`, `chunk1-resume.out`. chunk3 crashed with fable-xhigh rep 4 in flight; its cost was never recorded (untraced) and that run was redone in `chunk1-resume.out`, so the $24.72 excludes it. The 3 runs chunk3 completed before the crash (low/medium/high rep 4) are in the sum.
- Fable judging: 50 judgment files under `E/judgments-fable-pilot/`, `cost_usd` sums to $3.62 (script sum; not cross-checked against a log). Total Fable outlay about $28.34 by these sums.
- Pilot (n=1, budget $6): low 0.813, high 0.971, max 3.019 (max output 50,867 tokens, 45,405 thinking). Whole 60-run default sweep: $29.44 review + $10.95 judge = $40.39 (`results.md`, `audit_tokens.md`).

## Per-level recommendation (restates the decisions and intervals above; no new claims)
| level | recommendation | reason |
|---|---|---|
| Sonnet medium | use (cheap baseline) | 6.68 [6.30, 7.09] at $0.201/run; high adds +0.92 items [+0.29, +1.56] for +$0.124. |
| Sonnet high | use (default) | Best recall and recall-per-dollar among well-sampled default-prompt arms: 7.61 [7.12, 8.11] at $0.325/run. |
| Sonnet xhigh | avoid | -0.28 [-0.94, +0.38] vs high for +$0.26/run; P(ratio<0) 0.75 (#184 deny kept as a dated cost default). |
| Opus high | avoid (no measured gain over medium) | Indistinguishable from medium: -0.09 [-0.62, +0.45], P(|diff|<0.5) 0.86; $0.461 vs $0.340/run. |
| Opus xhigh | escalate-only | +0.92 items over high [+0.32, +1.52] at 2.2x the cost ($1.029/run); P(>1 item) 0.43; no per-effort escalation rule adopted. |
| max | inconclusive | n=1 arms, intervals about +/-1 item; no benefit shown, stays off the sweep. |

## Decisions taken
- #184 (closed; dotfiles PR #187 merged, squash 792d98a): Sonnet xhigh/max deny kept as a dated cost default (measured 2026-09-24, n=10/arm), not a capability limit; remediation puts `effort:"high"` first. The Bayesian result is consistent: Sonnet high -> xhigh is -0.28 [-0.94, +0.38] items for +$0.26/run, P(ratio<0) 0.75. Merge and squash hash are from the caller's brief, not re-verified here.
- Max stays off the sweep; no per-effort escalation rule for Opus adopted on this evidence (Opus xhigh gains about 0.9 item at 2.2x the cost of high, P(>1 item) 0.43).

## Caveats
- One synthetic, tool-less task, 13 items, one target document; results describe this document, not review quality generally.
- Contrasts are unadjusted (about 12 inspected, no pooling across arms), so the largest gains are probably optimistic.
- Sonnet-max is a truncation-recovered run (`budget_exhausted`), costing $2.75; an anecdote. No default-prompt Opus max arm exists.
- Judge choice moves contrasts by at most 0.27 items; both judges share model families with reviewers.
- Cost is `total_cost_usd` (API-list equivalent), not subscription spend.
- anthropics/claude-code#93596 (Opus 5 xhigh output tokens up 2-7x from about 2026-09-11): comparability with earlier runs unverified.
- Wall times are under 2-parallel contention.

## Untraced
- Cost of the crashed in-flight fable-xhigh rep 4 run in chunk3.
- Fable judging cost from any log (only the sum of judgment-file fields).
- Any Fable spend outside `runs-fable-pilot/` and `judgments-fable-pilot/`.

## Raw files and reproduction
- `claude_code_research/.scratch/experiment-effort-20260924/`: `BAYES_RESULTS.md`, `bayes_analysis.py`, `results.md`, `step4_*`, `FABLE_BATCH_RESULTS.md`, `PILOT_FABLE_RESULTS.md`, `audit_tokens.md`, `runs/`, `runs-fable-pilot/`, `judgments*/`, `logs/`.
- Reproduce: from `E/`, `bayes_venv/bin/python bayes_analysis.py` (seed 20260925). `bayes_venv/` and `bayes_cache/` are untracked local artefacts; `.scratch/` is git-ignored (`.gitignore:62`).
