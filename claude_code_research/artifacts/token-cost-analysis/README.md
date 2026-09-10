# token-cost-analysis

Unified multi-host Claude Code token-cost report. `token_cost_report.py` is a
single, standalone script: it walks each named host's Claude Code transcript
files, dedupes usage lines by `message.id`, prices tokens by exact model ID
(falling back to tier pricing for models not yet in the pricing table), and
prints a combined per-project cost report across every host in one pass.

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

## Known limitation: dedup-before-window-filter

`message.id` deduplication happens globally across each host's entire
transcript corpus, **before** the `--since`/`--until` window is applied.
This is deliberate -- it matches the corpus-wide ground truth this tool was
validated against -- but it means a message whose first occurrence falls
outside the requested window will **not** be counted even if a duplicate of
it falls inside the window. This can under-count totals for narrow windows
near a boundary. Widen the window if you need an exact boundary-accurate
figure.

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
  cache-field logic lives in one embedded Python source string
  (`_EXTRACTOR_SRC`), executed via `subprocess.run([sys.executable, "-"], ...)`
  locally and `subprocess.run(["ssh", ..., host, "python3", "-"], ...)`
  remotely -- same code path, every host, every run. `--since`/`--until`
  reach it as argv, never string-interpolated into the source.
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

## Verification

To sanity-check a run:

- Compare the reported grand total against a fresh
  `npx ccusage@latest daily --json` for the same window. Some gap is
  expected: a few percent from this tool's dedup-before-window-filter
  behavior (see above), plus a further gap from `ccusage`'s local-date
  daily bucketing versus this tool's UTC-date bucketing. A combined gap in
  roughly the 5-7% range against `ccusage` has been observed and is not on
  its own evidence of a bug.
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

## Known accuracy ceilings (not fixed by this tool)

- **Long-context (`[1m]`) premium pricing** is unrecoverable from
  `message.model` -- a `[1m]`-variant call records as the plain model ID in
  transcripts, so if long-context premium billing applies, this tool has no
  way to detect or price it correctly.
