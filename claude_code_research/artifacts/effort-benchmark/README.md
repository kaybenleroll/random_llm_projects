# Effort Benchmark: does reasoning effort change reviewer recall?

A headless harness that measures whether the `--effort` level (low/medium/high/xhigh/max) of a Claude model changes how many
of 13 deliberately seeded defects it finds in a fixed design document, with blind LLM judging and a Bayesian analysis.
Everything runs through the `claude` CLI in print mode; the analysis stage is pure local Python.

Read "Known limitations" (section 9) before quoting any number from a run.

## 1. Layout

    inputs/target.md            synthetic 13-defect design document (the review target)
    inputs/answer-key.md        answer key: one entry per seeded defect (judge rubric)
    inputs/review_prompt.txt    review instructions with the target inlined (identical bytes for every default-prompt run)
    inputs/judge_prompt_head.txt blind-judge instructions (judge output = JSON, one found/quote entry per key item)
    common.py           arms, judges, isolation flags, `claude` wrapper, retries. Edit ARMS / EXTRA_ARMS / JUDGES / budgets here
    run_arm.py          one review pass:      python3 run_arm.py <arm> <n> [--force] [--prompt-variant cap10]
    judge.py            blind judging:        python3 judge.py <arm> <n> [judge ...] [--force]
    make_schedule.py    seeded shuffle of (arm, n): python3 make_schedule.py --n 10 --seed 20260924 --arms a,b,c --out schedule.json
    orchestrate.py      resumable sweep (review, then both judges): --schedule schedule.json --jobs 2 [--no-judge] [--limit N]
    run_full.sh         builds the schedule and runs orchestrate.py in the foreground
    limits.py           usage-limit classifier/gate; test_limits.py is its offline unit test
    reconstruct.py      rebuilds review text + token accounting from raw events / session transcript for truncated runs
    analyze.py          descriptive tables, bootstrap CIs, inter-judge agreement -> results.md
    pilot_fable.py      one-run-per-arm driver for an extra model family (dry-run by default; see section 8)
    bayes_analysis.py   Bayesian model, contrasts, cost-effectiveness -> BAYES_RESULTS.md
    smoke_check.py      offline PASS/FAIL check of effort application and isolation over completed run records
    probe1.sh probe2.sh probe3_baseline.sh env_clean.sh   optional manual isolation probes (send tiny paid prompts)
    reference/BAYES_RESULTS_original.md   static copy of the original run's Bayesian output, for comparison only
    requirements.txt    pinned analysis dependencies

Working files are created next to the scripts and are git-ignored: `runs/<arm>/<n>.{json,review.md,raw.json}` (failed:
`<n>.failed.json`), `judgments/<arm>/<n>.<judge>.json`, `logs/`, `cwd/`, `STATUS.txt`, `schedule.json`.

## 2. Prerequisites

- Claude Code CLI on PATH as `claude` (original run: 2.1.282), logged in with an account that can use the models below. The harness
  cannot use `--bare` because that mode never reads the OAuth/keychain login.
- Python 3.10+ (harness scripts use only the standard library; original analysis venv used Python 3.14).
- Access to the model ids in `common.py` (`claude-opus-5-5`, `claude-sonnet-5`; `claude-fable-5-1` in `pilot_fable.py`). Change
  the ids there if yours differ; arm names are just labels.
- Budget: per-run costs observed in the original run (list-price `total_cost_usd`): Sonnet medium/high/xhigh about $0.20/$0.33/$0.59,
  Opus medium/high/xhigh about $0.34/$0.46/$1.03, so the six-arm n=10 review sweep is about $30, plus two judge calls per run
  (judge cost was not aggregated). Longest review about 9 minutes. A max-effort pass can cost $2 to $4 and may not finish.
- Ability to spend from a subscription usage limit: `limits.py` sleeps through a 5-hour window and halts on a weekly limit.
  Weekly-limit consumption is not recorded by the harness (only per-run dollars), so plan quota separately.

## 3. Setup

    cd effort-benchmark
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt      # analysis only; the harness needs nothing beyond the standard library
    python3 test_limits.py                          # offline; expect "RESULT: 0 failures"

## 4. How each call is made (what the smoke check verifies)

Every review and judge call is one fresh process:

    claude -p --model <id> --effort <level> --output-format json --setting-sources "" --tools "" \
           --strict-mcp-config --disable-slash-commands --max-budget-usd <cap>      (prompt on stdin)

with `cwd = ./cwd` (created on first use, its own `git init`, no CLAUDE.md) and a child environment that:
strips inherited `CLAUDE*` variables (`CLAUDE_EFFORT`, `CLAUDE_CODE_EFFORT_LEVEL`, session and entrypoint vars, see `STRIP_ENV`
in `common.py`); sets `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` (without it a project memory index leaked into context in a probe);
sets `CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000`.

- Effort application: the requested level is passed with `--effort`; sessions are deliberately persisted, and after each call
  `common.transcript_efforts` reads the `effort` field on every assistant line of the session transcript under
  `~/.claude/projects/*/<session_id>.jsonl`. `effort_verified` is true only if that set of values equals `{requested effort}`.
  This is independent evidence from the CLI's own log, not from the flag we passed.
