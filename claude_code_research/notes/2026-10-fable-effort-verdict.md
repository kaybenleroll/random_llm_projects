# Fable 5.1 effort verdict (#121): effort is applied

Date: 2026-10-17. Closes `kaybenleroll/random_llm_projects#121`. Status: verdict on one task (task 1, plan review); cross-task generalisation not measured. Companion note: `notes/effort-benchmark-120.md` (Opus/Sonnet and Fable recall, shared harness). Numbers were re-derived by script on 2026-10-17 from a tidy run table and the Bayesian output (both under the git-ignored `.scratch/`, described under Data provenance); the raw run JSONs are not in git.

## Verdict

**Effort is applied on Fable 5.1.** Decision rule, verbatim from the issue (fixed before running):

> call effort 'ignored' on Fable if the low-to-max output-token ratio is under about 1.2x with overlapping ranges across tasks; 'weakly applied' if 1.2-2x; 'applied' above 2x, with Opus arms confirming the harness can detect scaling.

- Low-to-max output-token ratio is 6.77x (95% CrI 5.50 to 8.28), P(ratio > 2) = 1.000 (no draw of 12,000 below 2; closed-form cross-check 1.00000). Posterior mass on "ignored" or "weakly applied" is under 1e-4.
- Ranges do not overlap: the highest low run is 7,184 output tokens, the lowest max run 32,620 (25 of 25 low/max pairs). Same for xhigh vs low (lowest xhigh 18,658) and, narrowly, high vs low (lowest high 7,994).
- Harness check: Opus and Sonnet scale medium to xhigh by 3.33x and 3.18x (table below), so the harness detects scaling. The Opus arms the rule asked for (cap10 medium/high) were not run; this check uses the existing default-prompt Opus and Sonnet arms instead (see Dropped scope).
- The rule's "across tasks" clause could not be applied: only task 1 exists. The verdict is "applied on task 1"; the dropped-scope section says why a second task would not change it.

## Fable task 1, per effort level (cap10 prompt, n=5 per level)

| effort | output tokens (mean, range) | thinking tokens (mean) | cost per run (arithmetic mean) | recall /13 (Opus judge) | recall /13 (Sonnet judge) |
|---|---|---|---|---|---|
| low | 6,200 (5,320 to 7,184) | 3,262 | $0.421 | 5.6 | 5.6 |
| medium | 8,521 (7,537 to 10,751) | 5,418 | $0.527 | 5.4 | 5.4 |
| high | 9,827 (7,994 to 11,424) | 6,548 | $0.592 | 5.6 | 5.8 |
| xhigh | 21,810 (18,658 to 25,993) | 17,983 | $1.191 | 6.4 | 6.4 |
| max | 42,261 (32,620 to 50,867) | 37,579 | $2.214 | 6.2 | 6.4 |

Output tokens are summed across turns (every run was one turn). Cost is the CLI's `total_cost_usd`, API-list equivalent, not subscription spend. Cost excluding each level's cache-cold first run: low $0.324, medium $0.445, high $0.497, xhigh $1.121, max $2.012. Recall is the raw mean of items found by two blind LLM judges (Opus 5.5 medium, Sonnet 5 high). Thinking share of output rises from 53% (low) to 89% (max); non-thinking tokens grow only from 2,938 to 4,682, so the scaling is thinking, not longer reviews.

## Credible intervals (output tokens, ratio of geometric means, 95% equal-tailed)

| contrast | median ratio [95% CrI] | P(> 2) | P(1.2 to 2) | P(superiority) |
|---|---|---|---|---|
| max / low | 6.77 [5.50, 8.28] | 1.000 | 0.000 | 1.0000 |
| xhigh / low | 3.51 [2.87, 4.29] | 1.000 | 0.000 | 1.0000 |
| xhigh / medium | 2.56 [2.09, 3.12] | 0.990 | 0.010 | 0.9996 |
| high / low | 1.58 [1.29, 1.95] | 0.014 | 0.982 | 0.964 |

P(superiority) is the posterior-predictive probability that a fresh run at the higher level emits more tokens than a fresh run at the lower one. Steps are monotone with no flat adjacent pair: medium/low 1.37 [1.12, 1.69], max/xhigh 1.93 [1.57, 2.36]. Thinking tokens: max/low 11.50 [8.92, 14.65], xhigh/low 5.52 [4.28, 7.07].

Harness-detection check (default prompt, task 1, n=10 per level, shared sigma):

