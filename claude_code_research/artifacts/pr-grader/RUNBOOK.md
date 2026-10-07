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
| `pr_grader.py` | runner: `stage`, `grade`, `table` sub-commands |
| `rubric.md` | AC statuses, finding severities, test adequacy, 1-5 anchors (inserted into every prompt, and the spec for the grade function) |
| `prompts/reviewer_system.txt`, `prompts/reviewer_task.txt` | identical reviewer prompt for every run |
| `prompts/verifier_system.txt`, `prompts/verifier_task.txt` | verifier prompt |
| `schemas/review.schema.json`, `schemas/verification.schema.json` | required JSON output of reviewers and verifiers |
| `tests/test_pr_grader.py` | unit tests (no model calls) |

## Prerequisites check

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

Run the unit tests first (they make no model calls and write only under
`PR_GRADER_TMP`):

```
PR_GRADER_TMP=<scratch dir> python3 -I tests/test_pr_grader.py
```

Expected: `OK` with no failures.

## Inputs

* a local clone of the repository (only read: `git archive`, `git diff`,
  `git rev-parse`; the clone is never checked out, modified or fetched);
* the merge commit of the PR (for a squash merge, the squash commit; the diff is
  taken against its first parent);
* the linked issue (`--gh-repo owner/name --issue N`, or `--issue-file path`
  whose first line is the title and the rest the body);
* an output directory, the only place the runner writes. Choose a neutral path:
  reviewers see the absolute path of the staged inputs, so do not put PR
  numbers, branch names or arm names in any directory name. `--label` is only
  an output sub-directory name and is never shown to reviewers.

## Run

Stage and scan only (no model call; do this first and read the result):

```
python3 -I pr_grader.py stage \
  --repo-path /abs/path/to/clone --merge-commit <sha> --label <label> \
  --gh-repo owner/name --issue <N> \
  --pr-number <PR> --leak-term "<branch name>" --leak-term "<any commit-subject phrase>" \
  --out /abs/path/to/output
```

Full grade (stage, three reviewers, verification, aggregate):

```
python3 -I pr_grader.py grade <same arguments> --claude "$CLAUDE" \
  --model opus --effort high --reviewers 3 --parallel 2 --timeout 2400
```

Run it detached and wait with an explicit loop; a grade takes several minutes:

```
nohup python3 -I pr_grader.py grade ... > grade.log 2>&1 &
PID=$!
while kill -0 $PID 2>/dev/null; do sleep 15; done
tail -n 20 grade.log
```

Results are resumable: a stored `result.json` for a reviewer or verifier is
reused unless `--no-resume` is given. Merge several PRs into one table with:

```
python3 -I pr_grader.py table <out>/<label1>/grade.json <out>/<label2>/grade.json --csv table.csv --md table.md
```

Useful flags: `--strip-prefix PATH` (repeatable) removes extra repo-relative
files or directories from the staged tree and diff, for example a process
description document. `--max-budget-usd` is a per-run safety cap (default 15).
`--max-verifications` caps verified claims per reviewer (default 15, most severe
first).

## The headless reviewer invocation

The runner starts each reviewer and verifier as its own `claude -p` process:

```
cd <empty neutral directory>
printf '%s' "<task prompt>" | env CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 "$CLAUDE" -p \
  --model opus --effort high \
  --no-session-persistence --disable-slash-commands --restricted \
  --tools Read,Grep,Glob \
  --setting-sources local --strict-mcp-config \
  --settings '{"autoMemoryEnabled":false,"claudeMdExcludes":["**/CLAUDE.md","**/CLAUDE.local.md","**/.claude/rules/**"],"disableAllHooks":true}' \
  --add-dir <staged inputs directory> \
  --max-budget-usd 15 --output-format json \
  --system-prompt "<system prompt text>"
```

Notes learned the hard way:

* `--tools` and `--add-dir` take a variable number of values: never pass the
  task prompt positionally after them. Send it on stdin.
* The neutral working directory must be empty. Run from a directory inside a
  project and the child may load that project's instructions, rules and
  auto-memory. Without `autoMemoryEnabled:false` and the env variable the child
  loaded a project memory index in a probe.
* `--restricted` confines the file tools to the working directory and the
  `--add-dir` directory. A probe confirmed reads inside the staged directory work
  and a read of a file under the home directory is refused.
