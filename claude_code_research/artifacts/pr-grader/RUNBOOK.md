# PR grader runbook

Grade one merged pull request from 1 to 5 using three independent, blinded,
read-only Opus reviewers plus a verification pass, then report a table row.
Everything here is portable: it needs Python 3.9+, git, the `gh` CLI (only to
fetch the linked issue text), and the Claude Code CLI (`claude`) logged in on
the machine. No third-party Python packages.

## What the grade does and does not mean

* It is a graded signal about one merged change judged against its linked issue,
  by reviewers who do not know how the change was produced.
* Reviewers tend to report something even on sound work, and the grade anchors
  are coarse. The absolute grade means little. Only differences between groups
  of PRs (for example two working methods graded on comparable issues) are
  meaningful, and only after the grader has been shown to discriminate (see
  "Calibration gate").
* It does not run the code, the tests or any container. ACs that need those are
  recorded as `not_assessable` and never lower the grade.
* It is not a substitute for hard signals (tests, later fix PRs, reverts,
  reopened issues). If calibration shows no separation, drop the grade and rely
  on the hard signals.

## Files in this directory

| file | role |
| --- | --- |
| `pr_grader.py` | runner: `preflight`, `stage`, `grade`, `table` sub-commands |
| `rubric.md` | AC statuses, finding severities, test adequacy, 1-5 anchors and caps (inserted into every prompt, and the spec for the grade function) |
| `prompts/reviewer_system.txt`, `prompts/reviewer_task.txt` | identical reviewer prompt for every run |
| `prompts/verifier_system.txt`, `prompts/verifier_task.txt` | verifier prompt |
| `schemas/review.schema.json`, `schemas/verification.schema.json` | required JSON output of reviewers and verifiers |
| `strip-list.example.txt` | example repo-specific strip list (the poc repository) |
| `tests/test_pr_grader.py` | unit tests (no model calls; a fake `claude` executable stands in) |

## Setup and preflight

Set these once per shell. Every command below uses absolute paths and works from
any directory.

```
GRADER=/abs/path/to/pr-grader            # the directory holding pr_grader.py
REPO=/abs/path/to/local/clone            # read only
OUT=/abs/path/to/output                  # written by the runner; never shown to reviewers
# optional: STAGE_ROOT=/abs/neutral/dir  # default /run/user/<uid>/pgrade (uid, not user name)
```

Requirements: Python 3.9+, git, `gh` (only to fetch the issue text), and the
Claude Code CLI logged in on the machine. **Minimum Claude Code CLI version:
2.1.292** (the version this runbook was developed and tested against; older
versions are not supported and the runner refuses them). No third-party Python
packages. `/run/user/<uid>` must exist and be writable (systemd tmpfs), or pass
`--stage-root` with another neutral absolute directory.

```
python3 --version                      # 3.9 or newer
git --version
gh auth status                         # only needed when the issue is fetched with gh
CLAUDE=$(command -v claude || ls "$HOME/.local/bin/claude" "$HOME/.claude/local/claude" /usr/local/bin/claude 2>/dev/null | head -1)
echo "$CLAUDE"; "$CLAUDE" --version    # record this version with every result
```

Pass the absolute path to the runner with `--claude "$CLAUDE"` when `claude` is
not on `PATH` in a non-interactive shell (aliases and shell functions are not
visible to child processes).

Run the unit tests (no model calls; they write only under `PR_GRADER_TMP` and
`/run/user/<uid>/pgradetest*`, removed afterwards):

```
mkdir -p "$OUT/test-tmp"
PR_GRADER_TMP="$OUT/test-tmp" python3 -I "$GRADER/tests/test_pr_grader.py"
```

Expected: `OK` with no failures.

Preflight (do it on every machine and after every CLI upgrade). It checks the CLI
version against the minimum, that `--restricted` is listed in `claude --help`,
that a Read inside a staged directory works and a Read of a path outside it is
refused (a live Haiku probe, a fraction of a cent), and what identifying text the
CLI puts in the reviewer's own context:

```
python3 -I "$GRADER/pr_grader.py" preflight --claude "$CLAUDE" --out "$OUT"
```

Expected: `PREFLIGHT OK`. Any problem exits 5 and `grade` refuses to start. The
version and `--restricted` checks (no model call) also run at the start of every
`grade`. Read the context-probe warning; see "Known residual leak" below.

## Inputs

* a local clone of the repository (only read: `git archive`, `git diff`,
  `git rev-parse`; the clone is never checked out, modified or fetched);
