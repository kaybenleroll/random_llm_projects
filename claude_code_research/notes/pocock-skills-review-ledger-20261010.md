# Pocock skills review: decision ledger (2026-10-10)

Upstream: `mattpocock/skills` at `49dd158`. Fifth review. Earlier passes: 2026-08-03, 2026-08-07/08, 2026-08-22, follow-ups 2026-09-13 and 2026-09-24.
Verdicts are present-tense (see Principle). Issues are in `kaybenleroll/dotfiles` unless stated.

## 1. Principle (stated by the user, 2026-10-10)

Judge every candidate on present-tense merit. Past decisions, "parked", "never built" and low past usage are not reasons to skip. A past decision counts only if its stated reason is re-verified true now.

The earlier "evidence bar" (act only on verified defects) and "prompt-level before skill-level" principles were the assistant's own proposals. They are retired as vetoes: both turned absence of an observed failure into a reason not to act.

Self-audit of the earlier drops: 17 of 23 rested wholly or partly on history. Two also rested on technical claims that are no longer true:

| Dropped item | Stated reason | Why stale |
|---|---|---|
| `claude --bg` fork (claude-handoff) | "ask hooks fail closed headless" (dotfiles#76) | #76's mechanism is for `-p` runs with no permission host. `--bg` cannot combine with `-p`; per the agent-view docs a background session blocked on a permission prompt shows "Needs input" and keeps running |
| implement-spec (parallel implementers) | "no worktree/tdd/code-review deps in place" | The Agent tool now accepts `isolation: "worktree"`; background subagents run concurrently |

## 2. Decision table

Verdicts: DO NOW, DO LATER, SKIP, NEEDS DECISION. Value/cost: benefit H/M/L, cost XS/S/M/L. "Unfiled" means no issue yet.

### 2a. Upstream skills

| Candidate | Verdict | Present-tense reason | Value / cost | Issue | Revisit (skips) |
|---|---|---|---|---|---|
| tdd as user-invoked reference skill, wired by path into implementer prompts | DO NOW | Implementer prompts carry ad hoc test-first wording with no anti-pattern list (M2). Seams: from issue/PRD, else highest existing seam, assumption logged (upstream's confirm-with-user gate fails unattended) | M / S | kaybenleroll/dotfiles#317 | |
| write-a-prd seam sketch + prototype-snippet exception; new-feature Phase 9 test block (as path reference); implement's "single test files often, full suite once" | DO NOW | Seam source for implementers; folded into the tdd issue (split if the plan passes four files) | M / S | kaybenleroll/dotfiles#317 | |
| poc_planning_tool `kompreno-issue-sop` test-first line | DO NOW | Currently 0 test-first hits; add after the tdd skill exists (PR in poc_planning_tool) | L / XS | after kaybenleroll/dotfiles#317 | |
| diagnose: red-capable gate, Minimise step, Redact, mutation diff | DO NOW | Phase 5 consumes a "minimised repro" that no phase produces; skill asks for HAR/log dumps, so Redact matters | M / S | kaybenleroll/dotfiles#318 | |
| reflect: mechanical (hook candidate) vs judgement (rule text); "no guardrail is a finding" | DO NOW | Reflect (78 invocations) can only emit rule text; mechanical rules sit as CLAUDE.md bullets costing context every turn | M-H / S-M | kaybenleroll/dotfiles#319 | |
| wizard `template.sh` sync (0600 `.env`, quoting, EOF) | DO NOW | Verified defects in current template | M / S | kaybenleroll/dotfiles#313 | |
| code-review-two-axis: merge-base diff, non-empty preflight, ordered spec search | DO NOW | Verified correctness fault (HEAD~1 default) | L / XS | kaybenleroll/dotfiles#314 | |
| code-review-two-axis flip to user-invoked | DO NOW | 1 use vs 31 for built-in `/code-review`; redundant with check-acs; model-invoked listing cost every turn | L-M / XS | kaybenleroll/dotfiles#312 | |
| wait-what (`/wait-what`, degrades without `docs/CONTEXT.md`) | DO NOW | On-demand re-pitch when a terse answer or coined label did not land; zero ongoing cost | L / XS | kaybenleroll/dotfiles#320 | |
| to-questionnaire | DO NOW | Consultancy fit; nothing equivalent; zero ongoing cost | L-M / XS | kaybenleroll/dotfiles#320 | |
| pr: Merge Danger line (door + blast radius) | DO NOW | One-line risk signal for the human merge decision; does not conflict with `validate-pr-body` (closing syntax only) | L-M / XS | kaybenleroll/dotfiles#320 | |
| pr: Evidence / Summary visual | DO NOW (optional wording) | check-acs refuses PR prose as AC evidence, so Evidence is non-load-bearing | L / XS | kaybenleroll/dotfiles#320 | |
| grilling: "yes accepts the recommendation", frontier-empty stop, scenario probing | DO NOW | Cuts ceremony; independent of the batching decision | L-M / XS | unfiled (grill-me edit) | |
| grilling: batch independent questions per round | NEEDS DECISION | Conflicts with SOUL.md line 15 and grill-me step 5; user feedback is split (section 5) | M-H / S | unfiled | |
| trigger: stress-test / new-session body load | DO NOW | stress-test body 51.8 KB loaded 316 times | M / M | kaybenleroll/dotfiles#311 | |
| triage: `.out-of-scope/` declined-concept record | DO NOW | The wayfinder ADR (dotfiles#120) was deleted; reasoning survives only in issue comments. This ledger is the record | M / XS | this note | |
| implement-spec: parallel implementers via `isolation: "worktree"`, per-slice PRs, `.scratch/` exploration notes | DO LATER | Integration branch + merger conflicts with PR-per-issue and check-acs ordering; take only the worktree half, after M3 | M (low conf) / S | unfiled | Filed once M3 is accepted as sufficient |
| claude-handoff: optional `claude --bg` fork in new-session | DO LATER | Stale objection removed (section 1); needs a live `ask`-hook test first | L-M / XS | unfiled | After M4 rerun passes |
| prd-to-issues: context-window sizing, prefactor, wide-refactor expand/migrate/contract | DO LATER | Sizing matches new-session policy; native blocking edges are blocked by the label hook | L-M / XS | unfiled | Next edit of prd-to-issues |
| codebase-design vocabulary, deletion test, two-adapter rule; ica churn scoping and ADR awareness | DO LATER | ica has 0 uses and is being flipped; no standalone skill (listing cost) | L / XS | unfiled | Fold when ica is next touched |
| retro: tool-economy / information-access lenses | DO LATER | Reflect Mode B lacks a cost lens | L-M / S | unfiled | Fold at next reflect edit |
| ask-matt: "/clear when disposable" branch | DO LATER | new-session has no `/clear` branch (`clear` 18 uses, `compact` 28) | L-M / XS | fold into #275 (existing) | |
| prototype: throwaway branch as primary source | DO LATER | 0 uses, being flipped | L / XS | unfiled | Fold when prototype is next touched |
| wayfinder: `[prototype]` node, destination-first, chart-time parallel research | DO LATER | Parallel research now trivial via background subagents | L / XS-S | unfiled | Fold at next wayfinder edit |
| triage: verify-claim-first, redundancy-by-concept | DO LATER | triage-issue never reproduces | L-M / XS-S | unfiled | Fold at next triage-issue edit |
| "It's working if" per-skill checks | DO LATER | write-a-skill has structure checks only | L / XS | unfiled | Fold at next write-a-skill edit |
| superpowers plugin (re-enable) | SKIP | Trigger overlap with grill-me/diagnose/new-feature/write-a-prd; adds ~10 descriptions per turn; only TDD wanted (ported instead) | L / XS | | If a second superpowers skill is wanted |
| handoff (file-based) | SKIP | Covered by new-session | n/a | | |
| code-review: Fowler smell baseline | SKIP | No editable surface with reach: built-in `/code-review` cannot be edited, two-axis has 1 use | L / S | | If two-axis is repositioned |
| grilling: don't block on fact-finding | SKIP | grill-me explore-first is stricter by design | L / XS | | |
| grill-me / grill-with-docs wrappers; ask-matt router; research; implement | SKIP | Covered (grill-me, skill-map + `check_roster`, deep-research, new-feature) | n/a | | |
| diagnosing-bugs `hitl-loop.template.sh` | SKIP | Local prose version has the pause rule upstream lacks | L / S | | |
| ica HTML report; prototype HTML LOGIC branch | SKIP | Terminal-first preference | L / M | | |
| domain-modeling: inline glossary, GLOSSARY-MAP, ADR template | SKIP | Only one repo has `docs/CONTEXT.md`; grill-me defers glossary writes by design | L / XS | | Wider CONTEXT.md adoption |
| wayfinder: map-as-index, child tickets, native blocking | SKIP | `validate-issue-labels.py` requires priority/type/area/effort on every child issue; L effort; no parallel-planning use now | L / L | | If bg sessions start being used for parallel planning |
| chief-of-staff | SKIP | Conflicts with SOUL.md "do not proactively suggest backlog items" | L / M | | |
| loop-me, teach | SKIP | `/loop` and `/schedule` exist; teach is not engineering | L | | |
| git-guardrails-claude-code | SKIP | Blanket push block conflicts with branch + PR flow | n/a | | |
| writing-for-agents | SKIP | Covered; SHA provenance handled under #313 | n/a | | |
| setup-*, migrate-to-shoehorn, scaffold-exercises, writing-beats/fragments/shape | SKIP | Irrelevant to a Python/R/bash, GitHub-only, chezmoi-managed setup | n/a | | |

### 2b. Structural ideas and prior actions

| Candidate | Verdict | Present-tense reason | Value / cost | Issue | Revisit (skips) |
|---|---|---|---|---|---|
| Invocation-convention audit (operative "Call the Skill tool with X"; user-invoked skills never called by skills) | DO NOW | `check_roster` cannot see cross-skill calls; new-feature's `/git-workflow` is one instance. `/verify` is a bundled skill, leave it | L-M / XS | kaybenleroll/dotfiles#314 | |
| Upstream SHA provenance | DO NOW | None recorded for any adapted skill | M / XS | kaybenleroll/dotfiles#313 | |
| claude-api override + flip zero-use skills | DO NOW | No `skillOverrides` key set; 15 of 40 roster skills have zero invocations (name-based count) | M / S | kaybenleroll/dotfiles#312 | |
| Go-ahead friction study (bare `/proceed` after a question) | DO NOW | Largest smoothness lever found; sample result in section 3 | high / S | kaybenleroll/dotfiles#315 | |
| check-acs re-run investigation | NEEDS DECISION | Study found no defect; recommend close with no change (section 5) | L / XS | kaybenleroll/dotfiles#316 | |
| Shared grilling primitive | SKIP | grill-me is called whole; extraction adds a listing entry | L / S | | |
| Plugin install / self-update | SKIP | chezmoi owns `~/.claude/skills`; namespaced duplicates cost listing tokens | L / XS | | |
| GLOSSARY.md rename | SKIP | Local convention is `docs/CONTEXT.md` (adapt text only) | n/a | | |
| SCOPE.md observed-failure bar | SKIP | This is the filter the user rejected for their own backlog | n/a | | |
| reflect Haiku pre-filter | SKIP | 36.5% false-positive rate (2026-08-24 test) still stands; no new signal | L / M | | New signal on capture precision |

Existing triage work (dotfiles#307, #310, #308) is separate and not part of this ledger.

## 3. Evidence summary

| Item | Number | Caveat |
|---|---|---|
| Skill usage, local host | Top: new-session 583, proceed 332, check-acs 322, stress-test 316, grill-me 239. 15 of 40 roster skills have zero invocations | About 3 months retained (earliest 2026-06-28; most stores start mid-July). Counts invocation by name; skills reached only via another skill's text are not counted. Subagent sidecars inflate file counts. Rankings are robust, absolute counts are not |
| Skill usage, s3rbase | proceed 707 vs new-session 409 (steer); `/proceed` slash 704 in 596 sessions | Same retention limits |
| TDD-named invocations | Zero on both hosts | Weak evidence: the skill was culled before the retention window. A project `tdd` skill existed in poc_planning_tool (added by 2026-04-29, deleted 2026-05-25). TDD is practised inline in prompts: 10 TDD/test-first Agent prompts on s3rbase |
| M2 | 503 implementer dispatches (of 9,186); 20 (4%) carry explicit test-first wording; 393 mention tests only; 90 none | Regex classification of "implementation"; 466 of 503 share a templated opening, so the count is dominated by one boilerplate prefix. Local host only |
| M3 | 116 adjacent implementer-dispatch pairs; 59 are on different identified issues: 49 serial (83%), 10 overlapping. For 46 serial pairs with timings: median 4.5 min of agent run, total about 460 min | Ceiling on wall-clock saving, so a lower bound on serial share and an upper bound on saving: needs issue numbers in both prompts, cannot judge file independence. Local host only |
| M4 | `claude --bg` in a fresh untrusted directory is refused: "Workspace not trusted" | Inconclusive on the real question (does an `ask` hook park the session). `claude --bg --help` launches an idle session instead of printing help (stopped and removed) |
| M6 | 524 of 733 interactive sessions (71.5%) open with a starter-like message (template headings or handover path); median 1,617 chars | The brief's 55% "Working mode:" figure is not in the source file; the 71.5% is the scripted number. October undercounted (newer starter format) |
| #315 | 57 of 120 sampled go-aheads unwarranted (48%, interval [39, 56]); high-confidence unwarranted only 25 of 120 (21%) | Single rater; 22 unclear. Most common unwarranted patterns: next step in agreed sequence (15), reversible write-up after opinion request (14), read-only check offer (11). The 704 `/proceed` count includes 457 sidechain hits (not re-verified here); local: 197 of 330 `/proceed` follow a turn ending in `?` |
| #316 | 55 re-runs sampled over 20 sessions: 46 (84%) are a new PR; 6 (11%) are classifier merge blocks; no defect found | n=20, classified from digests. Raw issue figures (94/45/13/6) no longer match the transcripts |

## 4. Draft: narrow go-ahead rule (from the #315 study; not filed)

"Stated recommendation + reversible + in scope: act and report. Ask only at gates: merge, destructive or outward-facing actions (issue filing, milestones), scope change, genuine fork, security posture."

Confidence: moderate. 48% unwarranted clears the study's 40% threshold, but only 21% do on high-confidence labels alone.

## 5. Open decisions for the user

1. Grilling rule. Batch independent, low-stakes clarifying questions (numbered, each with a recommendation, "yes" accepts) and keep serial for consequential decisions. This edits SOUL.md line 15 and grill-me step 5. Learnings queue holds conflicting feedback: `85bdd219` (2026-06-04, serial for careful decisions, rejected) vs `1dc67694` (2026-10-09, batch remaining questions, pending).
2. File the narrow go-ahead rule issue (section 4)?
3. Close kaybenleroll/dotfiles#316 with no change?
4. Rerun M4 in a trusted directory to test an `ask` hook in a `--bg` session (gates the `--bg` fork).
5. Hosts not yet scanned for skill usage: workhorse-instance, google-demo-apps, sea3r-worker, sea3r-worker-sea3r, wsl-skikk, skikk-thor, kompreno-dev-gcp. Not needed for any verdict above (local and s3rbase agree on the top five and the zero set).
6. Unfiled follow-ups pending the above: grill-me edits (decision 1), parallel implementers, `--bg` fork, prd-to-issues sizing.

## 6. Provenance convention

No upstream SHA was ever recorded for adapted skills, so each review looked like a first look. kaybenleroll/dotfiles#313 starts the convention. Future reviews should diff upstream against `49dd158`.