- Isolation from ambient config/memory: `--setting-sources ""` drops user/project/local settings (hooks, default effort,
  permissions); `--tools ""` removes all tools (so no file access and no tool hooks); `--strict-mcp-config` with no config means
  no MCP; `--disable-slash-commands` removes skills/commands; auto-memory is disabled by the env var; the empty git-rooted `cwd`
  anchors any CLAUDE.md/memory discovery inside itself. The init event recorded in each run (`init.tools/skills/slash_commands/
  mcp_servers/memory_paths/agents`) shows what was actually loaded.
- Isolation between runs: no run resumes or continues another; each has its own session id and process. The judge sees only the
  review text and the answer key (no arm, model or effort). Schedules are seeded, interleaved by replicate so time-of-day and
  rate-limit drift are not confounded with arm.

## 5. Smoke check (do this before any full run; about $1)

    python3 make_schedule.py --n 1 --arms sonnet-medium,sonnet-xhigh --out schedule-smoke.json
    python3 orchestrate.py --schedule schedule-smoke.json --jobs 1 --no-judge
    python3 smoke_check.py --runs runs --min-runs 2

Expected: every line `PASS`, final `RESULT: ALL PASS`, exit code 0. Thresholds (all must hold, per run):

| criterion | pass |
|---|---|
| effort applied | `effort_verified` true and transcript effort values recomputed by `smoke_check.py` equal exactly `{requested}` |
| no ambient config | `init.tools`, `skills`, `slash_commands`, `mcp_servers` all empty; `memory_paths` empty/null; agents only the built-ins |
| right model | `model_reported` equals the requested model id |
| clean completion | exit code 0, `ok` true |
| run isolation | all session ids distinct; all transcripts in one directory whose name ends `-cwd` |

Any FAIL means stop: do not run the sweep. In particular a `effort_verified` failure means the level you think you are testing is
not the level being applied (check for a `CLAUDE_CODE_EFFORT_LEVEL` override or a CLI version that does not log `effort`).
Optional manual probes: `probe3_baseline.sh` runs one non-isolated call so you can see the hooks/skills/agents the flags remove
(it writes to `../logs/`; create that directory first); `probe2.sh <model> <effort>` prints the raw init/effort fields of one call.

Validation of the checker itself: it was run offline against all completed run records of the original experiment
(376 checks, all PASS).

## 6. Full run

    python3 make_schedule.py --n 10 --seed 20260924 --arms opus-medium,opus-high,opus-xhigh,sonnet-medium,sonnet-high,sonnet-xhigh --out schedule.json
    setsid nohup ./run_full.sh 10 > logs/overnight.log 2>&1 &     # 6 arms x n=10, 2 parallel; create logs/ first
    while kill -0 "$(cat logs/orch.pid)" 2>/dev/null; do sleep 30; done; tail -n 20 logs/harness.log; tail -n 1 STATUS.txt

`STATUS.txt` last line is one of `FINAL: DONE | HALTED_WEEKLY_LIMIT | HALTED_CONSECUTIVE_FAILURES | STOPPED | CRASHED`. Re-run the same
command to resume (finished steps are skipped). `touch STOP` stops gracefully. Guards: 40 minute wall-clock timeout per review
attempt (process group killed, one retry), at most 2 retries for transient errors, 6 consecutive failures halt, a usage limit
resetting within 6 hours is slept through.
Pass criteria for the run: `FINAL: DONE`; at least 95% of scheduled reviews `status` ok (a `truncated` or `failed` review must be
reported, never silently pooled); `python3 smoke_check.py --runs runs --min-runs 60` all PASS.

Max-effort arms are not in the default sweep. `common.EXTRA_ARMS` defines `opus-5-5-max-cap10` and `sonnet-5-max-cap10` (effort max,
128000 output tokens, `--prompt-variant cap10`, which appends "List at most 10 findings, most important first, then stop.") and
`opus-5-max`. Run one with `python3 run_arm.py <arm> 1`; budget precedence is flag, then env `EFFORT_BUDGET_USD_REVIEW`, then arm
spec, then `common.BUDGET_USD`. At max effort a pass can spend its whole token turn thinking; runs that end that way are stored with
`status: truncated` (text recovered from the transcript by `reconstruct.py`) and must never be pooled with complete runs.

## 7. Judging and descriptive analysis

The orchestrator judges every completed review with two judges (`j-opus-medium`, `j-sonnet-high`). To judge by hand:
`python3 judge.py <arm> <n> [judge ...]`. Recall per run is recomputed from the per-item `found` flags (13 items); a verdict that
does not list exactly items 1..13 with boolean `found` is rejected and retried, and self-reported counts are ignored.

    python3 analyze.py --schedule schedule.json --out results.md