* the merge commit of the PR (for a squash merge, the squash commit; the diff is
  taken against its first parent);
* the linked issue (`--gh-repo owner/name --issue N`, or `--issue-file path`
  whose first line is the title and the rest the body);
* the PR number and PR branch name, used only by the leakage scan (`--pr-number`,
  `--branch`), plus any distinctive commit-subject phrase (`--leak-term`);
* optionally a strip list (`--strip-list`), see "Blinding rules";
* an output directory `--out`, which holds results and records and is never shown
  to reviewers. Reviewers see only the neutral stage root (default
  `/run/user/<uid>/pgrade/<ten letters>/`). The runner refuses a stage root whose
  path contains the user name, the home directory name, `.scratch`, or any
  component of the `--out` or repository paths. `--label` is only an output
  sub-directory name and is never shown to reviewers.

## Run

Stage and scan only (no model call; do this first and read the result):

```
python3 -I "$GRADER/pr_grader.py" stage \
  --repo-path "$REPO" --merge-commit <sha> --label <label> \
  --gh-repo owner/name --issue <N> \
  --pr-number <PR> --branch "<PR branch name>" --leak-term "<any commit-subject phrase>" \
  --strip-list /abs/path/to/strip-list.txt \
  --out "$OUT"
```

Full grade (stage, three reviewers, verification, aggregate):

```
python3 -I "$GRADER/pr_grader.py" grade <same arguments> --claude "$CLAUDE" \
  --model opus --effort high --reviewers 3 --parallel 2 --timeout 2400
```

Run it detached and wait with an explicit loop; a grade takes several minutes:

```
nohup python3 -I "$GRADER/pr_grader.py" grade ... > "$OUT/grade.log" 2>&1 &
PID=$!
while kill -0 $PID 2>/dev/null; do sleep 15; done
tail -n 20 "$OUT/grade.log"
```

Exit codes: 0 done, 3 blinding scan or leak check failed (before any model call),
4 stale stored result or other refusal, 5 CLI preflight failed.

Results are resumable. A stored `result.json` for a reviewer or verifier is reused
only if its prompt hash (system and task prompt), staged-inputs manifest hash,
model, effort and output-schema hash all match the current run. Otherwise the run
stops with `stale stored result <path>: <what changed> ... Re-run with
--no-resume, or delete the result file`, and no model call is made; a result file
written by an older version (no hashes) is refused the same way. Merge several PRs
into one table with:

```
python3 -I "$GRADER/pr_grader.py" table "$OUT/<label1>/grade.json" "$OUT/<label2>/grade.json" --csv "$OUT/table.csv" --md "$OUT/table.md"
```

