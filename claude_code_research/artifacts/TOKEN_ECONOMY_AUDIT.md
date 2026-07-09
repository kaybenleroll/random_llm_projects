# Claude Code Token-Economy Audit Playbook

**What this is:** a self-contained, runnable protocol for auditing how efficiently a Claude Code session/project uses context and tokens. Generated 2026-07-03 via a multi-agent Claude Code research session (five research agents + a synthesis pass over official docs, community sources, and prior findings).

**How to invoke:** drop this file into the target project's `.scratch/` (or anywhere convenient), start a fresh Claude Code session in that project, and say: *"Read and run TOKEN_ECONOMY_AUDIT.md."*

**Staleness warning:** several facts here are version-sensitive (compaction trigger %, context window sizes, plan pricing/limits, model names/pricing). Anything below marked `[community-sourced, unverified]` was not confirmed against official Anthropic docs at generation time. Before trusting version-sensitive numbers, re-verify against current docs — see Appendix B for a research method to do that.

**Ground rule for whoever runs this:** do NOT modify any config (CLAUDE.md, skills, settings.json, hooks) automatically. Run the checks, produce the findings table (Phase 5), and ask before applying any change.

---

## Phase 0: Measurement baseline (do this first, always)

Nothing below is worth acting on until you know the current numbers. Re-run this phase after every fix to confirm impact.

