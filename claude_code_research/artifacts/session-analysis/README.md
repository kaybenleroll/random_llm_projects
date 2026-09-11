# session-analysis

`session_analysis.py` walks a Claude Code transcript tree (`~/.claude/projects`
by default) and emits one row per transcript **file** at *session*
granularity: turn counts, deduped token totals, a real-work / automated /
subagent / unclassified classification, and threshold-based flagging for
oversized sessions. It answers "where is the token spend, which sessions are
oversized, how much of this is automation" as a single script invocation
instead of a bespoke investigation.

It does **not** do what the sibling `../token-cost-analysis/token_cost_report.py`
does: that tool aggregates `(project, day, model)` for multi-host `$`-cost
reporting. This tool is single-host/local-only, session-granular, and
deliberately carries no pricing table (see "Joining against `$`" below) — the
two are complementary, not overlapping.

## Usage

```
python3 session_analysis.py [--root PATH] [--project SUBSTR] \
    [--since YYYY-MM-DD] [--until YYYY-MM-DD] \
    [--max-turns N] [--max-cache-creation N] \
    [--out-dir PATH] [--no-parquet]
```

Examples:

```
# Full local corpus, defaults everywhere
python3 session_analysis.py

# One project, oversized-session flagging tightened
python3 session_analysis.py --project my-repo --max-turns 100

# A specific date window
python3 session_analysis.py --since 2026-08-01 --until 2026-08-31
```

- `--root` (default `~/.claude/projects`): the transcript tree to scan.
- `--project SUBSTR`: only rows whose project directory name contains this
  substring.
- `--since` / `--until` (`YYYY-MM-DD`, inclusive, UTC): see "Date-filter
  semantics" below — this is a narrower filter than it may look.
- `--max-turns` (default `175`) / `--max-cache-creation` (default
  `1525000`): flagging thresholds — see "Thresholds" below.
