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
- **After the merge** (never part of the episode). Turns attributed to N after the
  merge are reported in four separate pieces, by where the turn ran:
  - **tail** (`tail_usd`): the turn's own branch is N's, within `--tail-days` (default
    14) of the merge, i.e. real follow-up work on the issue;
  - **post-merge default-branch activity (not attributable to the issue)**
    (`tail_default_branch_usd`): turns on the default branch (or on a branch that names
    no issue) of a session whose title or branch evidence points at N, within the tail
    window. This is whatever the session did next, not work on N;
  - **cost on other issues' branches** (`tail_other_issues_usd`): turns within the tail
    window whose branch names a different issue. Never charged to N under the default
    rule (they go to the issue whose branch it is); it is non-zero only under
    `--title-first` or in the title-first column of the comparison;
  - **late** (`late_usd`): anything attributed to N after the tail window, any branch.

  `total_usd` = episode + tail + the two other post-merge pieces + late, so that
  per-issue totals + shared + unattributed still equal the project total. The headline
  **episode cost never includes** the post-merge default-branch activity or the cost on
  other issues' branches. Before this change `tail_usd` held all three post-merge
  pieces added together (within the window); on the validated store that old tail was
  185.21 USD, of which 0.36 was on the same issue's branch.
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

## 2. Attribution: turn-level branch first, then the session verdict

**Default rule (branch-first).** A turn whose own git branch matches `issue-N` (so
`issue-N` and `feature/issue-N-*` both match) is charged to N, whatever the session is
called. Every other turn (default branch, or a branch that names no issue) takes the
session-level verdict, the first tier below that yields at least one issue number:

1. **Title**: the session's latest custom title contains `#N`. Pilot convention:
   start every session with `claude --name "#N short-slug"` (or rename it with
   `/rename "#N short-slug"`). A `#<PR number>` is resolved to its issue when the
   issue file lists the PR. Under the default rule the title only labels turns made on
   the default branch (orchestration, review, verification) and sessions with no
   branch evidence, which is why the convention still matters.
2. **Branch**: the git branches recorded in the session's entries (main thread and
   subagents) name issues (a session with one branch issue sends its default-branch
   turns to it).
3. **Task prompt**: the first user prompt has a line starting `Task: #N`.
4. **Subagent parent link**: a subagent transcript takes its parent session's
   verdict (the parent is the session directory the transcript is stored in).
   Subagents stored under `<session>/subagents/<dir>/.../agent-*.jsonl` count too.
5. **PR link** (opt-in, `--pr-repo OWNER/NAME`): the session itself emitted
   `pr-link` entries for a pull request of that repository that the issue file lists
   for an issue. Weak session-level evidence, so it ranks last. It only exists when
   `--pr-repo` is passed, so **the numbers depend on that flag**: on the validated
   store it carried about 32.80 USD of the attributed cost since 2026-09-22. Use the
   same `--pr-repo` for every run you compare.

**`--title-first` (older rule, kept as a flag).** The session verdict decides every
turn, so a session titled `#A` that worked on the branch of issue `#B` is charged
entirely to A. The original specification prescribed this rule; the default was
changed because a long-lived orchestration session's title names an early issue while
its turns move on to later issues' branches. The branch is then the correct owner
(checked against the session's own PR links on the validated store), and title-first
understates the later issues' episode cost.
`--turn-branch-wins` is still accepted and does nothing (it is the default now).

**Both rules are always computed in one run** and printed side by side in `summary.md`
("Episode cost under both attribution rules") and `report.json` (`rule_comparison`):
median and sum of episode cost over the same issue set, their delta, and the
post-merge pieces of section 1 under each rule. `issues.csv` carries
`episode_branch_first_usd` and `episode_title_first_usd` per listed issue. The flag
only chooses which rule drives the per-issue table and `episode_usd`. Quote both
medians; a large gap means the title convention is not being followed and title-first
numbers should not be used for comparison. Example numbers from one store (one
project, 20 issues with attributed cost, turns since 2026-09-22, `--pr-repo` given):
median 5.17 USD title-first vs 10.52 USD branch-first, episode sum 305.13 vs 367.47
USD. These are example figures from one store, not thresholds.

Multi-issue sessions: when the session verdict names several issues, a turn that its
own branch does not place goes to a **shared** bucket (reported per issue set and as an
even-split "exposure", never added to any issue's total). Sessions with no signal go to
**unattributed**. Nothing is dropped: per-issue totals + shared + unattributed always
sum to the project total (checked under both rules on the validated store, to the
nano-dollar).

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
`--title-first` (section 2), `--tail-days`, `--hook-prompt-prefix` and
`--ccusage-tolerance` (default 0.005) are optional; `--turn-branch-wins` is a no-op
alias. Exit status: 0 success; 3 the ccusage
reconciliation is outside tolerance; anything else is an error.

Outputs in `--out` (no prompt text, issue titles or secrets are written; only ids,
hashed project ids, issue numbers, timestamps, counts and dollars; a project directory
name, which embeds a local path, is written as `p-` plus 8 hex digits of its SHA-256,
so rows stay joinable but no path is shared, and `report.json` holds the hashed
globs):

| file | content |
|---|---|
| `summary.md` | per-issue table, both-rules comparison, coverage tables (with the evidence split), pricing diagnostics, one-line reconciliation |
| `issues.csv` | per issue: episode / tail / late / total USD; episode USD by class (main, branch, subagent, hook child); sessions (by class), subagent transcripts, turns (main/subagent), first and last timestamp, episode first/last, shared exposure; appended columns `tail_default_branch_usd`, `tail_other_issues_usd`, `episode_branch_first_usd`, `episode_title_first_usd` (blank for issues not in the issue file) |
| `sessions.csv` | per session: hashed project id, class, session-level signal and issues, verdict (`issue`, `multi`, `unattributed`), turns, subagent transcripts, USD (subagents included), first/last timestamp, `turn_issues` (issues the session's turns were actually charged to) |
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
cost by deciding signal (per turn), the signal-conflict amount (turns charged to an
issue although their own branch names another; zero under the default rule), and a
line splitting the attributed cost into **attributed by branch/PR evidence** (the
turn's own branch names the issue it is charged to, or the `pr` tier decided) and
**attributed by title/prompt only**. Read "88% attributed" as "88% attributed, of
which only the branch/PR part is confidently attributed": on the validated store
since 2026-09-22 the split was 48.72% of total by branch/PR evidence and 39.80% by
title/prompt only. Those are example figures from one store. The all-time
table is dominated by `other_issues` and is only a sanity check; judge attribution
quality on the since-date table over the period your issue set covers.

What lands in `unattributed`, and why it is not forced into an issue:

- project sessions with no title, branch, task or PR signal, typically a long
  orchestration session on the default branch started without `--name "#N ..."`;
  list them with `awk -F, '$6=="unattributed" && $3!="hook_child"' sessions.csv`
  (columns: project, session_id, class, signal, issues, verdict, ...);
- hook children: headless `claude -p` runs started by hooks. A hook child's
  transcript carries no link to the session that triggered it. Its branch is the hook's
  working directory's, so a hook child whose recorded branch names an issue is
  attributed to that issue by the branch rule (15.89 USD of the validated store's
  target-issue cost), and the rest, with no issue branch, stay unattributed (26.34 USD
  since 2026-09-22). Treat the attributed part as a branch-based approximation, not a
  link to the triggering session. They are small individually but numerous; report them
  as a separate overhead line rather than guessing;
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
