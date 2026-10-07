# Episode cost runbook

Computes the fully loaded, API-equivalent cost of a GitHub issue "episode" from
Claude Code session transcripts, with a coverage report that says how much of the
project's spend could and could not be attributed. Standard-library Python only.
Read-only: it reads transcripts (and the two small JSON files you give it) and
writes only to the directory given by `--out`.

Files: `episode_cost.py` (the tool), `test_episode_cost.py` (unit tests).

## 0. Prerequisites

- Python 3 (developed and tested on 3.14; standard library only).
- Transcripts under `~/.claude/projects/<project-dir>/`. A project directory is the
  working directory's path with `/` replaced by `-`, so it starts with `-`.
- For the issue list and the reconciliation: `gh` (authenticated, read access to the
  repository), `jq`, and `ccusage` (`ccusage --version`).
- Place the three files of this directory anywhere; run everything from a directory
  that does not contain other `.py` files (the commands below use `python3 -I`).

Self-test (no transcripts needed, takes under a second):

```
cd <dir with episode_cost.py>
python3 -m unittest test_episode_cost
```

Pass: `OK` with zero failures.

## 1. Definitions

- **Episode of issue N**: every session of the project, and the subagent transcripts
  stored under it, that is attributed to N, from its first turn to the merge of the
  pull request that closed N (`merged_at`; `closed_at` if there was no PR).
- **Tail**: the 14 days after the merge, reported separately (`--tail-days`).
  **Late**: anything attributed to N after the tail. Total = episode + tail + late.
- **Cost**: each API turn priced at Anthropic list prices (table `PRICES` in the
  script, with its verification date, which is printed in every report). No plan,
  discount or cache-TTL assumption beyond the 5-minute/1-hour split recorded in each
  turn. Fast-mode turns are counted and priced at standard rates. A model that is
  not in the table is priced by its family if that is unambiguous (listed under
  "Family-fallback models") and otherwise left at zero and listed under "Unpriced
  models". Before relying on a report, check both lists are empty and re-verify the
  table against the live pricing page.
- **De-duplication**: a message id appears on several transcript lines (streaming
  updates) and, for resumed or forked sessions, in several sessions. One record is
  kept per message id: the one with the most output tokens (earliest wins a tie).
  This matches ccusage's rule. The number of cross-session duplicates is reported.
- **Cost classes**:
  - `main`: main-thread turns of a session that mostly ran on the default branch;
  - `branch`: main-thread turns of a session that mostly ran on another branch;
  - `subagent`: every turn from a subagent transcript, rolled into its parent;
  - `hook_child`: headless `claude -p` sessions started by hooks (entrypoint
    `sdk-cli` and either at most 3 API turns or a first prompt starting with
    `--hook-prompt-prefix`). They are listed separately, never merged into `main`.

## 2. Attribution signals, in priority order

The first tier that yields at least one issue number decides the whole session.

1. **Title**: the session's latest custom title contains `#N`. Pilot convention:
   start every session with `claude --name "#N short-slug"` (or rename it with
   `/rename "#N short-slug"`). A `#<PR number>` is resolved to its issue when the
   issue file lists the PR. This is the only signal that is reliable for sessions
   that run on the default branch (orchestration, review, verification), which is
   why the convention matters.
2. **Branch**: the git branch recorded in the session's entries (main thread and
   subagents) matches `issue-N` (so `issue-N` and `feature/issue-N-*` both match).
3. **Task prompt**: the first user prompt has a line starting `Task: #N`.
4. **Subagent parent link**: a subagent transcript takes its parent session's
   verdict (the parent is the session directory the transcript is stored in).
   Subagents stored under `<session>/subagents/<dir>/.../agent-*.jsonl` count too.
5. **PR link** (opt-in, `--pr-repo OWNER/NAME`): the session itself emitted
   `pr-link` entries for a pull request of that repository that the issue file lists
   for an issue. Weak session-level evidence, so it ranks last.