- `--out-dir` (default: `claude_code_research/.scratch/`, resolved relative
  to this script's own location): where `sessions.csv`,
  `session_model_tokens.csv`, `session_summary.json`, and (if pyarrow is
  available) the two `.parquet` files are written.
- `--no-parquet`: skip Parquet output even when pyarrow is importable.

Exit code `2` on a usage error (bad `--root`, `--since` after `--until`, a
negative threshold). Exit code `0` otherwise — including a run that matches
zero rows. **Never** non-zero for malformed transcript lines or unreadable
files; those are counted in guardrail counters (see the stdout/JSON summary)
and reported, not fatal.

## What counts as a "session"

Two file kinds, one row each:

- **Top-level session**: `<root>/<project>/<session-uuid>.jsonl`.
- **Subagent transcript**: any `agent-<hex>.jsonl` found beneath a
  `<parent-uuid>/subagents/` path segment, **at any depth below it** — not
  only directly under it. The Workflow tool nests these one level deeper, at
  `<parent-uuid>/subagents/workflows/wf_<id>/agent-<hex>.jsonl`; on this
  tool's own development corpus that nested layout accounted for roughly
  10% of all subagent transcripts (683 of ~6,730). Detection therefore
  anchors on **the path segment immediately preceding the first
  `subagents/` component**, not a fixed depth — that segment is the parent
  session UUID, confirmed independently by every line's own `sessionId`
  matching it at both the flat and nested depths. If no `subagents/`
  segment appears anywhere in the path (an older layout, or an
  `agent-*.jsonl` basename sitting directly in a project directory), the
  file is treated as top-level with a null parent, and counted in the
  `subagent_path_unmatched` guardrail. This path never errors.

Subagent rows are **never folded into their parent's totals** —
`parent_session_id` lets downstream analysis do that folding deliberately,
per-row. `session_id` is always the file's own stem; `agent-<hex>` stems are
unique across the whole corpus (using the parent UUID as the id would
collide across sibling subagents of the same parent).

**Excluded, not ingested as sessions**: any `.jsonl` file whose basename
matches a known non-transcript control/log basename —
`journal.jsonl` (workflow event log: lines carry `{type, key, agentId}`,
never `message`/`sessionId`/`timestamp`) and `nudge-events.jsonl`. Both
would otherwise collide as `session_id="journal"` /
`session_id="nudge-events"` across many unrelated workflow runs. This is
maintained as an explicit basename denylist
(`NON_TRANSCRIPT_BASENAMES = {"journal.jsonl", "nudge-events.jsonl"}`)
checked at discovery, counted in the `files_excluded_non_transcript`
guardrail. **Known limitation**: this is a denylist, not a schema sniff — a
future new non-transcript basename not yet on the list would still be
silently ingested as a session row. Extend the set if a new control-file
basename is ever identified.

## Classification

`classification` ∈ `real_work | automated | subagent | unclassified`.
`classify_session()` is a pure function, strict decision order:

1. **Path-based subagent, unconditional.** A file identified as a subagent
   transcript by its path is always `subagent` (basis `path`) — this never
   consults `promptSource`, even if one happens to be present.
2. **No qualifying user line.** If no non-meta `type:"user"` line survives
   the `isSidechain` exclusion (top-level files only — see "Turn counting"
   below), the row is `unclassified` (basis `no_user_lines`). This single
   branch covers both "no user lines at all" and "user lines exist but
   every one was excluded as sidechain/meta" — including a top-level file
   whose subagent-path match failed and landed here rather than falling
   through to the entrypoint fallback below.
3. **Recognized `promptSource`.** The first qualifying line's
   `promptSource`: `typed`/`queued` → `real_work`; `sdk`/`system` →
   `automated` (basis `prompt_source`).
4. **Unrecognized `promptSource`.** Present but not one of the above →
   `unclassified` (basis `unknown_prompt_source`), named in the summary's
   `unknown_prompt_source_values`. Does **not** fall through to the
   entrypoint fallback below — an unrecognized signal is a "flag this",
   never a "guess and move on".
5. **`promptSource` absent → entrypoint fallback.** `entrypoint == "cli"` →
   `real_work`; `entrypoint == "sdk-cli"` → `automated` (basis
   `entrypoint_fallback`). This branch is load-bearing: sessions that open
   with a slash command (e.g. `/reflect`, `/clear`) carry no `promptSource`
   at all — without this fallback they'd be silently dropped from
   `real_work`, on the order of a few percent of it on this tool's
   development corpus.
6. **No usable signal at all** → `unclassified` (basis `no_signal`).

`classification_basis` is a required output column (not just an internal
detail) precisely so an `unclassified` row's cause is visible downstream —
e.g. distinguishing a genuinely-empty transcript from one with a
`promptSource` value the classifier doesn't yet recognize.

## Turn counting: `api_turns` vs `user_prompts`

Two columns, both required, because they answer different questions and can
differ by roughly 4x on real-work sessions:

- **`api_turns`** — every non-meta `type:"user"` line, **including
  tool-result lines** (a proxy for API round-trips; this is the metric the
  `--max-turns` threshold is calibrated against).
- **`user_prompts`** — the subset of those that are *not* tool-result
  lines, i.e. genuine human/automation-originated prompts.

**The `isSidechain` exclusion applies to both columns, but only on
top-level files.** Subagent transcripts have every user line marked
`isSidechain:true` by construction; applying the top-level exclusion rule to
them would zero out `api_turns` on every subagent row. So: top-level files
drop `isSidechain:true` lines before counting either column; subagent files
count every qualifying user line regardless of `isSidechain`.

`user_prompts <= api_turns` holds on **every** row, structurally —
`user_prompts` counts a subset of the lines `api_turns` counts (those that
aren't tool results), so it can never exceed it. It is *not* generally true
that `user_prompts < api_turns` strictly — an automated or subagent session
where every turn happens to be a genuine prompt with no tool result has
`api_turns == user_prompts`.

## Token accounting

**Dedupe by `message.id`, scoped per file, keeping the LAST occurrence.**
Assistant usage is emitted once per streamed content block, so the same
`message.id` repeats across many lines in most files; summing every line
naively over-counts real-work sessions by roughly 2.3x. That over-count is
entirely about deduping *at all* — it holds regardless of which occurrence
is kept.

**Which occurrence to keep matters differently depending on the file kind:**

- **Top-level (real-work/automated) sessions**: repeated occurrences of the
  same `message.id` are byte-identical in practice — keeping the last is an
  arbitrary-but-deterministic tie-break, not a correction. First-vs-last is
  a no-op here.
- **Subagent transcripts**: repeats genuinely diverge — `output_tokens`
  grows monotonically across streamed occurrences of the same id. On this
  tool's development corpus, first-occurrence vs last-occurrence summed
  `output_tokens` differed by roughly 3.3x on subagent-heavy data. **This is
  where "keep the last occurrence" is the real correction, not in top-level
  rows.** Implementation is a plain `dict` keyed on `message.id`: each
  assignment overwrites, so the final value is the last-seen occurrence.

Other rules:

- Columns: `input_tokens`, `cache_creation_5m`, `cache_creation_1h`,
  `cache_creation_total` (= `cache_creation_5m + cache_creation_1h`),
  `cache_read_tokens`, `output_tokens`.
- Cache-field handling mirrors the sibling tool: a nested
  `usage.cache_creation.{ephemeral_5m_input_tokens,ephemeral_1h_input_tokens}`
  is preferred when present and non-all-zero; the flat
  `cache_creation_input_tokens` field is used only when the nested block is
  absent or all-zero, and is attributed entirely to the 1h bucket.
  Unrecognized nested TTL keys are summed into the 1h bucket rather than
  dropped, and are never silently ignored.
- `type:"cost-state"` lines are ignored entirely — absent from many large
  sessions, not a reliable running total.
- Usage lines with no `message.id` cannot be deduped: they're still
  included in totals (each counted individually, under a synthetic
  per-line key), and counted separately in the
  `usage_lines_missing_message_id` guardrail.
- **No model-tier filter.** Unlike the sibling tool (which must drop
  unrecognized tiers because it has to price them), every model ID seen is
  kept and reported.
- **Cross-file `message.id` reuse** (from session fork/resume — measured at
  roughly 0.1% of distinct ids on this tool's development corpus) is
  **counted and reported** via the `cross_file_duplicate_ids` guardrail,
  **never subtracted** — deliberately unlike the sibling tool's cross-host
  dedup pass. If this guardrail ever exceeds roughly 0.5% of distinct ids,
  treat the `<=0.1%` figure above as stale and re-measure.

## Classification/turn-counting/dedup edge case: subagent files and
`isSidechain`

Worth stating explicitly since it's easy to get backwards: subagent
transcripts have every user line sidechain-flagged **and** never carry
`promptSource`. The `isSidechain` exclusion (Turn counting) does **not**
apply to them, but the path-based classification rule (Classification, step
1) fires unconditionally and never even looks at `promptSource` or
sidechain status. Two independent rules, easy to conflate, each scoped
correctly on its own.

## Thresholds

`flagged = api_turns > --max-turns OR cache_creation_total >
--max-cache-creation`; `flag_reasons` names which fired (`;`-joined,
sorted, e.g. `api_turns;cache_creation_total`).

Defaults: **175** (`api_turns`) and **1,525,000** (`cache_creation_total`).
These are the p95 of the `real_work` population on this tool's own
development-machine corpus scan (a ~10,750-file top-level-only scan,
`n≈495` real-work sessions, 2026-09-10) — **not** a universal constant.
Re-derive them for a materially different corpus (see "Verification"
below): the corpus-regression test suite fails loudly with a
"re-derive defaults and update README" message if the live corpus's p95
drifts more than 20% from these defaults.

p90 was considered and rejected as a default: it sits inside the ordinary
50-150-turn band that most real-work sessions occupy, and would flag
routine sessions as noise; p99 was considered too conservative to serve as
an early warning.

Thresholds are applied to **every** row — `real_work`, `automated`, and
`subagent` alike, not just `real_work`. A runaway automated session (an
automation loop gone wrong) is exactly the kind of anomaly this tool exists
to surface, and normal, short automated sessions cannot false-positive
against these defaults.

## Output

### `sessions.csv` (29 columns)

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `session_id` | string | no | File stem. Unique per file. |
| `parent_session_id` | string | **yes** | Set only on subagent rows (or a rare edge case where a `subagents/` segment is the very first path component). Null on every top-level row. |
| `agent_id` | string | **yes** | `session_id` when the row is a subagent transcript, else null. (No other definition of this column appears anywhere in the tool's design beyond its presence in the column list; this is the only interpretation consistent with the rest of the schema — see "Design notes" below.) |
| `project` | string | no | First path segment under `--root`, or `(root)`. |
| `cwd` | string | yes | From the first line that carries one. Null if none did. |
| `git_branch` | string | yes | Same pattern as `cwd`. |
| `cc_version` | string | yes | Same pattern as `cwd`. |
| `classification` | string | no | `real_work \| automated \| subagent \| unclassified`. |
| `classification_basis` | string | no | `path \| no_user_lines \| prompt_source \| unknown_prompt_source \| entrypoint_fallback \| no_signal`. |
| `first_prompt_source` | string | yes | The qualifying first user line's raw `promptSource`, if any. Null for subagent rows (never consulted) and for rows with no qualifying line. |
| `entrypoint` | string | yes | Same qualifying line's `entrypoint`, when read. |
| `first_ts` | string (ISO 8601, UTC) | yes | Null iff no line in the file carried a parseable timestamp. |
| `last_ts` | string (ISO 8601, UTC) | yes | Same nullability as `first_ts`. |
| `duration_s` | float | yes | `last_ts - first_ts` in seconds; null unless both are set. |
| `api_turns` | int | no | See "Turn counting". |
| `user_prompts` | int | no | See "Turn counting". |
| `assistant_messages` | int | no | Count of **distinct deduped `message.id` values with a `usage` block** — not raw assistant-type line count, which would overcount by the same streamed-repeat factor the token dedup corrects for. |
| `input_tokens` | int | no | Deduped total. |
| `cache_creation_5m` | int | no | Deduped total. |
| `cache_creation_1h` | int | no | Deduped total. |
| `cache_creation_total` | int | no | `cache_creation_5m + cache_creation_1h`. |
| `cache_read_tokens` | int | no | Deduped total. |
| `output_tokens` | int | no | Deduped total. |
| `primary_model` | string | yes | See `pick_primary_model` below. Null iff the file has zero usage-bearing lines. |
| `models` | string | no | `;`-joined, sorted, every distinct model ID seen. Empty string if none. |
| `model_count` | int | no | `len(models split on ';')`, i.e. number of distinct models. |
| `malformed_lines` | int | no | Count of lines that failed `json.loads` in this file. |
| `flagged` | bool | no | See "Thresholds". |
| `flag_reasons` | string | no | `;`-joined, sorted, subset of `{api_turns, cache_creation_total}`. Empty string if not flagged. |

`pick_primary_model`: the model with the highest total token volume
(`input_tokens + cache_creation_total + cache_read_tokens + output_tokens`)
— the best available spend-share proxy without a pricing table. Ties are
broken by higher `assistant_messages`, then by lexically smallest model ID,
for full determinism.

Multi-valued fields (`models`, `flag_reasons`) are `;`-separated and sorted,
inside the CSV's normal quoting — safe for a naive downstream
`awk -F,`/`csv.DictReader` join with no unescaped-comma risk.

### `session_model_tokens.csv` (long format, one row per `(session_id, model)`)

Columns: `session_id, project, classification, model, input_tokens,
cache_creation_5m, cache_creation_1h, cache_creation_total,
cache_read_tokens, output_tokens, assistant_messages`.

This table exists specifically so that `$` costing is a downstream **join**,
never a duplicated pricing table inside this tool (see "Joining against `$`"
below). `project` and `classification` are carried alongside `session_id`
and `model` so a `$`-join can filter/group without a second join back to
`sessions.csv` for the common cases. The design intentionally left this
column set unspecified beyond "long format, one row per `(session_id,
model)`" — the extra columns here (`project`, `classification`,
`assistant_messages`) are additive convenience, not a departure from that
shape; every column in `sessions.csv` that sums per-model (the six token
fields) sums back exactly, verified by
`test_model_rows_sum_to_session` in the fixture suite.

For every `session_id`, summing this table's six token columns across its
model rows reproduces that session's row in `sessions.csv` exactly, and the
row count per session equals `sessions.csv`'s `model_count`.

### `session_summary.json` (+ matching stdout)

Counts and token totals per classification, flagged-row count, every
guardrail counter (`files_seen`, `files_excluded_non_transcript`,
`files_filtered_out`, `rows_excluded_no_timestamp`, `files_unreadable`,
`subagent_path_unmatched`, `malformed_lines_total`, `usage_lines_seen`,
`usage_lines_missing_message_id`, `cross_file_duplicate_ids`),
`classification_basis_counts`, `unknown_prompt_source_values`,
`pyarrow_available`, and the top 20 flagged rows by
`(cache_creation_total, api_turns)`.

### Parquet (conditional)

If `pyarrow` is importable and `--no-parquet` was not passed,
`sessions.parquet` and `session_model_tokens.parquet` are written alongside
the CSVs, built via an **explicitly declared schema**
(`session_parquet_schema(pa)` / `model_parquet_schema(pa)`) — never via
`pa.Table.from_pylist`'s type inference. This matters concretely: a naive
`from_pylist` call infers each column's type from its values, and the very
first row this tool emits (its file-discovery order puts a top-level
session first, whose `parent_session_id` is null) would coerce that whole
column to pyarrow's `null` type instead of `string` — silently dropping the
type information a downstream reader depends on. The explicit schema fixes
`parent_session_id` as `string` (nullable) and every token column as
`int64` regardless of row order. Timestamps are written as plain ISO
strings (`first_ts`, `last_ts`), never `pa.timestamp()`, so the CSV and
Parquet outputs always agree on their textual form.

If pyarrow is not importable, both CSVs are written exactly as normal, a
one-line note is printed to stdout, and `pyarrow_available: false` is set
in the summary. `--no-parquet` suppresses writing Parquet files
unconditionally but still reports the true `pyarrow_available` value (i.e.
it reflects importability, not whether the flag suppressed writing).

## Joining against `$`

This tool carries **no pricing table and no `$` column**, deliberately —
see the sibling `../token-cost-analysis/token_cost_report.py`'s
`MODEL_PRICING`/`TIER_FALLBACK`/`resolve_pricing`. Keeping pricing in
exactly one place avoids a second table silently drifting out of sync with
the first. Recipe (join `session_model_tokens.csv` against the sibling's
pricing table):

```python
import csv, os, sys

sys.path.insert(0, "../token-cost-analysis")
from token_cost_report import resolve_pricing

total_usd = 0.0
with open("session_model_tokens.csv", newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        pricing, path, norm = resolve_pricing(row["model"])
        if pricing is None:
            continue  # unresolved model id -- not priced, not silently zero-costed
        p_in, p_out, p_cw1h, p_cw5m, p_cread = pricing
        total_usd += (
            int(row["input_tokens"]) / 1e6 * p_in
            + int(row["output_tokens"]) / 1e6 * p_out
            + int(row["cache_creation_1h"]) / 1e6 * p_cw1h
            + int(row["cache_creation_5m"]) / 1e6 * p_cw5m
            + int(row["cache_read_tokens"]) / 1e6 * p_cread
        )
print("$%.2f" % total_usd)
```

This snippet was run end-to-end against a real `session_model_tokens.csv`
(full local corpus, 2026-09-11): 16,962 of 17,008 model-rows resolved to
exact pricing, 46 resolved to neither exact nor tier pricing (synthetic/
placeholder model values present in a handful of sessions — e.g. test
harness transcripts whose `message.model` is not a real Claude model ID)
and were skipped rather than mispriced. `resolve_pricing` never raises.

## Date-filter semantics

`--since`/`--until` filter on a session's **`first_ts` only** — the
row-level equivalent of "this session started within the window" —
inclusive, UTC. Not `last_ts`, not any overlap test.

**Known, accepted limitation**: a session that starts just before `--since`
but whose activity (and token spend) continues into the window is excluded
entirely, including the tokens it burned inside the window. Overlap
semantics would require splitting a session's token totals across the
boundary, which this tool does not attempt. Widen the window if boundary
accuracy matters for a specific analysis.

A row with a null `first_ts` passes an unfiltered run (nothing to filter
against) and is excluded — counted in `rows_excluded_no_timestamp` — the
moment either `--since` or `--until` is set.

## Error handling

- A per-line `json.loads` failure increments that file's `malformed_lines`
  and the file's row is still emitted (not dropped).
- An unreadable file (missing, a directory masquerading as a `.jsonl`, a
  permission error) is skipped, counted in `files_unreadable`, and a
  `WARNING` is written to stderr. Never fatal.
- A missing/unparseable `timestamp` on any line leaves `first_ts`/`last_ts`
  null; never a crash.
- **Invariant (unfiltered run)**: `rows + files_unreadable +
  files_excluded_non_transcript == files_seen`. **Invariant (filtered
  run)**: the above, plus `+ files_filtered_out + rows_excluded_no_timestamp
  == files_seen`. Both forms are asserted in the fixture test suite.

## Guardrail counters (full list)

`files_seen`, `files_excluded_non_transcript`, `files_filtered_out`,
`rows_excluded_no_timestamp`, `files_unreadable`, `subagent_path_unmatched`,
`malformed_lines_total`, `usage_lines_seen` (raw usage-bearing line count,
pre-dedup — the denominator for the dedup-ratio corpus invariant),
`usage_lines_missing_message_id`, `cross_file_duplicate_ids`.

## Design notes (two points the original design left implicit)

- **`agent_id`**: derived as `session_id if <row is a subagent transcript>
  else None`. No other definition appears anywhere in this tool's design —
  it is simply a semantically-named alias for "this row's own id, when the
  row is an agent". Kept as a separate column from `session_id` (rather
  than omitted) because a downstream reader filtering specifically for
  agent rows can test `agent_id is not None` without also checking
  `classification == "subagent"`.
- **`session_model_tokens.csv` columns**: the design specified only "long
  format, one row per `(session_id, model)`" with no explicit column list.
  The shipped column set (`session_id, project, classification, model` +
  the six token fields + `assistant_messages`) was chosen because
  `project`/`classification` make the table self-sufficient for the common
  per-project or per-classification `$` rollups without a join back to
  `sessions.csv`, and `assistant_messages` mirrors `sessions.csv`'s own
  per-model message count for symmetry. This is additive convenience on top
  of the required shape, not a deviation from it.

## Verification

### Fixture test suite (machine-independent)

```
python3 -m unittest -v
```

Runs the full known-answer fixture suite (10 hand-authored transcript files
under `tests/fixtures/projects/`, covering every classification branch, both
subagent path depths, the non-transcript exclusion, dedup direction on both
populations, filters, thresholds, and error handling) plus the pure-function
unit tests. These do not depend on `~/.claude/projects` and behave
identically on any machine.

### Real-corpus regression tests (machine-specific)

The same `python3 -m unittest -v` invocation above also runs a
`TestRealCorpusInvariants` suite, skipped automatically if
`~/.claude/projects` does not exist. **These 9 invariants are calibrated
against this tool's own development machine's corpus** (classification
counts, threshold-provenance percentiles, flag rate, and the real-work
turn-ratio band are the machine-specific ones; no-silent-drops, dedup
firing, cross-file duplicate rate, and the runtime budget are structural
and travel to any corpus). **A failure on a different machine's corpus is
not on its own evidence the tool is broken** — re-derive the bands there
first. Measured on this tool's development corpus (2026-09-11, `n=17,539`
files, ~8.5s wall-clock):

| # | Invariant | Band | Observed |
|---|---|---|---|
| 1 | `rows + files_unreadable + files_excluded_non_transcript == files_seen` | exact | 17,539 == 17,539 |
| 2 | subagent parent coverage + both-depths detection | ≥99% parents resolve; nested-depth files > 400 | 100% resolved; 683 nested / 6,051 flat |
| 3 | dedup ratio `sum(assistant_messages)/usage_lines_seen` | `[0.30, 0.55]` | 0.484 |
| 4 | classification split (full corpus) | real_work `[400,700]`, automated `[9000,12000]`, subagent `[6500,7500]`, unclassified ≤1% | 500 / 10,284 / 6,734 / 9 |
| 5 | threshold provenance (real_work only) | p95 `api_turns`/`cache_creation_total` within ±20% of 175 / 1,525,000 | 175.0 / 1,522,208 |
| 6 | flag rate on real_work | `[0.02, 0.12]` | 0.080 |
| 7 | `user_prompts <= api_turns` everywhere; real_work median ratio | `[2.5, 6.0]`; automated/subagent well below | held on every row |
| 8 | cross-file duplicate id rate | ≤0.5% of distinct ids | 0.110% (155 / 140,693) |
| 9 | full-corpus runtime | < 45s | ~8.5s |

Invariant 4's `real_work` band is deliberately **kept tight** at
`[400,700]`: real-work classification only ever reaches a row via
`promptSource`/entrypoint on **top-level** files, which the subagent
path-detection logic never touches — so this band is exactly what would
catch a regression in that path detection (if the workflow-nested subagent
files stopped being caught as `subagent`, they'd fall through and inflate
`real_work` toward roughly double this band). Do not widen it to "tolerate"
a symptom; widening would make it blind to the one regression it exists to
catch.

### Manual clean-venv, no-pyarrow check

```
python3 -m venv /tmp/session-analysis-check
/tmp/session-analysis-check/bin/python3 session_analysis.py --root tests/fixtures/projects --out-dir /tmp/session-analysis-check-out
```

Confirms: exit code 0, both CSVs written correctly, no `.parquet` files, and
the printed summary reports `pyarrow available: False`. This is also
exercised automatically (portably, no real venv needed) by
`TestParquetAbsentPath` via `unittest.mock.patch.dict(sys.modules,
{"pyarrow": None})`.

### Cross-check against the sibling tool (manual, not asserted)

Comparing `sessions.csv` token sums against
`token_cost_report.py --hosts local`'s corpus totals: expect **this tool's
totals ≥ the sibling's**, and not by a small residual. The dominant source
of divergence is `output_tokens` specifically: the sibling keeps the
**first** occurrence per `message.id`, this tool keeps the **last** — and on
subagent-heavy corpora that is a measured ~3.3x difference on
`output_tokens` alone (see "Token accounting" above). Treat this as the
expected, understood direction and scale of disagreement, not a small gap
worth debugging.