| model | xhigh / medium [95% CrI] | P(> 2) | lowest xhigh vs highest medium |
|---|---|---|---|
| Opus 5.5 | 3.33 [2.94, 3.76] | 1.000 | 40,628 vs 19,634 |
| Sonnet 5 | 3.18 [2.86, 3.54] | 1.000 | 51,221 vs 20,539 |

Their max runs hit the 128k output cap and are right-censored lower bounds (medium-to-max at least 8.6x Opus, 13.8x Sonnet, by the lower CrI limit); their upper limits are prior-driven and uninformative. Neither model has a low arm, so low-to-max is not estimable for them.

## Does the extra thinking buy recall?

Bayesian recall, primary judge, Fable-only fit (source `BAYES_RESULTS.md` of the #120 run; not re-run): low 5.65, medium 5.48, high 5.65, xhigh 6.31, max 6.15. Contrasts: high minus low +0.00 [-0.66, +0.66]; xhigh minus high +0.66 [+0.02, +1.34], P(> 1 item) 0.20; max minus xhigh -0.16 [-0.88, +0.53]. Under the Sonnet judge xhigh minus high weakens to +0.50 [-0.25, +1.27]. Intervals are 90% and unadjusted for the 16 contrasts inspected, so the xhigh step is probably optimistic.

## Data provenance

- Model `claude-fable-5-1`, Claude Code 2.1.282, run 2026-09-25 with the harness committed at `claude_code_research/artifacts/effort-benchmark/` (`pilot_fable.py`, `common.py`).
- Command per run: `claude -p --model claude-fable-5-1 --effort <level> --output-format json --setting-sources "" --tools "" --strict-mcp-config --disable-slash-commands --max-budget-usd 6`, prompt on stdin, cwd an empty git-initialised directory, env `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` and `CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000`, inherited `CLAUDE_*` variables stripped. For max only, `CLAUDE_CODE_EFFORT_LEVEL=max` was also set on that child process (settings cannot carry max).
- Prompt: the default review prompt plus the `cap10` suffix "List at most 10 findings, most important first, then stop."
- Task 1: review of a 1,203-line synthetic rate-limiting PLAN document with 13 seeded defects, tool-less, single turn. Recorded effort was verified from the session transcript in 25 of 25 runs; all 25 finished with status ok.
- n = 5 per level, 25 Fable runs, $24.72 review cost. The Opus/Sonnet comparison arms come from the #120 sweep (60 default-prompt runs, plus n=1 max runs).
- Tidy table: `claude_code_research/.scratch/rlp121-analysis/runs_tidy.csv`, 89 rows (one per run, all models; columns model, effort, prompt, task, arm, run_id, rep, status, censored, out_tokens, think_tokens, text_chars, cost_usd, wall_s, effort_verified, judge item counts). Generated 2026-10-17 by a read-only script over the run JSONs and judge files in `claude_code_research/.scratch/experiment-effort-20260924/` (both under `.scratch/`, which is git-ignored and ephemeral; the repo also ignores `*.csv`, so the table is not committed) (`runs/`, `runs-fable-pilot/`, `judgments*/`, `audit_tokens.json`) one row per run. Output tokens are summed across turns (audit-corrected for the 60 default runs); `result.usage.output_tokens` alone covers only the last turn. The `censored` column flags the two default-prompt max runs. The scripts (`build_table.py`, `analysis.py`) sit beside it and are likewise not committed; the method below is enough to rebuild them (numpy and scipy only, about 10 seconds).
- Model: `y = log(output_tokens)`, `y ~ Normal(mu[arm], sigma^2)` with a shared sigma per model (the n=1 arms carry no variance information), right-censored likelihood for the two capped max runs. Priors: mu ~ N(10, 2^2), sigma^2 ~ InvGamma(2, 0.1). Gibbs sampler, 4 chains of 3,000 draws after 1,500 warm-up, data augmentation for the censored runs, seed 20261017; max R-hat over mu 1.014 (Fable alone 1.000). Ratio = exp(mu_a - mu_b). Checks: an independent closed-form normal-inverse-gamma posterior gives Fable max/low 6.76 [5.22, 8.75]; per-arm-sigma fits give 6.76 [5.12, 8.95]; log-normal fit checks show no misfit for Fable (Sonnet's within-arm spread varies by 2.3x, the one mild exception, without moving its headline ratio).

## Confounds and limits

- **Single task.** One synthetic, tool-less, single-turn plan review. The intervals describe run-to-run noise on this task, not between-task variation.
- **Model and prompt confounded.** The cap10 prompt was used on Fable only; the Opus and Sonnet arms use the default prompt. Fable effort contrasts are internally clean, but Fable-vs-Opus/Sonnet comparisons mix model and prompt. A single Opus cap10 max run (89,805 tokens) was 6.1x the default-prompt medium median; that is a prompt-confounded point, not a control.
- **Draft-then-rewrite inflation.** Fable at xhigh and max is documented to sometimes draft a long deliverable in its thinking and then write it out again. Tokens at those levels therefore measure thinking spend, not task value. Thinking text is absent from the records, so this was not inspected directly.
- **Cold-cache first runs** inflate cost (about 23.7k to 26.5k cache-creation tokens in run 1 of each level, none afterwards), not tokens. The cost column includes them; the warm figures are above.
- **Right-censoring.** The Opus and Sonnet default-prompt max runs hit the 128k cap (Opus 135,878 tokens with no review text; Sonnet 256,000 over two truncated turns). They are lower bounds.
- **Cost figures.** $2.214 (arithmetic mean of the five max runs) and $2.207 (bootstrap-resample mean in the #120 Bayesian output) describe the same data; neither is an error. The same pattern holds for the other levels (0.421/0.419, 0.527/0.528, 0.592/0.593).
- **Recall** is measured on one answer key by judges that share model families with the reviewers; no precision scoring. Wall times were taken under 2-way parallelism and are not reported here.
- All 25 Fable runs were taken on one day; serving drift between sessions is unmeasured.

## Dropped scope and why

The issue originally planned three tasks, with Opus cap10 medium/high controls (about 105 runs; 25 done). It was re-scoped on 2026-10-17 after the Bayesian re-analysis:

- **Tasks 2 and 3 were never authored** (no prompt, target document or answer key exists), so they were unrun as well as unscored.
- **Value-of-information simulation.** Draw true parameters from the current posterior, simulate extra runs, refit, and count futures that move P(ratio > 2) below 0.95. For extra Fable cap10 low/max runs (1, 3, 5 or 10 per arm): 0 of 1,500 futures at every size. For xhigh/low: 0 to 0.2% of futures. For Opus default xhigh/medium: 0. For the Opus cap10 max/medium control: about 5% of futures (4.5% to 4.6% with 3 to 10 extra medium runs; 2.5% to 3.2% with matched extra medium and max runs), and only through a prompt-by-effort interaction, a tail that comes from the deliberately wide N(0, 0.5^2) prior on the cap10 shift. So the Opus cap10 controls and extra Fable runs cannot change the task-1 verdict.
- **What would still be learned** is cross-task generalisation, not the task-1 ratio. One task cannot identify between-task spread (tau), so the table is assumption-driven: adding task noise N(0, tau^2) to the task-1 low-to-max log-ratio gives the probability that a new task's true ratio exceeds 2 (and falls under 1.2):

| tau (log-scale sd across tasks) | 0.25 | 0.5 | 0.75 | 1.0 | 1.5 |
|---|---|---|---|---|---|
| P(new-task ratio > 2) | 1.000 | 0.992 | 0.944 | 0.891 | 0.789 |
| P(new-task ratio < 1.2) | 0.000 | 0.0004 | 0.011 | 0.041 | 0.125 |

A new task would need about 3.4x less scaling than task 1 to drop under 2x. The plausible route is an easy task where Fable's adaptive thinking stays short at every level; there is no data on how likely that is.
- **One optional cheap check, only if anyone cares:** an easy task (single obvious answer) at low, high and max, n=5 each (15 runs, well under the cost of the original plan). It would test the adaptive-thinking route directly. Nothing in the practical guidance below depends on it.

## Practical guidance

- Pin Fable roles at `high`. Recall is flat from low through high (5.65, 5.48, 5.65 of 13) while tokens rise 1.58x low to high.
- `xhigh` adds about 0.66 recall over `high` [0.02, 1.34] (90% CrI, weakened to +0.50 under the second judge) at about twice the cost ($1.191 vs $0.592, ratio 2.01). Use only where a measured gain justifies it.
- `max` adds no recall over `xhigh` (-0.16 [-0.88, +0.53]) at 1.86x its cost ($2.214 vs $1.191). Avoid.
- A Fable bullet in the dotfiles `model-notes` "Effort evidence" section (token multiples 1.4x, 1.6x, 3.5x, 6.8x versus low for medium, high, xhigh, max; recall as above; one task, cap10, n=5) is an **optional follow-up** and needs its own dotfiles issue (dotfiles#181 is closed). It is not filed and no dotfiles file is changed here.