1. **`/context`** — live breakdown of the context window by category (system prompt, system tools, MCP tools, custom agents, memory files, skills, messages, free space, autocompact buffer), e.g. `51k/200k tokens (26%)` per category. Run this on a fresh/typical session before any task work. Record the numbers — this is the baseline every later phase compares against. If the pre-work baseline is already >30-40% of the window, that's a Phase-5 finding by itself.
2. **`/usage`** — session/plan cost and usage. Press `d`/`w` to toggle 24h/7-day view. On Pro/Max/Team/Enterprise it also shows a breakdown by skill/subagent/plugin/MCP-server as % of total — this catches costs invisible in a single `/context` snapshot (e.g. a skill that's cheap per-load but fires 40x/week). `/cost` may exist as a legacy alias in some installed versions; prefer `/usage` if both exist.
3. **`/memory`** — lists every CLAUDE.md / CLAUDE.local.md / rules file actually loaded this session, plus the auto-memory folder location and toggle. If a file isn't listed here, Claude cannot see it — full stop.
4. **`/mcp`** — lists connected MCP servers and status.
5. Check tool-search mode: `echo $ENABLE_TOOL_SEARCH` (unset/`auto`= deferred loading, the default and cheap mode; `false` = full upfront tool-schema loading, expensive). Also check if running via Vertex AI or a non-first-party `ANTHROPIC_BASE_URL` proxy — tool search is off by default in both, meaning MCP tool schemas load in full regardless of server count.
6. **Third-party: `ccusage`** (github.com/ryoppippi/ccusage) — local CLI, parses Claude Code's local JSONL logs, no data leaves the machine. Run once for historical trend data `/usage` alone won't show:
   ```
   npx ccusage@latest daily
   npx ccusage@latest session
   ```
   Use this to answer "has burn been getting worse over time" and to get exact per-session token/cost totals (more reliable than eyeballing `/usage`).
7. Record five baseline numbers for the audit report: (a) startup `/context` baseline, (b) average tokens/session and average cost over last 2-4 weeks from `ccusage`, (c) typical session length (messages) before first compaction, (d) typical subagent spawns per session and model tier used for each, (e) plan tier (Pro/Max 5x/Max 20x/API) — see the sanity table below.

### Tripwire checklist (self-check — each "yes" is a citable finding, not a vibe)

- [ ] Any CLAUDE.md (root, subdirectory, or global) over ~200 lines (see Phase 1 for the authoritative check).
- [ ] Detailed workflow instructions (e.g. "how to run migrations") living in CLAUDE.md instead of a skill.
- [ ] Frequent auto-compaction — multiple compactions in one session, or compaction on simple tasks.
- [ ] 3+ subagents spawned for a task that's really single-file/simple.
- [ ] Subagents returning raw file/command dumps as response text instead of extracted findings.
- [ ] Subagents using Sonnet/Opus for purely mechanical work (read files, run bash, fetch URLs, locate code).
- [ ] MCP servers connected but near-zero usage share in `/usage` over 7 days.
- [ ] CLI tool available (e.g. `gh`) but an MCP equivalent used instead for the same job.
- [ ] No `/clear` between clearly unrelated tasks in the same session.
- [ ] Extended thinking/effort left at default-high for simple tasks (check `/config` or `/effort`).
- [ ] Agent teams (~7x token cost of a standard session — each teammate is a full context window) used for small tasks, or left idle after finishing.
- [ ] Vague, broad prompts observed in transcript history triggering wide exploratory scans.

### Plan/cost sanity check (context for judging whether measured usage is normal)

| Plan | Price/mo | Relative capacity | Reported 5-hr ceiling `[community-sourced]` |
|---|---|---|---|
| Pro | $20 | 1x | ~40-45 messages/5hr |
| Max 5x | $100 | 5x | ~225 messages/5hr |
| Max 20x | $200 | 20x | ~900 messages/5hr |

- Anthropic doubled 5-hour rate limits for Pro/Max/Team/seat Enterprise on 2026-05-06 and removed peak-hours reduction — discount any pre-2026-05 community figures.
- A weekly cap stacks on top of the rolling 5-hour window; hitting the weekly cap is the harder wall.
- Official Anthropic benchmark (API/Enterprise billing): average ~$13/developer/active-day, $150-250/dev/month, 90% of users under $30/active-day. Consistently over $30/day per active developer is worth investigating against the tripwire list above before assuming "just a big project."
- Upgrade signal: Pro→Max 5x when 5-hour resets interrupt valuable work weekly; Max 5x→Max 20x only if Claude Code is core to an all-day workflow and 5x still feels tight.

### A/B methodology (if comparing a proposed fix's actual impact)

Token spend is non-deterministic run-to-run (different exploration paths). To validate a fix isn't just noise:
1. Fix the exact task wording for both variants (verbatim, not paraphrased).
2. Fresh/cleared session per run — no shared prior context.
3. N≥3 runs per variant, not 1 — report median/range, not a single number.
4. Capture via `/context` immediately after task completion, plus `ccusage session` for the exact total.
5. Change one variable at a time (e.g. CLAUDE.md length only — not length + model tier together).
6. Report as a range: "baseline: 3 runs, 45k-62k tokens, 1 compaction in 2/3 → optimized: 3 runs, 28k-35k tokens, 0 compactions."
7. Cross-check correctness alongside token count — a reduction achieved by skipping verification/exploration is not a win.

---

## Phase 1: Fixed-cost audit

Costs paid on every turn regardless of task relevance: CLAUDE.md, skill listings, MCP tool schemas, hooks, permission config.

### 1.1 CLAUDE.md size/structure — the highest-priority single check

CLAUDE.md at every level (`~/.claude/CLAUDE.md`, project root, any subdirectory `CLAUDE.md`) loads into context at session start and stays for the whole session (unless a subdirectory file — see below). Every line is a per-turn tax, confirmed by three independent community sources plus Anthropic's own guidance.

1. Find every CLAUDE.md in scope:
   ```
   find . -iname "CLAUDE.md" -not -path "*/node_modules/*" -not -path "*/.git/*"
   ls -la ~/.claude/CLAUDE.md
   ```
2. Measure size: `find . -iname "CLAUDE.md" -exec wc -l {} \;`. **Flag anything over 200 lines** — Anthropic's own stated ceiling ("Aim to keep CLAUDE.md under 200 lines by including only essentials," `code.claude.com/docs/en/costs`). For a token estimate rather than a line-count proxy, diff `/context` before/after a controlled edit, or use `wc -w` × 1.3 as a rough approximation (~13 tokens/line typical for prose/markdown).
3. **Placement cost, not just size**: starting Claude Code from the repo root loads only the root CLAUDE.md at launch — subdirectory CLAUDE.md files load on demand only when Claude reads/works in that subdirectory. Starting from a subdirectory loads that directory's CLAUDE.md plus every ancestor's. For work scoped to one package/subsystem, **start Claude from that subdirectory**, not the root — cheapest way to keep irrelevant instructions out of context entirely. Verify empirically for your installed version: `cd` into a subdirectory in a fresh session, run `/context`, check what's loaded.
4. Detect duplication/staleness: diff user-global vs project-root CLAUDE.md for repeated rules; grep for references to deleted files/branches/people; look for narrow single-workflow procedures (e.g. a 40-line "how to deploy" block) sitting in root CLAUDE.md that should be a skill instead (skill bodies load on-demand, not every turn — biggest single win when found).
5. A `# Compact instructions` section is legitimate (guides `/compact` behavior) — don't flag as bloat.
6. Report: table of file path → line count → flagged Y/N (>200) → notes (duplication / staleness / skill-extraction candidates).

### 1.2 Skill trigger audit

Mechanic: every skill's `name` + `description` (+ `when_to_use`, capped at 1,536 combined characters) is listed in context at session start for every discoverable skill (user, project, plugin) — paid regardless of whether it fires. Skill *count* drives this cost, not trigger breadth. The skill *body* only loads on invocation, then **stays resident for the rest of the session**. So the real risk of an over-broad trigger is: (a) it fires on tasks it shouldn't, permanently bloating context for the session, and (b) skill count inflates the always-on listing tax.

1. Enumerate: `find . ~/.claude -path "*/skills/*/SKILL.md" 2>/dev/null`. For each, check combined `description`+`when_to_use` length against the 1,536-char cap — near/over means the listing gets truncated (causes both under- and confused over-triggering).
2. Count total discoverable skills (user+project+plugin). No official ceiling, but treat >30-40 as worth a deliberate audit relative to how many actually get used per `/usage`.
3. Manual over-broad test on each description: does it use generic verbs/nouns matching a huge fraction of ordinary requests ("use when writing code") vs specific trigger phrases? Cross-check against `/usage` invocation frequency — disproportionately high invocation vs narrow apparent purpose = description too broad.
4. Check `disable-model-invocation: true` is set on any skill meant to be manual-only (`/skill-name` invoke only) — missing this on a manual-only skill is a bug, flag it.
5. For skills that DO trigger often (per `/usage`): `wc -l` the SKILL.md, flag bodies >150-200 lines paired with high frequency as the highest-value trims (official guidance: "keep the body concise, every line is a recurring cost once loaded").
6. Report: table of skill → description length vs cap → invocation frequency → verdict (fine / over-broad / missing disable-model-invocation / body too long for its frequency).

### 1.3 MCP server tool-loading audit

Claude Code defaults to **tool search** (deferred loading): only tool names + server instructions load at start; full schemas load on demand. Verify mode first (Phase 0 step 5) — it changes what "cost" means here.

1. `/mcp` for connected servers and status.
2. For each, check server-instructions length — Claude Code truncates server instructions and individual tool descriptions at 2KB each; bloated/missing instructions hurt Claude's ability to know *when* to search for that server's tools.
3. Cross-reference `/usage` per-server share (24h/7d) against `/mcp`'s list. Near-zero usage over 7 days = disable candidate. Cost of an unused server is small when tool search is ON (name+instructions only) but can be substantial (real-world reports: 15-40K+ tokens) when tool search is OFF (Vertex/proxy/`ENABLE_TOOL_SEARCH=false`).
4. Prefer CLI tools over MCP where both exist for the same job (`gh` CLI vs a GitHub MCP server) — CLI adds zero standing tool-listing cost.
5. Report: table of server → connected Y/N → tool-search-mode active Y/N → 7-day usage share → recommendation (keep/disable/investigate).

### 1.4 Hooks overhead audit

Hooks are **not** a standing context-window cost — the script itself isn't loaded into model context. Overhead is: (a) latency (subprocess spawn per matching call), (b) indirect token cost only if the hook's *output* is injected back into context (e.g. `additionalContext`). A hook that filters/summarizes output before Claude sees it (e.g. grepping a log for `ERROR`) *reduces* net tokens — documented good pattern, not a cost source.

1. Enumerate: `find . ~/.claude -iname "settings*.json" -exec jq '.hooks' {} \;`
2. For each hook: does its output surface into the transcript (vs affecting only permission/side-effects silently)? Flag any hook emitting large stdout without `head`/`grep`/`jq` truncation.
3. Check matcher breadth — an overly broad matcher (`"matcher": "*"`) fires on every tool call, multiplying latency even if each call is cheap. Narrow to the specific tool(s) needed.
4. Report: table of hook event → matcher → command → injects output into context Y/N → broad-matcher latency risk Y/N.

### 1.5 Permission allowlist audit — low priority

`settings.json` allow/deny lists are enforced by the CLI engine, not injected verbatim into context every turn — negligible token cost. Sanity check only:
1. `find . ~/.claude -iname "settings*.json" -exec jq '.permissions.allow | length, .permissions.deny | length' {} \;` — hundreds of entries is a maintainability concern, not a token-economy one.
2. Overly narrow rules cause more permission-prompt interruptions (wall-clock/UX cost, not context tax) — don't report as a token-savings item unless the file is absurdly large or malformed.

### 1.6 Other fixed-cost sources

1. **Base system prompt + built-in tools**: ~18K-token fixed baseline, cached, identical every turn — not actionable, but the floor `/context` will never show below.
2. **Bundled skills** (`/code-review`, `/batch`, `/debug`, `/loop`, etc.) are always available unless `disableBundledSkills` is set — check `settings.json`; disable if the project doesn't use these workflows, to trim the always-on listing.
3. **Subagent/plugin preloads**: any custom subagent definition (`.claude/agents/*.md`) with a `skills:` frontmatter field preloads those skill bodies at spawn — verify each is actually needed, not copy-paste leftover.
4. **Background usage** (conversation summarization for `--resume`, idle status checks): typically under $0.04/session — not worth auditing further.
5. **Extended thinking / effort**: billed as output tokens every response by default. Confirm via `/config`/`/effort` whether left at high effort on a project that only needs simple edits — flag if egregious (full treatment in Phase 3).

### Phase 1 priority order (highest token-per-fix-effort first)

1. Trim/relocate root and global CLAUDE.md over 200 lines.
2. Disable unused MCP servers (Phase 1.3), especially with tool search off.
3. Narrow/fix over-broad skill descriptions with high invocation but low relevance.
4. Everything else (hooks, permissions, bundled skills) — verify but expect small returns.

---

## Phase 2: Context, compaction, and memory strategy

### 2.1 Compaction mechanics — exact behavior

**Trigger**: Claude Code auto-compacts as you approach the context limit, running the same summarization as manual `/compact`. Official docs describe this qualitatively without a published universal percentage. `[community-sourced, unverified]`: threshold around 83.5% of the window (up from ~77-78% in older versions), with an undocumented `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` env var (1-100) to tune it. Confirm against your installed version via `/context` if precision matters.

**What a compaction pass does**: replaces conversation history with a structured summary explicitly preserving: your requests/intent, key technical concepts, files examined/modified with important snippets, errors and fixes, pending tasks, current work state. Full tool outputs/intermediate reasoning are discarded.

**What survives vs is lost (official)**:

| Mechanism | After compaction |
|---|---|
| System prompt, output style | Unchanged — not part of message history |
| Project-root CLAUDE.md, unscoped rules | Re-injected from disk |
| Auto memory (MEMORY.md) | Re-injected from disk |
| Rules with `paths:` frontmatter (path-scoped) | **Lost** until a matching file is read again |
| Nested subdirectory CLAUDE.md | **Lost** until a file there is read again |
| Invoked skill bodies | Re-injected, capped 5,000 tokens/skill, 25,000 total; oldest dropped first, truncation keeps the *start* |
| Skill descriptions (the index) | **Not** re-injected — only invoked skills survive |
| Hooks | N/A — code, not context |

Practical implication: deep in a subsystem via a nested/path-scoped rule, compaction silently drops that context until Claude next touches that subsystem. If a rule must be load-bearing all session regardless of files touched, drop its `paths:` frontmatter or move it to root CLAUDE.md.

**Detecting a compacted session**: CLI shows "Conversation compacted" at the moment it happens. Retrospectively: `/context` shows history as one dense summary block; `/memory` still lists the same files (they reload) but subsystem-specific rules/nested CLAUDE.md will be visibly missing until re-triggered.

**Pre-compaction checkpointing**: write down any decision/constraint/plan detail living only in conversation (not in a file) to a scratch markdown or CLAUDE.md/notes before it's at risk. For cross-subsystem work, **save the plan to a file before editing** — official guidance for long cross-package changes. Run `/compact focus on <thing>` proactively before a large new subtask rather than waiting for auto-compact to guess priorities.

**Compact-early refinement** `[community-sourced, converges across 2 independent sources]`: practitioners report compacting earlier (e.g. self-imposed at 70%, or 50% for "noisy" workflows via the unverified env var above) produces a cleaner, less lossy summary than compacting under pressure at the ceiling — corroborated independently without the env var by guidance to "compact while still healthy, not when warnings appear." Treat "compact at your own chosen checkpoint, well before forced" as a safe low-risk adoption; treat the specific env var as unverified until checked against your installed version's docs.

### 2.2 `/clear` vs manual `/compact` vs auto-compact — decision rule

- **`/clear`**: switching to genuinely unrelated work. Default to this between unrelated tasks rather than letting context accumulate "just in case."
- **Manual `/compact [focus]`**: before a long new task in the *same* subsystem/session, when you want continuity but the transcript is heavy. Always prefer `/compact focus on <X>` over the bare form when you know what matters — it steers what the summary keeps.
- **Auto-compact**: acceptable as a safety net, not a strategy — it fires late and without your priorities. Multiple auto-compactions in one session signals the task was sized wrong for one window (see §2.4), not that compaction itself is failing.
- Auto-compact is not free: it's a full summarization pass (billed as an extra generation) with a lossy result — subsequent turns may re-read/re-derive facts that were compacted away. Relying on it also means running "hot" near the ceiling for long stretches, which degrades cache-hit rate (a soon-to-be-invalidated transcript, see Phase 4).

### 2.3 Memory system — MEMORY.md (auto memory) vs CLAUDE.md vs notes dirs

| | CLAUDE.md | Auto memory (MEMORY.md) |
|---|---|---|
| Who writes it | You | Claude, automatically |
| Contents | Instructions/rules | Learnings/patterns Claude discovered |
| Loaded | In full every session (target <200 lines, see Phase 1.1) | First 200 lines OR 25KB (whichever hits first); topic files loaded on demand only |
| Storage | In-repo or user/global | `~/.claude/projects/<project>/memory/` — machine-local, keyed to git repo (shared across worktrees, not machines) |

Deciding what to persist:
- **CLAUDE.md**: build/test commands, architecture facts, naming conventions, "always do X" rules a new teammate would also need.
- **Auto memory / a project notes dir**: debugging insights, build quirks, one-off gotchas that would save re-discovery — only if genuinely reusable, don't let it accumulate one-off noise.
- **Drop entirely**: anything task-specific to one completed piece of work with no recurrence value.

**The bigger lever**: information written to memory persists *outside* the token-billed context — it costs tokens only when loaded (typically once, at session start), not on every turn of a growing transcript. A decision made early in a session that's still relevant 75 turns later either (a) survives uncompacted in-transcript the whole time (paid every turn, at risk of lossy summarization) or (b) gets written to memory once and dropped from active reasoning, reloaded cheaply later. Promote durable facts out of the live transcript proactively, within a session — don't wait for a memory-write to happen only at session end.

Audit steps:
1. `/memory` → check `MEMORY.md` size (near 200 lines/25KB? well-triaged into topic files, or bloated with one-off notes?).
2. Check project CLAUDE.md line count (cross-ref Phase 1.1) — if >200 lines, recommend splitting into path-scoped `.claude/rules/*.md` or per-subsystem CLAUDE.md.
3. Confirm auto memory is enabled (`autoMemoryEnabled` not false) if the project is large/long-running — disabled here is a missed lever.

`[community-sourced, strong corroboration]`: a 61-comment GitHub feature request ("Persistent Memory Across Context Compactions") documents a user who logged 59 compactions across 26 days of heavy use, found no built-in persistent-memory mechanism, and hand-built a 3-tier system (always-loaded `MEMORY.md` <~100 lines, on-demand topic files, a large synced vault) plus a compaction-watcher script — independent real-world validation that writing durable facts to memory before compaction forces them out beats trusting compaction to preserve them.

### 2.4 Session/task decomposition — sizing work to avoid needing compaction at all

The cheapest compaction is the one that never fires because the task fit in one window.

- Delegate open-ended research/exploration to subagents — a subagent's file reads never touch the main budget; only its distilled response does (full mechanics in Phase 3).
- Scope a task to what actually needs shared context — start from the relevant subdirectory (§2.5) rather than repo root if the change is genuinely local.
- For cross-subsystem changes: keep synthesis in the main thread but hand subagents pre-scoped reads/edits per subsystem, rather than dumping every file into main context.
- Write the plan to a file before large edits begin — makes the unit of work resumable across compaction or a session restart.
- **Sizing heuristic**: if you can't state the task's file/subsystem footprint in one sentence before starting, it's probably too large for one window — split into sequential sessions with a checkpoint file, or parallel subagent-scoped chunks reporting to a coordinator.

### 2.5 Monorepo / many-subsystem guidance

- **Where you start Claude matters most.** Repo root → only root CLAUDE.md loads at launch (subdirectory files load on demand). Subdirectory → that dir's CLAUDE.md plus every ancestor's, file access scoped to that subtree. For subsystem-scoped work, start from that subdirectory.
- **Layer CLAUDE.md by directory**: root for repo-wide rules, one per subsystem for stack-specific conventions, each area's owner maintains their own.
- **`claudeMdExcludes`** setting (`.claude/settings.json`/`.local.json`): exclude other teams'/legacy/vendored subsystem CLAUDE.md by glob so they never load even if files there are read.
- **Path-scoped `.claude/rules/*.md`** (`paths:` frontmatter) for centrally-located instructions firing only for matching files anywhere in the tree, vs per-directory CLAUDE.md for owner-maintained local convention. Remember: path-scoped rules do **not** survive compaction (§2.1) — if something must persist regardless of files touched, put it in root CLAUDE.md instead.
- **Per-directory skills** (`.claude/skills/` inside a subsystem) load on demand, keeping subsystem tooling knowledge out of context during unrelated work — but starting from repo root can accumulate skills from every subsystem touched in the session into the hundreds, and descriptions get truncated when there are many (stripping keywords Claude needs to pick correctly). Prefer subdirectory starts, or `disable-model-invocation: true` + explicit slash-invocation for skills with side effects.
- **`Read` deny rules** in `permissions.deny` for generated/vendored code (`dist/`, `build/`, `*.generated.*`, `vendor/`) — stops Claude opening these even when grep surfaces them.
- **Code intelligence / language-server plugins** reduce file-read volume needed just to locate a symbol's definition/callers vs grep-scanning a large tree.
- **`worktree.sparsePaths`**: when spawning subagents into worktrees for parallel subsystem work, sparse-checkout only the directories that subagent needs.

Audit steps: (1) per-subsystem CLAUDE.md files present, or one overloaded root file? (2) `claudeMdExcludes` present if clearly-irrelevant subtrees exist? (3) `.claude/rules/` exists and uses `paths:` scoping appropriately (unscoped rules that only apply to one file type leak tokens every session for every file type)? (4) sessions typically started root vs relevant subdirectory (observe/ask — not visible from config alone)? (5) `Read` deny rules covering generated/vendored paths?

### Phase 2 summary checklist

1. `/context` + `/memory` at session start.
2. Repo root or scoped subdirectory? Prefer the latter for subsystem work.
3. Delegate multi-file exploration to a subagent, not the main thread.
4. Write the plan to a file before large/cross-subsystem edits.
5. `/clear` between unrelated tasks.
6. `/compact focus on <X>` proactively before a long new task in the same session, rather than waiting.
7. After any compaction: assume path-scoped rules and nested CLAUDE.md are gone until re-triggered.
8. Periodically re-check CLAUDE.md line counts and MEMORY.md size/triage quality.

---

## Phase 3: Orchestration patterns review

### 3.1 Fan-out vs single-agent sequential — decision rule

Fan-out (parallel subagents) is worth it only when **all** hold:
- Subtasks are independent (none needs another's output to start).
- Subtask exploration costs don't significantly overlap (overlap = redundant spend, §3.3).
- The work doesn't need one coherent mental model across all pieces ("audit these 12 independent modules for the same bug pattern" → fan-out is fine; "understand how auth flows through the system to refactor it" → single sequential agent, because the model must hold the whole picture).

Scale changes the calculus: at small scale, fan-out's fixed overhead (spawn cost, prompt duplication, response aggregation) usually exceeds the savings. At large scale (dozens-hundreds of files/subsystems), a single sequential agent hits context pressure and starts forgetting/truncating — fan-out becomes necessary, not just efficient, once total exploration surface exceeds one window with reasoning room left.

**Note on token cost specifically (not just wall-clock)**: parallel fan-out does not reduce total token spend vs sequential — each subagent still independently re-derives context and returns response text to the parent; N parallel ≈ N sequential in tokens, and the parent holds N response payloads simultaneously rather than one-at-a-time-discarding. For pure token minimization, sequential-with-synthesis-between-calls can be cheaper. Fan-out's real win is wall-clock and/or main-thread context hygiene (keeping N raw explorations out of the main thread) — not token savings per se. Default to a **single capable agent doing more** unless the task genuinely decomposes into independent units, or unless keeping the main thread clean is itself worth the delegation overhead (this is often the dominant real reason to delegate).

Audit step: before fan-out, write down the file/directory partition each subagent will own. >~20% overlap between two partitions → shrink scope or merge into one agent.

### 3.2 Model tiering

Baseline (assumed already codified elsewhere, reaffirmed here): mechanical/read-only → cheapest tier (e.g. Haiku); reasoning/synthesis → mid tier (e.g. Sonnet); heaviest architectural reasoning → top tier (e.g. Opus), explicit escalation only, never inherited by default.

Large-codebase refinements:
- **"Locate the right file/symbol among thousands" is always the cheapest/mechanical tier**, regardless of how conceptually tangled the codebase seems — locating is pattern-matching, not judgment. Exception: if locating requires disambiguating between multiple plausible candidates via business-logic tracing (e.g. "which of these 6 files implementing `process()` is wired into the payment path"), that's reasoning-tier work wearing a location-task costume.
- A single cheap-tier search call may lack the attention budget for a truly huge repo in one pass — widen *search breadth* (§3.4), don't upgrade the model tier. These are separate levers; "the repo is big" ≠ "this needs a smarter model."
- Top-tier (Opus-equivalent) escalation should scale with *architectural blast radius*, not codebase line count. A 5-file change touching a shared auth abstraction used repo-wide warrants escalation; a 200-file mechanical rename does not, however large the diff.
- Cheapest-tier models are commonly capable of more "medium" synthesis work than typically routed to them — simple classification, short-answer extraction, single-file style-only review are good candidates to push down a tier.
- Sanity-check any hardcoded model aliases resolve to the current/best point release in that tier, not a stale pinned older alias (older aliases usually remain functional but are strictly dominated).

### 3.3 Avoiding redundant context re-derivation

The single biggest waste at scale: multiple subagents in one session re-exploring the same subsystem from scratch. Techniques, in order of preference:

1. **Maintain a shared manifest** (e.g. `.scratch/explored-manifest.md`), updated by the orchestrator after every subagent returns: file/dir path, one-line finding, which subagent found it, timestamp. Before spawning an overlapping subagent, grep the manifest and inline relevant findings directly into the new prompt.
2. **Inline short prior findings directly** — never say "see the manifest" for something short (a path, a signature, a one-line fact); only point to a file for large structured data needing repeated consultation.
3. **Partition before spawning, not after** — decide subsystem ownership up front so overlap is designed out.
4. **Reuse a completed subagent for follow-ups on the same subsystem** (resume via its agent ID/name) rather than spawning fresh and re-exploring from zero — the largest lever for iterative back-and-forth in a large codebase.
5. Periodically scan subagent outputs for near-duplicate "I explored X and found Y" statements across different subagents — a sign the manifest technique wasn't applied.

`[community-sourced]`: independently corroborated — a developer-reported failure mode where "subagents often re-read the same files and rebuild the same context from scratch," severe enough that one built a file-overlap tracker to route new work to an existing subagent rather than spinning up a fresh one. Confirms this applies *between sibling subagents*, not just main-thread-vs-subagent.

### 3.4 Search-breadth settings (if your Explore-style tool supports a thoroughness parameter)

Typical levels: quick / medium / very thorough.
- **quick** — single targeted lookup, you already know roughly where the answer lives. Lowest cost, default unless you have a reason to widen.
- **medium** — multiple related locations, default for most queries where you know the subsystem but not the exact file.
- **very thorough** — comprehensive search across unusual places/naming conventions, slower and costlier. Reserve for: first exploratory pass in an unfamiliar large codebase with no prior signal on conventions; a quick/medium pass already came back empty/ambiguous and a wrong "not found" is costly (e.g. security audits); codebases with inconsistent/legacy naming.

Audit step: never default to "very thorough" as a first move just because the repo is large — try quick/medium first, escalate only after a documented miss.

### 3.5 Isolation mode (worktree) — cost/benefit

Isolation gives a subagent its own repo copy on a new branch; auto-cleans if no changes made; path/branch returned if changes exist. It does not reduce token usage directly — the cost is an extra git operation, and if it *does* produce changes, reconciliation/merging is an out-of-band human cost the token lens doesn't capture.

Worth it when: multiple subagents edit concurrently with any real chance their edit sets collide (insurance against a wrong partition-boundary assumption); the work is exploratory/speculative and might be discarded; a large mechanical migration benefits from per-unit isolation before merging.

Not worth it when: a single subagent works sequentially in the main tree with no concurrent editors; read-only research/location tasks — no edits happen, isolation is pure overhead.

Rule of thumb: isolation cost is roughly fixed; correctness benefit scales with (concurrent editing subagents) × (probability of file-set overlap). Skip at small scale with hand-verified disjoint partitions; default on for anything that writes at scale (many parallel editors, or a large fan-out orchestration).

### 3.6 Effort-level tuning — a lever distinct from model choice

Effort (`low`/`medium`/`high`/`xhigh` where available) is a *behavioral* signal — how much the model thinks — not an externally enforced token cap; at low effort the model still reasons on genuinely hard problems, just less.

- Effort and search breadth (§3.4) are independent axes — a "very thorough" search should still run at low effort (still mechanical pattern-matching over a wider area, not deeper per-item reasoning).
- Dropping effort from high→medium on a bounded mid-tier-model task often cuts token spend more than dropping a model tier — effort directly controls thinking-token volume, tool-call consolidation, and preamble verbosity, three of the largest invisible cost centers in agentic loops. Tasks that are bounded *and* mechanical-adjacent (e.g. "apply this exact diff pattern to 5 files") should use low effort even on a reasoning-tier model.
- A top-effort/auto-orchestration session mode (if your installation has one) multiplies token cost across every task in the session — treat as a deliberate, bounded, temporary escalation, not a default "large codebase" setting; drop back down once the bounded task is done.

### 3.7 Subagent response minimization — the compounding lever

Subagent *response text* (not its internal tool calls) becomes main-thread input tokens, permanently, for the rest of the session. This compounds with subagent count.

- Write full findings to a `.scratch/` file; have the subagent return only the file path plus a 2-3 sentence summary.
- For location tasks: return `path:line`, never the surrounding code block, unless the exact text is load-bearing for the next step.
- For multi-file audits: each subagent appends one line to a shared results file rather than returning its finding in response text; the orchestrator reads the aggregate once at the end.
- Don't spawn a subagent to answer something already fully specified in current context (e.g. re-deriving a fact already in memory or already stated) — the subagent's context-building costs more than reusing what's already available.
- A task resolvable in 1-2 tool calls is nearly always cheaper done directly (by whichever agent already has the necessary context loaded) than spun out to a fresh agent that must re-establish that context from scratch.

### 3.8 Multi-agent workflow/pipeline tooling — cost model (if your installation has one)

If your Claude Code setup supports a scripted multi-agent workflow primitive (a script orchestrating many `agent()` calls via `parallel()`/`pipeline()` outside the conversation, with intermediate results held in script variables rather than the main context):

- `parallel(thunks)` is a barrier — waits for all before returning; use when downstream steps need every result before proceeding.
- `pipeline(items, ...stages)` has no barrier — item A can be in stage 3 while item B is in stage 1; use when items process independently through stages, reducing wall-clock and avoiding holding a full batch's stage-1 outputs simultaneously.
- Concurrency and total-agent caps are typically hard runtime limits (e.g. a documented cap around ~16 concurrent, ~1,000 total per run in some installations) — plan large fan-outs assuming throttled batches, not unlimited concurrency.
- **This is not automatically token-cheaper than manual subagent spawning** — a single run can use meaningfully more tokens than working through the same task in conversation, since total spend is bounded by agent-count × per-agent-cost, not by the concurrency cap. Pilot on a small slice (one directory, not the whole repo) before committing to a full run; use any per-agent token-total view to catch a runaway pattern early; most such tools let you stop mid-run without losing completed-agent results.
- Prefer this primitive over ad hoc fan-out specifically when task count exceeds what one conversation turn can coordinate (roughly dozens-to-hundreds of agents) — below that, plain subagent calls are cheaper since the runtime/script overhead isn't justified.
- Every agent spawned this way typically inherits the session's default model unless explicitly routed otherwise — explicitly route mechanical stages (file discovery, per-file audits with no judgment) to a cheaper model tier rather than letting everything inherit the session default.
- If it supports an explicit token budget for the run, set one for anything with unbounded/uncertain fan-out shape (e.g. "process every file matching X") rather than letting it discover full scope mid-run.

### Phase 3 quick checklist

1. Partitionable into independent units? No → single sequential agent. Yes → 2.
2. Unit count > ~5-8 (a turn's practical coordination limit)? Yes → consider a scripted workflow tool if available, not manual fan-out. No → manual calls, parallel where independent.
3. Per unit: mechanical (locate/match/run-command) or judgment-requiring? → cheapest tier/low effort vs reasoning tier/medium-high, accordingly. Codebase size alone never pushes model tier up for a mechanical task.
4. Any two units write overlapping files? Yes/uncertain → isolation mode on the writers.
5. Check any explored-manifest / prior-findings record before spawning; inline relevant ones.
6. Every subagent writes full output to a file, returns only path + short summary.
7. If using a scripted workflow tool: pilot small, check per-agent token totals before scaling to the full repo.

---

## Phase 4: Caching and output hygiene audit

### 4.1 Prompt caching mechanics — what to know before auditing

- **Caching is a prefix match.** A cache breakpoint caches everything from the start of the prompt up to that point. Any byte change anywhere *before* a breakpoint invalidates it and everything after.
- **Render order is fixed: tools → system → messages.** Tool definitions render first — if the tool set changes (MCP server connects/disconnects, a skill enabling a new tool), the entire cache invalidates, including the system prompt.
- **Minimum cacheable prefix is model-dependent** (roughly 1024–4096 tokens depending on tier). Below that, cache-write tokens stay 0 with no error — it silently just doesn't cache. Rarely actionable (CLAUDE.md+skills are usually well above this) but worth knowing if a project's CLAUDE.md is very short.
- **Session-varying tool sets break caching.** MCP servers connecting/disconnecting mid-session, or a skill invocation changing declared tools, invalidates the tool-list prefix and everything downstream for that turn.
- **Economics**: cache writes cost ~1.25x (5min TTL) or ~2x (1h TTL) of base input price; cache reads cost ~0.1x. A single-shot session gets no benefit — payoff comes from repeated turns/subagent calls reusing the same stable prefix.
- Editing config files (CLAUDE.md/skills) mid-session invalidates the cache for the rest of that session — the next turn pays full price for the entire accumulated context. Batch such edits at session boundaries rather than mid-session if the session will continue for many more turns.

### 4.2 Checking actual cache-hit behavior

Claude Code doesn't expose `cache_read_input_tokens`/`cache_creation_input_tokens` in a documented UI panel directly, but:
- **`/usage`** (if it or `/cost` breaks down cost per session): a session with heavy cache reuse shows markedly lower effective cost than raw token count would suggest. If cost scales linearly with turn count despite a large stable CLAUDE.md, caching isn't landing — go to §4.3.
- **API-level introspection** (if any custom harness wraps Claude Code or the Agent SDK/raw API): every response's `usage` object has `input_tokens` (uncached, full price), `cache_creation_input_tokens` (written this turn), `cache_read_input_tokens` (served from cache, ~0.1x cost). Total prompt size = sum of all three. Persistent `cache_read_input_tokens` of 0 across turns that should share a stable prefix = something is invalidating every turn.
- If custom tooling exists around the API/SDK and doesn't log `usage` per request, recommend adding it — it's the only ground-truth signal for cache health.

### 4.3 Silent cache-invalidator checklist

Walk every file that renders into the system prompt or tool list before the first stable point (CLAUDE.md, `.claude/rules/*.md`, all `SKILL.md` files) and check for each of these. Note file:line for each hit and what it should become.

| # | Check | Grep pattern | Why it breaks caching |
|---|---|---|---|
| 1 | Dates/timestamps interpolated into CLAUDE.md/skill preambles | `date +`, `` `date` ``, `$(date`, "Today's date is", `datetime.now()`, `Date.now()` | Changes every day/call — invalidates the whole prefix from that point on |
| 2 | Random/non-deterministic IDs or ordering | `uuid`, `random`, `shuf`, `RANDOM`, unsorted `ls`/glob embedded in a static doc | Same bytes must appear every time |
| 3 | Environment-dependent content rendered early (hostname, username, cwd, branch, terminal width) | `whoami`, `hostname`, `$PWD`, `git branch --show-current` used to build prompt text | Differs per machine/session — kills cross-session reuse |
| 4 | Non-deterministic serialization feeding a static config block | `json.dumps` without `sort_keys=True`, unordered dict/set iteration, unordered glob results | Same content, different byte order → different prefix hash |
| 5 | Conditional system-prompt sections gated on runtime flags | `if flag: system += ...`, feature-flag-driven prompt assembly | Every flag combo is a distinct prefix |
| 6 | Session-varying MCP server list/tool set | `.mcp.json`, `enabledMcpjsonServers`, conditional MCP registration hooks | Tools render first — any variation invalidates system+messages too |
| 7 | Different models per turn on an otherwise continuous conversation | subagent `model:` overrides mid-conversation, `/model` switches | Caches are model-scoped; switching forces a full rebuild |
| 8 | Per-user/session IDs baked into a "stable" system block | f-string/template interpolation of IDs into system-level text | Prevents cross-user/session sharing of the same cache entry |

Fix is almost always: move dynamic content to *after* the stable prefix (e.g. inject last, just before the user's actual request), or make it deterministic (sort before serializing).

### 4.4 Tool-output hygiene — filter before it enters context

Highest-leverage fix in most sessions: **never let a raw verbose command dump straight into context.** Run the tool, capture full output, extract only what matters (pass/fail summary, error lines, diff hunks near the point of interest) before it becomes part of the transcript.

| Tool | Avoid | Use instead |
|---|---|---|
| npm/pnpm/yarn test | `npm test` raw | `npm test 2>&1 \| tail -n 50`; or `grep -E "✓|✗|passing|failing|Error"`; `--reporter=dot`/`--silent`; on failure `grep -A 20 "FAIL\|Error"` scoped to the failure |
| pytest | verbose default with tracebacks | `pytest -q`; `pytest --tb=short -q`; for failures only `pytest -q 2>&1 \| grep -E "FAILED|ERROR|passed|failed"` |
| eslint/lint | `eslint .` full | `eslint . --format=compact 2>&1 \| grep -v "^$"`; `eslint . -f json \| jq '.[] \| select(.errorCount > 0)'`; `--quiet` |
| tsc | raw `--noEmit` | `tsc --noEmit 2>&1 \| head -n 40`; or grep scoped to the file being edited |
| docker build | full layer log | `2>&1 \| tail -n 30`; or `grep -E "ERROR|error:|Step [0-9]+/"` |
| git diff/log | full changeset dump | `git diff --stat` first, then `git diff -- <file>` for files under discussion; `git log --oneline -20` |
| large JSON/log | cat/print whole file | `jq` to project fields, or `grep`/`sed -n` for the relevant range |
| grep/rg itself | unbounded `-r` dumped raw | pipe through `head -n N`, or `-l` (filenames only) first |

Audit steps: (1) search CI configs, `Justfile`/`Makefile`/`package.json` scripts, and any Claude Code hooks for raw test/build/lint invocations Claude would run directly. (2) Check skills/custom commands for guidance recommending full-verbose runs — flag them. (3) Recommend project wrapper scripts defaulting to quiet/summary mode so a fresh session gets filtered output without remembering flags.

### 4.5 Large file reads — offset/limit strategy

- The Read tool typically defaults to reading up to 2000 lines from the start of a file; beyond that needs explicit offset/limit.
- Never read an entire large file (log, generated code, lockfile, data file) "just to check something." Grep/search first for relevant line numbers, then read scoped to that region.
- **Lockfiles** (`package-lock.json`, `poetry.lock`, `Cargo.lock`, `yarn.lock`): never read in full — `grep -A 3 '"package-name"' package-lock.json` etc.
- **Generated code** (build output, `.min.js`, codegen, `dist/`, `build/`): opaque — grep for a symbol, don't read whole; if needed, read with a limit around the grep-matched line.
- **Log files**: `tail -n 100` or `grep -n "ERROR"` to find line numbers, then read scoped to that range.
- **Large data files**: `head`/`jq`/`grep` to inspect shape/sample rows, don't read a multi-thousand-row file whole.

Audit steps: `find . -type f -size +200k \( -name "*.log" -o -name "*.json" -o -name "*.lock" \)` (adjust patterns to the project's stack) to inventory tempting large files. Check whether CLAUDE.md/skills already warn about known-large files (generated schemas, vendored bundles, fixtures) — if not and such files exist, recommend adding "never Read `<path>` in full; grep first."

### 4.6 Settings affecting caching or output truncation

- Output truncation is generally handled by the harness, not a user-configurable ceiling — the practical lever is what you pipe into the tool call (§4.4), not a global setting.
- Model/subagent selection affects cache *scope*, not the mechanism — switching models mid-session (e.g. a reasoning-tier main thread delegating to a cheap-tier subagent) does not share a cache between them; expected, not a bug.
- MCP server config stability matters more than any explicit caching flag — check for conditionally-enabled MCP servers (env/flag-dependent), the most common config-level silent invalidator, since MCP tool declarations render before system/messages.
- No user-facing knob typically exists to force a longer cache TTL — that's an API-level parameter set by the harness. Nothing to audit here beyond confirming a custom harness/SDK wrapper isn't accidentally omitting cache markers on the stable system-prompt block.

### Phase 4 deliverables

1. List every silent-cache-invalidator hit from §4.3, file:line, suggested fix.
2. List of test/build/lint invocations in scripts/CI/skills dumping raw output, with quiet/filtered replacements (§4.4).
3. Inventory of large files (lockfiles, logs, generated code, fixtures) over ~200KB, with a recommendation to add grep-first guidance to CLAUDE.md if likely to be read directly.
4. If custom tooling wraps the API/SDK: whether `cache_read_input_tokens` is logged/monitored anywhere — recommend adding it if not.

---

## Phase 5: Synthesis — prioritized findings and report-back

### Reporting format — mandatory

Produce a single findings table:

| Check | Current state | Flag (ok/warn/bad) | Recommended action |
|---|---|---|---|

One row per check across Phases 1-4. Order the table by Phase, then flag severity (bad → warn → ok) within each phase.

**Do not apply any changes automatically.** Present the findings table and specific proposed diffs/edits, then ask the user before modifying any CLAUDE.md, skill, settings.json, or hook. This is a hard requirement, not a suggestion.

For each finding, explicitly mark whether it's **official-docs-verified** or **community-sourced/unverified** (per the flags preserved throughout this playbook) — don't launder community-sourced claims into confident assertions in your own report.

### Generalized top-priority levers (apply/adapt to what you actually find)

Ranked by typical expected token/cost impact, independent of any specific project:

1. **Stop reflexively fanning out for small tasks.** Every subagent call pays fixed overhead plus the subagent's full response lands as main-thread input tokens. Delegate only when read-heavy/mechanical, genuinely parallelizable, or would otherwise pollute main-thread context with large intermediate output.
2. **Treat compaction as a last resort, not a steady-state strategy.** `/clear` at natural boundaries, keep memory files as the durable record instead of relying on the live transcript, `/compact focus on <X>` at a chosen checkpoint rather than letting auto-compact fire mid-task.
3. **Assume prompt caching is being silently defeated until checked.** Given typical session sizes (CLAUDE.md, skills, rules — often tens of thousands of tokens), a cold cache every turn is one of the largest, least-visible cost multipliers. Audit for the §4.3 invalidator patterns periodically, not just once.
4. **Right-size effort and response verbosity per subagent call, not just model tier.** Subagent response text is what the orchestrator pays for on every subsequent turn — over-generous responses compound across a session far more than a single effort misconfiguration.
5. **Use worktree isolation sparingly** — it solves a correctness problem (concurrent-edit collision), not a token problem, and shifts cost onto human reconciliation when it does produce changes. Reserve for genuinely parallel, mutually-interfering work.

`[community-sourced, tempering caveat, keep un-laundered]`: multiple high-engagement GitHub issues and HN threads describe token/quota consumption that reporters could not attribute to their own usage patterns (e.g. "100% usage after 2 hours of light work, no subagents"), suggesting some cost variance in Claude Code is not fully explained by prompt/context/model choices and may reflect platform-side accounting behavior outside any orchestration rule's control. Not actionable as a rule change — flagged so an unexplained cost spike isn't automatically assumed to be a workflow mistake.

---

## Appendix A: Community findings — corroboration summary

These converge across 2+ independent community sources (blogs/HN/GitHub) beyond official docs; treat as strong-but-unverified signal, not fact:

- Subagent cost framing: "subagents are not automatically cheaper — use them when saved main-context clutter is worth more than startup overhead" (matches §3.1/§3.7).
- CLAUDE.md as a per-turn tax: "a 5,000-token CLAUDE.md costs 5,000 tokens on every single turn"; 200-line ceiling for the global file independently recommended.
- Compact-early practice, with and without the unverified `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` env var (§2.1).
- Cross-subagent redundant re-reads as a real, reported failure mode (§3.3).
- Pre-filtering command output before it reaches context — a concrete, low-risk lever applying even to non-delegated single-agent work (§4.4), arguably higher-leverage for routine dev-loop tasks than subagent-tuning advice.
- Unexplained quota/cost variance reports (Appendix A tempering note above) — real, but outside any prompt-engineering lever's control.

---

## Appendix B: If you want to do live research on top of this playbook

Claude Code and its docs evolve continuously — anything version-sensitive above (compaction %, context window sizes, plan pricing/limits, model names/pricing, env var names) should be re-verified before being treated as current fact, especially if this file is more than a few months old relative to when it's being run. Below is a reusable research method (validated 2026-07-03) for doing that verification or extending this playbook.

### High-signal sources

**1. Hacker News via Algolia API (WebFetch, no auth)**
- Good for: practitioner discussion, tool launches with cost/context claims, comment threads with real numbers.
- Access: `WebFetch("http://hn.algolia.com/api/v1/search?query=<terms>&tags=story", prompt)`; swap `tags=comment` for comments. Direct API, no `site:` filter needed.
- Working query terms: `claude code token cost`, `claude code compaction prompt caching`, `claude code subagent context`.
- Ask the WebFetch prompt to extract story title + URL + points + comments + one relevant quote/stat.

**2. GitHub REST Search API on `anthropics/claude-code` issues (curl, no auth needed for public search)**
- Good for: ground-truth bug reports/feature requests on compaction, context, token usage; comment count as a signal-strength proxy.
- Access:
  ```
  curl -s "https://api.github.com/search/issues?q=repo:anthropics/claude-code+<TERM>+in:title,body&sort=comments&order=desc&per_page=10"
  ```
  Pipe to a small script extracting `number`, `title`, `html_url`, `comments`. Fetch one issue body via `curl -s "https://api.github.com/repos/anthropics/claude-code/issues/<NUMBER>"` → `.body`.
- Sorting by `comments` desc surfaces the highest-engagement threads first. Unauthenticated rate limit: 60/hr — batch queries.
- **`anthropics/claude-code` GitHub Discussions are disabled** (confirmed via API `410`) — don't waste a call there; issues are the only GitHub-native channel.

**3. WebSearch, phrased as a normal query, no `site:` restriction**
- Good for: blog posts/newsletters that themselves summarize or quote Reddit/Discord/Twitter discussion — the practical workaround for the Reddit block below. Also directly surfaces dedicated cost-optimization guides.
- Access: include the word "reddit" or "community" in the query *text* (not as a `site:` filter) to bias toward aggregator/summary content, e.g. `"Claude Code reduce token usage subagents reddit"`.
- Always WebFetch the actual article afterward — the search snippet alone is too thin to cite confidently.

**4. WebFetch on articles surfaced by #3**
- Access: `WebFetch(url, "extract concrete/actionable tips, especially anything with specific numbers, env vars, or commands, and flag anything that reads as practitioner experience rather than a restatement of official docs")`.
- Treat env-var-level or numeric claims from these as unverified against official docs unless cross-checked elsewhere — flag, don't assert.

### Low-signal / skip

- **Reddit direct access** (`site:reddit.com` in a WebSearch query, or `allowed_domains: ["reddit.com"]`): hard-blocked — confirmed via explicit API error (`"reddit.com" not accessible to our user agent`). Don't retry; use source #3 instead for secondhand signal.
- **`site:reddit.com` Boolean queries generally**: WebSearch silently returns zero results for blocked domains rather than erroring — don't conclude "no discussion exists" from an empty `site:reddit.com` result.
- **GitHub Discussions tab**: disabled entirely for this repo — confirmed via API, not a search fluke.
- **X/Twitter**: no free API access comparable to HN Algolia; deprioritize unless a query organically surfaces X links.

### Quick-reference query bank

- HN Algolia: `claude code token cost`, `claude code compaction prompt caching`, `claude code subagent context`
- GitHub issues: `repo:anthropics/claude-code compaction in:title,body`, `repo:anthropics/claude-code token cost in:title,body` (both `sort=comments&order=desc`)
- WebSearch: `Claude Code reduce token usage subagents reddit`, `Claude Code token cost optimization dev.to blog post`, `Claude Code context window management tips community reddit`