* `--output-format json` returns an event array. The last element has
  `type: "result"` with `usage`, `total_cost_usd`, `modelUsage` and `result`
  (the model's final text). The first element lists the tools, MCP servers,
  skills and model the child actually had.
* A reviewer whose JSON fails the schema is retried once; both attempts are kept.
* The CLI reads its own login credentials from its home configuration. That is
  outside the runner's control and is not an input to the review.

## Blinding rules

Reviewers receive exactly: the issue title and body, the merged diff, and the
repository tree at the merge commit. Nothing else.

Never provided to a reviewer: PR title or body, commit messages, branch name, PR
number, PR comments, issue comments, review comments, plan documents, process
configuration. Reviewers are not told which working method produced the change,
and the prompt forbids speculating about it.

Stripped from the extracted tree and the diff (path components or basenames):
`.claude`, `.agents`, `.github`, `.githooks`, `.scratch`, `.codex`, `.cursor`,
`.gemini`, `.superpowers`, `.windsurf`, `CLAUDE.md`, `CLAUDE.local.md`,
`AGENTS.md`, `GEMINI.md`, `.mcp.json`, `settings.local.json`, `.claudeignore`,
`skills-lock.json`, `.env` files (not `*.example`), and the prefixes
`docs/plans`, `docs/superpowers`, `planning`, `plans`, `.scratch`, plus any
`--strip-prefix`. Paths to plan documents in the issue text are replaced by
`[path removed]`. Symlinks and special files are not extracted. The staged
directory is made read-only.

Blinding scan (runs on every `stage` and `grade`; a failed scan aborts before any
model call):

* Hard terms: `Co-Authored-By`, `Claude-Session`, `claude.ai/code`, "Generated
  with Claude", the PR number, and every `--leak-term`. Any hit in the issue, the
  prompts, the diff (any line) or a path name fails the scan.
* Arm terms: `stress-test`, `check-acs`, `orchestrat`, `plan(s)`, `.scratch`,
  `docs/plans`, `superpowers`, `subagent`, `CLAUDE.md`. A hit on a line the
  change added, in the issue or in the prompts fails the scan.
* Hits inside the unchanged post-merge source tree are ambient: they are the same
  for every change in the repository, and text the change itself wrote also
  appears in the diff and is scanned there. They are counted per term and listed
  in `inputs_manifest.json` under `blinding_scan.ambient_tree_hits` for a human to
  judge. If the ambient text still describes a working method (workflow guides,
  skill references), add it with `--strip-prefix` and re-stage.
* Before accepting a run also grep the staged inputs yourself:

```
grep -rEni 'co-authored-by|claude-session|<PR number>|<branch name>' <out>/_stage/<id>/issue.md <out>/_stage/<id>/diff.patch
```

Expected: no output.

What each reviewer received is recorded per run in
`<out>/<label>/runs/reviewer_<i>/received.json`: the full argument vector (system
prompt replaced by its SHA-256), working directory and its entries (must be
empty), staged directory and its top-level entries (`after`, `diff.patch`,
`issue.md`), file count and manifest SHA-256, tools, settings, environment
overrides, and SHA-256 of the system prompt and stdin. The prompt texts
themselves are saved beside it (`system_prompt.txt`, `user_prompt.txt`).
`inputs_manifest.json` lists every staged file with its SHA-256. Reviewers see
only those files; to prove it, audit the tool calls in `attempt<k>.stdout.json`
(every `tool_use` path must start with the staged directory).

## Output

Per PR, under `<out>/<label>/`: `inputs_manifest.json`, `grade.json`, `row.csv`,
`row.md`, and `runs/` (every prompt, raw output, parsed result, usage).
`grade.json` records the model alias and resolved model id, CLI version and path,
timestamps, wall time per phase, and token usage and cost per run and in total.

Table row: grade (median of the three reviewers after verification), per-reviewer
grades (`a|b|c`), the grades the reviewers gave themselves, verified blocker and
major counts per reviewer, minor findings reported, discarded blocker/major
findings, ACs met per reviewer (`met/total`), valid reviewer count, model, CLI
version, time.

## Verification pass

Every blocker or major finding, and every AC a reviewer marked `partial` or
`not_met`, is given to a separate headless verifier (same restrictions, no access
to the reviewer's reasoning) which must reach `confirmed`, `refuted` or
`unverifiable` by reading the code, and states whether confirming would need
execution. Test containers are not started. Unverified blocker/major findings are
discarded; an unverified `partial`/`not_met` AC becomes `not_assessable`. The
grade is then recomputed from verified facts by the deterministic rules in
`rubric.md`, not taken from the reviewer's own number. Claims over the cap are
discarded as unverified.

## Grade anchors (1 to 5)

Lowest applicable result, rules applied in this order:

| grade | anchor |
| --- | --- |
| 1 | any verified blocker, or any AC `not_met` |
| 2 | three or more verified majors, or two or more ACs `partial` |
| 3 | exactly two verified majors, or exactly one AC `partial`, or test adequacy `inadequate` |
| 4 | exactly one verified major, or test adequacy `partial`, or any `significant` unrequested scope |
| 5 | every assessable AC `met`; no blocker; no major; tests `adequate`; no significant unrequested scope. Minor findings do not lower the grade |

`not_assessable` ACs never lower the grade. Reported minor findings are not
verified and never affect the grade.

## Operating thresholds

* Blinding scan: zero hard hits and zero arm hits in authored content, else do
  not run.
* Reviewers: three per PR. Accept the row only if at least 2 of 3 returned valid
  output (`n_valid_reviewers` >= 2); otherwise mark the PR ungraded. The grade is
  the median of the valid reviewers.
* Per-run timeout 2400 s and budget cap 15 USD (defaults). A timed-out run is
  retried once, then counts as invalid.
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
* The runner writes only below `--out` (staged inputs, run records, results).
  `.env` files are stripped from the staged tree; `*.example` files are kept.
* No secrets are read or printed. The runner never reads credentials or
  environment values other than passing its environment to the CLI. Before
  sharing outputs, scan them:

```
grep -rEl 'sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY' <out>/<label>
```

Expected: no output.

## Troubleshooting

* `claude CLI not found`: pass `--claude /absolute/path`.
* "neutral cwd is not empty": delete the stray files in `<out>/_cwd`.
* Schema failures twice in a row: open `attempt*.stdout.json`; usually the model
  wrapped the JSON in prose or omitted a required field. Re-run that reviewer
  (delete its `result.json`).
* Blinding scan fails on authored content: fix the cause (strip the path, add the
  leak term to the scan, redact the issue text), re-stage, and do not use
  `--ignore-scan` except to investigate.