Reports per-arm recall (mean of both judges; a run with no completed review counts as 0 in the intent-to-treat columns), bootstrap
intervals, per-judge recall, agreement and Cohen's kappa. Sanity threshold (pre-register it): the presumed-strongest arm's mean recall
should be at least about 30% of the items (4 of 13); below that, suspect the pipeline, not the models. The original run's arms were at
6.5 to 7.7 of 13.

## 8. Bayesian analysis

    .venv/bin/python bayes_analysis.py            # add --refit to discard the fit cache in ./bayes_cache and resample
    # writes ./BAYES_RESULTS.md; no model or network calls

Model: Bernoulli-logit per (run, item): `logit p = mu + arm + item + run`, hierarchical item and run terms, independent N(0,1.5) arm
priors, NUTS 4 chains x 1000 draws (seed 20260925), separately for each judge, plus a prompt-indicator fit and an arm-by-item
interaction fit. Outputs: per-arm expected recall of 13 with 90% credible intervals, predictive counts, recall per dollar, decision
contrasts with P(diff>0), P(diff>1 item) and P(|diff|<0.5), cost-effectiveness of each effort step, diagnostics.
Diagnostic pass thresholds (recommended): R-hat <= 1.01 everywhere, minimum ESS >= 400, 0 divergences, posterior predictive checks
inside their 90% intervals. The original run reported R-hat max 1.010, min ESS 607, 0 divergences, 25/25 checks inside.

Reproduction caveats: the script is written for the original 14-arm data layout. It reads `judgments/<arm>/`, `runs/<arm>/` for the
default-prompt and max arms, and `judgments-fable-pilot/`, `runs-fable-pilot/` for five extra-family arms (produced with
`pilot_fable.py`; it defaults to `--dry-run`, and a real run needs `PILOT_FABLE_STAGE2=1 python3 pilot_fable.py --execute <arm>`).
Judge those pilot reviews with `python3 judge.py <arm> 1 --pilot-dir runs-fable-pilot`. If you replicate only part of the design, edit the
`ARMS` table and the arm-specific fits/contrasts in `bayes_analysis.py` to match. The "plain English" block at the top of the output
and the reference means in section 1 are static text/values from the original data; on new data they will differ and must be
rewritten, and section 1's "mismatch" flags then compare against the original values and are not errors.
`reference/BAYES_RESULTS_original.md` is the original output for comparison.

Reading the output: the headline quantity is expected recall of 13 per arm and the difference between arms in items. Ignore point
estimates whose 90% interval comfortably includes 0. `P(|diff|<0.5)` is the probability the arms are practically equivalent
(within half an item). Cost-effectiveness ratios are unstable when the cost difference is small or the recall gain straddles zero;
read the P(gain>0) and P(ratio<0) columns next to them. Original findings, for orientation only: no within-model effort step showed a
credible gain of 2+ items of 13; the largest supported steps were about +0.9 item (Opus high to xhigh, Sonnet medium to high); Sonnet
xhigh was not better than high; Opus high was not better than medium.

## 9. Known limitations (state these with any result)

- The decision rule was set post hoc. The original plan called for it to be committed before the data; that requirement was not met.
  Treat every contrast as exploratory.
- Six arms (Opus and Sonnet at medium, high, xhigh) have n=10. The max-effort arms were run once each (n=1) with a different prompt
  (cap10) and are not comparable to the n=10 arms; they are not analysed inferentially. One extra default-prompt Sonnet max run (n=1)
  ended by a budget stop and was recovered from its transcript; treat it as an anecdote. The default-prompt Opus max run failed and
  was never judged. An extra model family (five effort levels, n=5, cap10 prompt) is confounded with prompt and cannot be compared
  with the others.
- Bayesian intervals are unadjusted across 16 contrasts (the primary-judge decision-contrast table; the same 16 are repeated for the
  second judge, plus 7 under the interaction fit and 9 cost steps). Credible intervals are therefore optimistic for the
  largest contrasts and the results are hypothesis-generating, not confirmatory. Non-monotone patterns (Opus high below medium,
  Sonnet xhigh below high) mean either a real plateau or arm-level noise larger than the model captures; the data cannot tell which.
- Weekly-limit (subscription quota) cost was not recorded; only per-run dollar cost (`total_cost_usd`, list-price basis) is.
  Per-run cost is not directly comparable across model families unless the same price basis applies.
- One synthetic target document with 13 seeded defects and one prompt: results describe this document, not review quality in general.
- Two LLM judges (Opus medium, Sonnet high), each one pass per review; observed item-level agreement was 96.8% (kappa 0.94), but judge
  noise is not separated from reviewer noise. Judges are from the same model families as the reviewers.
- The effort check depends on the CLI writing an `effort` field to its transcripts (verified for the CLI version above); other
  versions may not, in which case `effort_verified` is false for every run and the smoke check fails.
- `usage.output_tokens` in a result is one turn only; the all-turn total is in each record's `recon.total_output_tokens`.
- Output token cap: the CLI clamps a turn to its model limit regardless of `CLAUDE_CODE_MAX_OUTPUT_TOKENS`; at max effort a full
  turn can be spent thinking with no answer text.