Useful flags: `--strip-prefix PATH` (repeatable) is a one-off strip pattern;
`--strip-list FILE` is the repo-specific list (below); `--max-ambient-strict N`
aborts if strict terms hit more than N times in the unchanged tree;
`--max-budget-usd` is a per-run safety cap (default 15); `--max-verifications`
caps verified claims per reviewer (default 15, most severe first); `--config-dir`
sets `CLAUDE_CONFIG_DIR` for the reviewers (a neutral account, see "Known residual
leak").

## The headless reviewer invocation

The runner starts each reviewer and verifier as its own `claude -p` process. With
`ID` the ten-letter directory name under the stage root:

```
cd /run/user/<uid>/pgrade/<ID>/cwd          # empty, neutral; PWD is reset to it too
printf '%s' "<task prompt>" | env CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 PWD="$PWD" "$CLAUDE" -p \
  --model opus --effort high \
  --no-session-persistence --disable-slash-commands --restricted \
  --tools Read,Grep,Glob \
  --setting-sources local --strict-mcp-config \
  --settings '{"autoMemoryEnabled":false,"claudeMdExcludes":["**/CLAUDE.md","**/CLAUDE.local.md","**/.claude/rules/**"],"disableAllHooks":true}' \
  --add-dir /run/user/<uid>/pgrade/<ID>/in \
  --max-budget-usd 15 --output-format json \
  --system-prompt "<system prompt text>"
```

Notes learned the hard way:

* `--tools` and `--add-dir` take a variable number of values: never pass the
  task prompt positionally after them. Send it on stdin.
* The neutral working directory must be empty. Run from a directory inside a
  project and the child may load that project's instructions, rules and
  auto-memory. Without `autoMemoryEnabled:false` and the env variable the child
  loaded a project memory index in a probe. The runner also resets `PWD`, which
  the child would otherwise inherit from the parent shell.
* `--restricted` confines the file tools to the working directory and the
  `--add-dir` directory. The preflight probe confirms a read inside the staged
  directory works and a read of a file outside it is refused.
* `--output-format json` returns an event array. The last element has
  `type: "result"` with `usage`, `total_cost_usd`, `modelUsage` and `result`
  (the model's final text). The first element lists the tools, MCP servers,
  skills and model the child actually had.
* A reviewer whose JSON fails the schema is retried once; both attempts are kept.
* The CLI reads its own login credentials from its home configuration. That is
  outside the runner's control and is not an input to the review.

## Blinding rules

Reviewers receive exactly: the issue title and body, the merged diff, and the
repository tree at the merge commit, at a neutral path, plus the filled prompts.
Nothing else from the runner.

Never provided to a reviewer: PR title or body, commit messages, branch name, PR
number, PR comments, issue comments, review comments, plan documents, process
configuration, the output directory path, the repository path, the user name.
Reviewers are not told which working method produced the change, and the prompt
forbids speculating about it.

Stripped from the extracted tree and the diff (path components or basenames):
`.claude`, `.agents`, `.github`, `.githooks`, `.scratch`, `.codex`, `.cursor`,
`.gemini`, `.superpowers`, `.windsurf`, `CLAUDE.md`, `CLAUDE.local.md`,
`AGENTS.md`, `GEMINI.md`, `.mcp.json`, `settings.local.json`, `.claudeignore`,
`skills-lock.json`, `.env` files (not `*.example`), and the root prefixes
`docs/plans`, `docs/superpowers`, `planning`, `plans`, `.scratch`, plus anything
in `--strip-prefix` or the strip list. Paths to plan documents in the issue text
are replaced by `[path removed]`. Symlinks and special files are not extracted.
The staged directory is made read-only.

### Repo-specific strip list

Process and workflow documents differ per repository (workflow guides, skills
references, usage analytics), so they are removed with a list you write per
repository and pass with `--strip-list FILE`. One root-relative path or glob per
line, `#` comments: a plain path is that file or directory tree; `dir/**`
everything below; `*` within one component; `**/name` at any depth. The example
`strip-list.example.txt` is the list for the poc repository (every path checked
present at merge commit `10aaab8b` of that repository):

```
docs/developer-guide/workflow-guide.md
docs/developer-guide/skills-reference.md
DEVELOPMENT_WORKFLOW.md
GETTING_STARTED.md
NEWDEV_GUIDE.md
docs/operations/token-usage-analysis.md
devtools/data/token-analysis/**
```

How to build one for a new repository: stage with an empty list, read
`blinding_scan.ambient.*` in `inputs_manifest.json` (hit counts per term with the
top files), add the files that describe the working method, re-stage, repeat
until the remaining hits are ordinary domain use. `tree.strip_patterns_unmatched`
in the manifest lists patterns that matched nothing (stale or mistyped).

### Blinding scan

Runs on every `stage` and `grade`; a failed scan aborts before any model call.
Terms come in two tiers.

STRICT terms (abort): `Co-Authored-By`, `Claude-Session`, `claude.ai/code`,
"Generated with Claude", the PR number, the branch name and every `--leak-term`,
`check-acs`, `.scratch`, handover file names (`handover*.md` and similar),
plan-file paths (`docs/plans/`, `plans/<year>-...`, `planning/archive/`,
`docs/superpowers`) and `superpowers`.

* Anything authored for this change aborts on a strict hit: the issue text, the
  diff (every line for the trailer terms, added lines for the rest), the filled
  reviewer and verifier prompts, the argv, the stage and working-directory paths,
  and every file and directory name in the staged tree (a file named `handover...`
  aborts wherever it is).
* In unchanged tree content the change-specific identifiers abort too (branch
  name, `--leak-term`, a PR reference such as `#4742`, `PR 4742`, `pull/4742`).
  A bare number equal to the PR number in unchanged code does not (it is counted).
* Other strict terms in unchanged tree content cannot abort by default, because
  real repositories mention them in ordinary documents (ADRs citing plans, build
  files using `.scratch` directories). They are counted per term, with the top
  files, under `blinding_scan.ambient.strict`, and the totals appear in
  `blinding_scan.counts` and `grade.json`. Add the offending process documents to
  the strip list; use `--max-ambient-strict N` to make a residue above N abort.

DOMAIN-AMBIGUOUS terms (never abort): `plan(s)`, `stress-test`, `orchestrat`,
`subagent`, `CLAUDE.md`. Hits in authored content are listed as warnings and
counted (`counts.warn_authored_by_term`); hits in unchanged tree content are
counted (`counts.ambient_domain_ambiguous_by_term`).

In addition the runner checks what the reviewer process is handed that is not
file content, against identifying words: the user name, the home directory name,
`.scratch`, and every non-generic component of the `--out`, repository and
stage-root paths. It scans the filled system and task prompts of a reviewer and
a verifier, the argv (without the executable path, which the model never sees),
the stage and working-directory paths and `PWD`, and repeats the check
immediately before every model call (the verifier's claim text is checked for
the user name and `.scratch` only). A hit refuses the run (exit 3).

Before accepting a run also grep the staged inputs yourself:

```
grep -rEni 'co-authored-by|claude-session|<PR number>|<branch name>' /run/user/<uid>/pgrade/<ID>/in/issue.md /run/user/<uid>/pgrade/<ID>/in/diff.patch
```

Expected: no output.

What each reviewer received is recorded per run in
`$OUT/<label>/runs/reviewer_<i>/received.json`: the full argument vector (system
prompt replaced by its SHA-256), working directory and its entries (must be
empty), `PWD`, staged directory and its top-level entries (`after`, `diff.patch`,
`issue.md`), file count and manifest SHA-256, tools, settings, environment
overrides, the leak-scan result, the input hashes, and SHA-256 of the system
prompt and stdin. The prompt texts themselves are saved beside it
(`system_prompt.txt`, `user_prompt.txt`). `inputs_manifest.json` lists every
staged file with its SHA-256. Reviewers see only those files; to prove it, audit
the tool calls in `attempt<k>.stdout.json` (every `tool_use` path must start with
the staged directory).

### Known residual leak

Claude Code itself attaches the logged-in account's e-mail address to every
session's context (a `userEmail` block). The runner cannot remove it, and it
contains the user name and the organisation's domain. The preflight's context
probe asks a Haiku run what identifying text it can see in its own context and
prints a WARNING naming the user-name term if the CLI injects it. Options: run
the reviewers under a neutral account's configuration (`--config-dir
/abs/path/to/neutral-claude-config`, the `CLAUDE_CONFIG_DIR` of a separate login;
untested here), or accept and record it. It does not reveal which working method
produced the change, but it is not blind to who ran the grader.

## Output

Per PR, under `$OUT/<label>/`: `inputs_manifest.json`, `grade.json`, `row.csv`,
`row.md`, and `runs/` (every prompt, raw output, parsed result, usage).
`grade.json` records the model alias and resolved model id, CLI version and path,
timestamps, wall time per phase, token usage and cost per run and in total, the
blinding counts, and per reviewer and in the aggregate: the grade, the
`assessable_fraction`, `low_confidence`, the number of unresolved claims and the
caps that applied.

Table row: grade (median of the three reviewers after verification), per-reviewer
grades (`a|b|c`), the grades the reviewers gave themselves, verified blocker and
major counts per reviewer, minor findings reported, discarded blocker/major
findings, ACs met per reviewer (`met/total`), **assessable fraction (median)**,
**unresolved claims per reviewer**, **low-confidence flag**, valid reviewer count,
model, CLI version, time. Always read the grade together with the assessable
fraction.

## Verification pass

Every blocker or major finding, and every AC a reviewer marked `partial` or
`not_met`, is given to a separate headless verifier (same restrictions, no access
to the reviewer's reasoning) which must reach `confirmed`, `refuted` or
`unverifiable` by reading the code, and states whether confirming would need
execution. Test containers are not started. Unverified blocker/major findings are
discarded; an unverified `partial`/`not_met` AC becomes `not_assessable`. Every
claim left unresolved (`unverifiable`, a failed verifier run, or over the cap) is
counted as `unresolved_claims` per reviewer and reported; an unresolved
blocker/major finding caps that reviewer's grade at 4 and flags low confidence,
and an unresolved AC lowers the assessable fraction. The grade is recomputed from
verified facts by the deterministic rules in `rubric.md`, not taken from the
reviewer's own number. Claims over the cap count as unresolved.

## Grade anchors (1 to 5)

The grade is the minimum of every cap that applies (`B` verified blockers, `M`
verified majors, `N` not_met ACs, `P` partial ACs); `rubric.md` is the full
specification with definitions and examples.

| cap | applies when |
| --- | --- |
| 1 | `B >= 2`, or `B >= 1` and `N >= 1`, or `N >= 3` |
| 2 | `B == 1` (no `not_met` AC), or `N == 2` (no blocker), or `M >= 3`, or `P >= 2` |
| 3 | `N == 1` (no blocker), or `M == 2`, or `P == 1`, or tests `inadequate` |
| 4 | `M == 1`, or tests `partial`, or `significant` unrequested scope, or `assessable_fraction < 0.8` (or no ACs), or an unresolved blocker/major claim |
| 5 | none of the above |

`assessable_fraction` = ACs judged `met`/`partial`/`not_met` divided by all ACs.
`not_assessable` ACs never count as defects, but a change whose ACs mostly cannot
be judged from source cannot earn a 5: below 0.8 the grade is capped at 4 and
flagged low confidence. Reported minor findings are not verified and never affect
the grade.

## Operating thresholds

* Blinding scan: zero strict hits (authored content, paths, prompts, argv) and
  zero reviewer-input hits, else do not run. Record the ambient strict and
  domain-ambiguous counts with the result.
* Reviewers: three per PR. Accept the row only if at least 2 of 3 returned valid
  output (`n_valid_reviewers` >= 2); otherwise mark the PR ungraded. The grade is
  the median of the valid reviewers.
* Per-run timeout 2400 s and budget cap 15 USD (defaults). A timed-out run is
  retried once, then counts as invalid.
* Report `low_confidence` and `assessable_fraction` with every grade; do not
  compare grades across PRs whose assessable fractions differ widely.
* Reviewer agreement: report the spread (max - min) of per-reviewer grades. A
  spread of 2 or more on a PR means the grade is unreliable for that PR.
* Observed cost for one dry run on a 19-file diff in a 1,400-file repository:
  three reviewers, about 2 to 4 minutes each, about 1.1 to 2.3 USD of API-equivalent
  cost each; a single verifier about 20 seconds and 0.16 USD.

## Calibration gate (do before trusting any grade)

1. Take a set of merged PRs with known later outcomes (a fix PR, revert, reopened
   issue or follow-up bug within a fixed window versus none). Use at least 15 PRs.
2. Grade them all with this runbook, unchanged prompts, same model alias.
3. Report the grade distribution of the two outcome groups, the per-reviewer
   agreement, and a Bayesian posterior (credible interval) for the difference in
   grade between the groups, not a p-value.
4. Decision: if the credible interval for the difference includes zero, or the
   reviewer spread is 2 or more on a third of the PRs, the grader does not
   discriminate. Drop the grade and rely on hard signals.
5. Stability: re-grade at least 3 PRs from scratch (`--no-resume`, new output
   directory) and report the run-to-run grade variation. A median that moves by
   2 or more points between runs on any of them means the grade is too noisy to
   compare close groups.

## Safety: reads and writes

* Source repository: read only. The runner issues `git archive`, `git diff` and
  `git rev-parse`, and `gh issue view` (read). It never checks out, fetches or
  writes in the clone. Verify afterwards with `git -C <clone> status --porcelain`
  (empty) and `git -C <clone> rev-parse HEAD` (unchanged).
* Reviewers and verifiers hold only `Read`, `Grep`, `Glob`, confined by
  `--restricted` to an empty working directory and the staged inputs. They have
  no shell, no write tools, no network tools, no MCP servers, no hooks, no skills.
* The runner writes only below `--out` (run records, results) and the stage root
  (staged inputs and empty working directories; delete
  `/run/user/<uid>/pgrade/<ID>` when finished, it holds a copy of the repository
  tree on tmpfs). `.env` files are stripped from the staged tree; `*.example` files are kept.
* No secrets are read or printed. The runner never reads credentials or
  environment values other than passing its environment to the CLI. Before
  sharing outputs, scan them:

```
grep -rEl 'sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY' "$OUT/<label>"
```

Expected: no output.

## Troubleshooting

* `claude CLI not found`: pass `--claude /absolute/path`.
* "neutral cwd is not empty": delete the stray files in
  `/run/user/<uid>/pgrade/<ID>/cwd` (re-staging recreates it empty).
* "stale stored result": the prompts, staged inputs, model or effort differ from the
  run that wrote the result; regenerate with `--no-resume` (or delete that result).
* `stage root ... contains identifying terms` / exit 3 from the reviewer-input
  check: choose a `--stage-root` free of user, project and arm words.
* Schema failures twice in a row: open `attempt*.stdout.json`; usually the model
  wrapped the JSON in prose or omitted a required field. Re-run that reviewer
  (delete its `result.json`).
* Blinding scan fails on authored content: fix the cause (strip the path, add the
  leak term to the scan, redact the issue text), re-stage, and do not use
  `--ignore-scan` except to investigate.
