# token-cost-analysis

Unified multi-host Claude Code token-cost report. `token_cost_report.py`
walks each named host's Claude Code transcript files, dedupes usage lines by
`message.id`, prices tokens by exact model ID (falling back to tier pricing
for models not yet in the pricing table), and prints a combined per-project
cost report across every host in one pass. It requires `extractor.py` as a
sibling file (it reads that file's source at import time and ships it
verbatim to each host) -- copy both files together; `token_cost_report.py`
raises `SystemExit` at import if `extractor.py` is missing.

## Usage

```
token_cost_report.py --hosts local,s3rbase[,newhost...] \
    [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--out PATH] [--allow-partial]
```

Example:

```
python3 token_cost_report.py --hosts local,s3rbase --since 2026-08-12 --until 2026-09-10
```

- `--hosts` (required): comma-separated SSH aliases. `local` means "run the
  extractor directly on this machine, no SSH." Remote hosts must already
  exist in `~/.ssh/config`.
- `--since` / `--until`: UTC dates, inclusive. Default: full available
  history.
- `--out`: output path for the combined JSON report. Default:
  `.scratch/token_cost_report_<UTC-timestamp>.json`, resolved relative to the
  script's own directory (two levels up, i.e. the containing project root).
  Per-host raw extraction dumps (pre-merge, pre-pricing) are always written
  separately to `.scratch/token_cost_raw_<host>_<UTC-timestamp>.json` as
  debugging/audit artifacts.
- `--allow-partial`: if any host fails (SSH failure, non-zero exit, timeout,
  or contaminated/unparseable stdout), the tool aborts without writing a
  report by default. Pass this flag to write a report anyway; it is marked
  `"partial": true` with the failed hosts listed, and the stdout summary's
  first line states the omission before any dollar figures.

## Dedup policy