Multi-issue sessions: when the deciding tier names several issues, a turn whose own
branch names one of them goes to it, and every other turn goes to a **shared**
bucket (reported per issue set and as an even-split "exposure", never added to any
issue's total). Sessions with no signal go to **unattributed**. Nothing is dropped:
the buckets always sum to the project total.

Known bias, reported in every run as "signal conflict": under title-first priority a
session titled `#A` that worked on a branch for issue `#B` is charged entirely to A.
`--turn-branch-wins` re-runs with turn branches overriding a title or prompt, as a
sensitivity check. On a real store the two rules changed the median per-issue cost
by roughly a factor of two, so quote both (or fix the title convention) before
comparing two groups of issues.

## 3. Inputs

### 3.1 Issue file (`--issues`)

A JSON list of `{number, merged_at, closed_at, prs}`. Build it for issues
`N1 N2 ...` of `OWNER/NAME`:

```
cat > mkissues.sh <<'EOF'
#!/bin/sh
# usage: mkissues.sh OWNER/NAME N [N...]   -> JSON list on stdout
REPO=$1; shift
for N in "$@"; do
  gh issue view "$N" --repo "$REPO" --json number,closedAt,closedByPullRequestsReferences \
  | jq -c '{number, closed_at: .closedAt, prs: [.closedByPullRequestsReferences[].number]}' \
  | while read -r ROW; do
      PR=$(echo "$ROW" | jq -r '.prs[0] // empty')
      MERGED=null
      [ -n "$PR" ] && MERGED=$(gh pr view "$PR" --repo "$REPO" --json mergedAt | jq '.mergedAt')
      echo "$ROW" | jq -c --argjson m "$MERGED" '. + {merged_at: $m}'
    done
done | jq -s .
EOF
sh mkissues.sh OWNER/NAME N1 N2 > issues.json
```

Issues without a closing PR get `merged_at: null` and the close time is used.
The file may be omitted; the script then reports everything as unlisted issues.

### 3.2 ccusage export (`--ccusage-json`)

```
ccusage session --json > ccusage_session.json
```

Use the default (online pricing) mode, not `--offline`: the offline price cache lags
new models, and ccusage then reports a model's usage at zero cost. The script
detects that case (cost 0 with tokens > 0), reports the model, and excludes it from
the tolerance check, but the comparison is cleaner without it.

### 3.3 Freezing the inputs

An active store keeps growing while you work, so two runs a minute apart can differ
legitimately. To produce an analysis you can freeze and re-verify, copy the project
directories you analyse into a snapshot and point both tools at it:

```
SNAP=$PWD/snap
mkdir -p "$SNAP/projects"
cp -a ~/.claude/projects/<project-dir>* "$SNAP/projects/"
CLAUDE_CONFIG_DIR="$SNAP" ccusage session --json > ccusage_session.json
```

and add `--projects-root "$SNAP/projects"` to the commands below. Keep the snapshot,
the issue file and the ccusage export together; with these unchanged, the output is
byte-for-byte reproducible (section 5).

## 4. Run

Project directory names begin with `-`, so the glob must use `=`:

```
python3 -I episode_cost.py \
  "--project-glob=-home-me-myproject*" \
  --issues issues.json \
  --pr-repo OWNER/NAME \
  --coverage-since 2026-09-22 \
  --ccusage-json ccusage_session.json \
  --out out/
```

`--project-glob` may repeat; the default is every project directory. `--coverage-since
YYYY-MM-DD` adds a second coverage table limited to turns on or after that UTC date.
`--tail-days`, `--hook-prompt-prefix`, `--ccusage-tolerance` (default 0.005) and
`--turn-branch-wins` are optional. Exit status: 0 success; 3 the ccusage
reconciliation is outside tolerance; anything else is an error.

Outputs in `--out` (no prompt text, issue titles or secrets are written; only ids,
project directory names, issue numbers, timestamps, counts and dollars):

| file | content |
|---|---|
| `summary.md` | per-issue table, coverage tables, pricing diagnostics, one-line reconciliation |
| `issues.csv` | per issue: episode / tail / late / total USD; episode USD by class (main, branch, subagent, hook child); sessions (by class), subagent transcripts, turns (main/subagent), first and last timestamp, episode first/last, shared exposure |
| `sessions.csv` | per session: class, deciding signal, issues, verdict (`issue`, `multi`, `unattributed`), turns, subagent transcripts, USD (subagents included), first/last timestamp |
| `report.json` | everything above plus shared buckets, unattributed cost by class, parameters (including a hash of the issue file) and reconciliation |
| `reconciliation.md` | ccusage comparison (only with `--ccusage-json`) |

## 5. Determinism check (pass: identical hashes)

```
python3 -I episode_cost.py ...same arguments... --out out1/
python3 -I episode_cost.py ...same arguments... --out out2/
(cd out1 && sha256sum *) > h1; (cd out2 && sha256sum *) > h2; cmp h1 h2 && echo IDENTICAL
```

Pass: `IDENTICAL` (all five files). Costs are integer nano-dollars internally and all
orderings are explicit, so any difference means the inputs changed (a live store,
section 3.3) or the script was edited.

## 6. Coverage report: how to read it

Both tables (all time, and since the `--coverage-since` date) split the project's
total cost into:

- `target_issues`: issues listed in the issue file (your analysis set);
- `other_issues`: issues found by a signal but not listed (other work in the project);
- `shared`: turns of multi-issue sessions with no way to split them;
- `unattributed`: no signal at all.

"Attributed share" = target + other. Below it: cost by class within each bucket, the
cost by deciding signal, and the signal-conflict amount from section 2. The all-time
table is dominated by `other_issues` and is only a sanity check; judge attribution
quality on the since-date table over the period your issue set covers.

What lands in `unattributed`, and why it is not forced into an issue:

- project sessions with no title, branch, task or PR signal, typically a long
  orchestration session on the default branch started without `--name "#N ..."`;
  list them with `awk -F, '$6=="unattributed" && $3!="hook_child"' sessions.csv`
  (columns: project, session_id, class, signal, issues, verdict, ...);
- hook children: headless `claude -p` runs started by hooks. A hook child's
  transcript carries no link to the session that triggered it, and its branch is the
  hook's working directory's, so no principled per-issue attribution exists. They are
  small individually but numerous; report them as a separate overhead line rather
  than guessing;
- sessions for issues outside the studied window or without any issue (maintenance,
  research).

Rule of thumb for a pilot: an unattributed share above about 10% of the period's
cost means the naming convention is not being followed or hook overhead is large;
fix the convention first, then compare.

## 7. Reconciliation with ccusage (pass: within +/-0.5%)

`reconciliation.md` compares, over the sessions present in both the store and the
ccusage export, total cost, a per-model token and cost table, and a subagent
roll-up check. Pass: "Delta after excluding ccusage-unpriced models" is within
`+/-0.50%` (the exit status is 0), and the roll-up delta is within the same
tolerance while the "main thread only" figure is far below it (subagents are real
cost; ccusage groups them under the parent session id, as this tool does).

Why there is a residual, and how to explain it (check these in order):

1. **Unpriced models in ccusage.** Offline mode (or an old price cache) leaves a new
   model at zero cost. The script excludes any model ccusage prices at zero from the
   tolerance figure and names it. Re-export in online mode to remove it.
2. **Nested subagent transcripts.** ccusage reads `<session>/subagents/*.jsonl` but
   not transcripts stored one directory deeper, such as workflow agents under
   `<session>/subagents/workflows/<run>/agent-*.jsonl`. This tool counts them (they
   are billed API usage). `reconciliation.md` prints their file count and cost and
   the delta with them removed. On the store this was validated against (about 6,200
   common sessions, about USD 6,400) the entire +0.083% residual was exactly these 14 files
   (USD 5.33), and the delta without them was 0.000%. The worst single session
   (+11%) was the session holding them.
3. **Cross-session duplicate messages** (resumed or forked sessions): both tools keep
   one copy per message id, but may attribute it to different sessions. Per-session
   figures can differ in opposite directions; the total over all sessions does not.
   Per-session comparison is therefore not a pass criterion, the total is.
4. **Concurrency.** A live store changes between the ccusage export and the run. Use
   the snapshot of section 3.3 to remove this.

If the delta is outside tolerance and none of 1 to 4 explains it, do not use the
report: compare the per-model table (token counts that differ point to
de-duplication or unread files; equal tokens with different cost point to prices).

## 8. Subagent roll-up check

The `Subagent roll-up check` section of `reconciliation.md` lists, for sessions that
have subagent transcripts, ccusage vs this tool with subagents rolled in vs main
thread only, plus one named example session. Pass: roll-up within tolerance. A
main-thread-only figure far below ccusage (around -60% on the validated store) shows
how much spend per-issue figures miss if subagents are not rolled up.

## 9. Operating notes

- Run after the issue's PR is merged; the tail needs 14 further days to be complete.
- Transcripts are only retained for the period Claude Code keeps them
  (`cleanupPeriodDays`); freeze a snapshot before they expire.
- Re-verify the price table (`PRICES` and its date) against the live pricing page
  whenever a new model appears; the report prints the verification date.
- The script never reads settings files, credentials or MCP configuration, never
  prints transcript text, and writes only below `--out`.