`message.id` deduplication keeps the occurrence with the **max
`output_tokens`** per id ("keep-max"), replacing the tool's original
first-occurrence ("keep-first") policy (issue #101). Streamed generation
(chiefly in subagent transcripts) writes an early line carrying a stub
`output_tokens` count and a later line carrying the settled count;
keep-first was picking the stub. Measured on this machine's full corpus
(291,064 usage-bearing lines, 140,837 distinct `message.id`s):

| Policy | Total `output_tokens` | Ratio |
|---|---|---|
| keep-first (old) | 64,442,942 | 1.000 |
| keep-max (current) | 101,474,466 | **1.575** |

By transcript type: subagent transcripts **3.462x**; main-session
transcripts **1.000x** (zero divergence there).

**The dollar effect is much smaller than the token ratio.** `output_tokens`
is only one of five priced fields, and cache-read dominates this corpus's
cost -- output tokens measured at ~7.1% of priced cost. The 1.575x
correction to `output_tokens` alone moves the grand total by **roughly
+4%**, not +57.5%. Do not scale a report generated before this fix by the
1.575x token ratio to estimate its true dollar total -- that overstates the
dollar impact by roughly an order of magnitude. If you need an accurate
total for a historical window, regenerate the report; there is no linear
rescaling of an old JSON report that recovers the correct dollar figure.

**ccusage reconciliation:** the tool's keep-max total was compared against
`npx ccusage@latest daily --json` for a real-activity window and tracked it
closely (within the same few-percent range this tool's UTC-vs-local-date
bucketing already produces) -- `ccusage` does not appear to share the old
keep-first bug, so the "5-7% agreement" this README documents below is
independent validation of keep-max, not of keep-first.

Because the winner of a duplicate group is not always the first
occurrence, window membership and day-bucket assignment now follow the
**winning** occurrence's timestamp, not the first occurrence's:

- A message whose first occurrence fell outside `--since`/`--until` but
  whose winner falls inside it is now counted (`msgids_boundary_rescued`)
  -- fixing the old caveat, where such messages were silently lost.
- A message whose first occurrence fell inside the window but whose winner
  falls outside it is now dropped entirely (`msgids_boundary_dropped`) --
  a new, narrower edge case replacing the old one, not a strict
  improvement in every case. A narrow `--until` near active streaming
  activity can lose messages it previously at least partially counted.

Both counters are reported per host in `self_report_per_host` and in the
`print_summary` output; both are `0` on a full-history run and only
nonzero near a window boundary. Widen the window if you need an exact
boundary-accurate figure.

## Cross-host duplicate detection

Each host's own extraction already dedupes `message.id` within that host's
corpus. On top of that, the combine step dedupes `message.id` **globally
across every requested host**: if the same project directory is ever
replicated onto two hosts (sync, backup), the same `message.id` shows up in
more than one host's output, and per-host dedup alone cannot see that. The
combine step catches it and counts each such message once.

- Hosts are compared in sorted-name order: the alphabetically-first host to
  report a given `message.id` keeps its tokens; every later host's copy of
  that message is treated as a cross-host duplicate and subtracted from that
  host's bucket totals before pricing. This mirrors the existing
  dedup-before-window-filter pattern -- it's a second dedup pass, applied at
  combine time, on the same set of already-in-window lines each host fed
  into its own buckets.
- The stdout summary gets a `=== Cross-host duplicate detection ===` section
  stating how many duplicate messages were found, an estimated $ value for
  the double-counted tokens excluded, and a breakdown of which host kept
  each duplicate versus which host(s) it was dropped from. It prints "none
  found" when there's nothing to report (including the single-host case).
- The JSON report gets a top-level `cross_host_dedup` key: `duplicate_message_count`,
  `dropped_usd`, `by_host_pair` (kept/dropped host counts), and a capped
  `events` list (each with the message id, kept/dropped host, and which
  project/day/model bucket it affected) for auditing exactly what was
  dropped -- `events_truncated` is set if the list exceeds the cap.
- This only catches duplicates with a `message.id`; the existing
  `lines_missing_message_id` guardrail already flags lines without one, and
  those remain undeduped (per-host and cross-host) as before.

## Design notes

- **Identical extraction on every host**: the JSONL-walking / dedup /
  cache-field logic lives in `extractor.py`, whose source is read at
  runtime (`Path(__file__).with_name("extractor.py").read_text()`) and
  piped verbatim to `subprocess.run([sys.executable, "-"], ...)` locally
  and `subprocess.run(["ssh", ..., host, "python3", "-"], ...)` remotely --
  same code path, every host, every run. `--since`/`--until` reach it as
  argv, never string-interpolated into the source. `extractor.py` is
  stdlib-only and must never import a sibling module -- see its own
  docstring.
- **Pricing is by exact model ID** (`MODEL_PRICING`), normalized by stripping
  a trailing `-YYYYMMDD` date suffix, falling back to tier-substring pricing
  (`TIER_FALLBACK`) only for model IDs with no exact-table entry -- printed
  as a `WARNING` since the fallback path is known to mis-price older
  generations. Every distinct model ID seen is reported with its resolved
  pricing path, so a table gap is visible rather than silently absorbed.
- **Day-granular extraction** (`(project, iso_date, exact_model_id)`), not
  week-granular, so arbitrary `--since`/`--until` boundaries are honored
  exactly; the parent rolls day buckets up into weekly series for display.
- **Normalized monthly rate**: `total_usd * 30 / max(observed_span_days, 7)`,
  where `observed_span_days` is the project's first-to-last-seen span
  *within the requested window* (not full history). The 7-day floor avoids
  a short session reading as an inflated monthly run-rate; every normalized
  figure is shown next to its `observed_span_days` so a reader can judge how
  much extrapolation is involved.
- **Host-failure policy is abort-by-default** (see `--allow-partial` above)
  -- a tool whose purpose is a trustworthy cross-machine total must not be
  able to produce a partial total that looks complete.

## Tests

Run `python3 -m unittest -v` from this directory (33 tests as of issue #101:
keep-max dedup selection, no-`message.id` handling, cache-shape/usage-field
preservation, window/boundary attribution, counter accounting, and an
extractor self-containment check). Fixtures live on disk under
`tests/fixtures/projects/<name>/*.jsonl`, one project directory per test
scenario so `run_extract(..., project=<name>)` can isolate a fixture from
every other fixture sharing the same tree. `tests/fixtures/dup_msgid_measurement.json`
is a committed, re-runnable snapshot from `tools/measure_dup_msgids.py`
(the Step 0 corpus scan behind the token/dollar figures in "Dedup policy"
above) -- not currently wired into the unit test run as a real-corpus
invariant class, but kept as the reproducible source of those numbers.

## Verification

To sanity-check a run:

- Compare the reported grand total against a fresh
  `npx ccusage@latest daily --json` for the same window. Some gap is
  expected: a small amount from the boundary edge cases in "Dedup policy"
  above (near-zero on a full-history run), plus a further gap from
  `ccusage`'s local-date daily bucketing versus this tool's UTC-date
  bucketing. A combined gap in roughly the 5-7% range against `ccusage` has
  been observed and is not on its own evidence of a bug -- see "Dedup
  policy" above for confirmation that this agreement reflects the current
  keep-max policy, not the old keep-first one.
- For a project present on more than one host, its combined row's
  `total_usd` must equal the sum of its `per_host_usd` entries, and each of
  those must match that host's standalone total for the project exactly --
  no double-counting, no silent collapse.
- Each host's `self_report_per_host[<host>].dedup_ratio` should be
  consistent across repeated runs of the same window on an inactive
  (non-growing) corpus; a `dedup_ratio` of exactly 0% on a host with a
  nonzero `window_usage_lines_with_msgid` count usually indicates
  `message.id` is missing or differently shaped in that host's JSONL.
- If you deliberately replicate a project directory across two hosts to
  test cross-host dedup, `cross_host_dedup.duplicate_message_count` should
  equal the number of shared messages, and the affected host's per-project
  `total_usd` should drop by exactly that duplicate's priced token value
  relative to a run against that host alone.

## Related tools

`../session-analysis/session_analysis.py` covers a different, complementary
axis: single-host **session**-granular analysis (turn counts, a
real-work/automated/subagent classification, oversized-session flagging)
rather than this tool's multi-host `(project, day, model)` `$`-cost
aggregation. It carries no pricing table of its own by design — its
`session_model_tokens.csv` output is a long-format `(session_id, model)`
table meant to be joined against this tool's `MODEL_PRICING`/
`resolve_pricing` for a `$`-costed session-level view; see that tool's
README for the join recipe.

## Known accuracy ceilings (not fixed by this tool)

- **Long-context (`[1m]`) premium pricing** is unrecoverable from
  `message.model` -- a `[1m]`-variant call records as the plain model ID in
  transcripts, so if long-context premium billing applies, this tool has no
  way to detect or price it correctly. Investigated for issue #100; no fix
  was implemented because no reliable signal exists. Findings:
  - Every field on a transcript's `message` object was enumerated across
    ~846K lines / ~289K usage-bearing lines from this machine's full
    `~/.claude/projects` corpus: `role`, `content`, `model`, `id`, `type`,
    `stop_reason`, `stop_sequence`, `stop_details`, `usage`, `diagnostics`,
    `context_management`, `container`. Within `usage`: `input_tokens`,
    `cache_creation_input_tokens`, `cache_read_input_tokens`,
    `output_tokens`, `service_tier`, `cache_creation`, `inference_geo`,
    `server_tool_use`, `iterations`, `speed`, `output_tokens_details`. None
    of these carry a long-context/`[1m]` indicator.
  - `usage.service_tier` was the closest candidate (a tier field genuinely
    exists), but every usage line in the local corpus reports `"standard"`
    (the remaining lines have it `null`/absent) -- including lines where
    `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`
    exceeds 200,000 (40,114 such lines observed, up to ~640K combined
    tokens on `claude-sonnet-5`). `service_tier` does not vary with context
    size and carries no `"long_context"`/`"1m"` value.
  - No other field (`stop_details`, `diagnostics`, `context_management`,
    `container`, or any top-level transcript-line key) carries request
    beta-header or billing-tier metadata either -- transcripts record only
    the API *response*, and long-context pricing (historically: >200K input
    tokens on a model requested with the `[1m]` beta) is a property of the
    *request*, which Claude Code's transcript format does not persist.
  - Per Anthropic's current pricing (checked because this table's premise
    was worth re-confirming, not just trusting the issue text): the
    200K-token premium tier only ever applied to older models (Sonnet 4,
    Sonnet 4.5) under an opt-in long-context beta. Every model in
    `MODEL_PRICING`/`TIER_FALLBACK` above (`sonnet-5`, `sonnet-4-6`,
    `opus-5`, `opus-4-8`, `haiku-4-5`, `fable-5`, `fable-5-1`) is
    current-generation and bills its full 1M-token context window at
    standard rates with no surcharge -- and no such surcharge tier exists
    for these models to mis-detect in the first place. The local corpus's
    distinct model IDs (`claude-sonnet-5`, `claude-opus-5`,
    `claude-haiku-4-5-20251001`, `claude-opus-4-8`, `claude-fable-5`,
    `claude-fable-5-1`, `claude-sonnet-4-6`) confirm no legacy tiered model
    is even present in this tool's usual data. If a legacy tiered model
    (e.g. `claude-sonnet-4-5`) ever appears, it would already fall through
    to `TIER_FALLBACK`'s flat `sonnet` rate -- which is a pre-existing,
    separately-flagged mis-pricing of older generations (see the
    `tier_fallback` `WARNING` in Design notes), not something a long-context
    detector could fix without a request-side signal the transcript never
    records.
