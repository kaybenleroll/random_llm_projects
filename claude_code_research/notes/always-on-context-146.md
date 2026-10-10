# Always-on context per session (issue #146), 2026-10-09

## Method (re-runnable)
1. First-request total = first main-thread assistant record's usage (input + cache_creation + cache_read) in `~/.claude/projects/<cwd-key>/<session>.jsonl`. Script: `.scratch/first.py` (lists first-turn usage across sessions), `.scratch/comp.py <sessionid-prefix>` (component sizes), `.scratch/fit.py` (char totals vs usage).
2. The transcript stores every injected attachment verbatim (type `instructions`, `skill_listing`, `agent_listing_delta`, `deferred_tools_delta`, `mcp_instructions_delta`, `hook_success`, `prompt_snapshot`, ...). Component size = characters of that attachment content.
3. Tokenizer is NOT available offline. Tokens per component = chars / 2.68, a ratio CALIBRATED so message-side chars match (total - cached prefix). Cross-check: poc cwd gives 2.67 c/t independently (see below), so the ratio is stable, but the per-component split is ESTIMATED, not measured. `/context` was not run (needs an interactive session).
4. "System prompt + built-in tool schemas" is taken as the cache-READ prefix of the first call (shared across sessions, i.e. the stable system+tools block): 13,985 to 15,938 tokens across 4 same-cwd sessions. Measured upper bound for system+tools; cannot be split further read-only (tool schemas are not in the transcript).
5. Billing: all sessions are the personal Max account, Sonnet 5.5 main thread. Rates $/MTok (Sonnet 5.5): cache read 0.10 (per commit 59216ba), 5m write 2.50, 1h write 4.00 (from token_cost_report.py). Plan mode runs on Opus 5.5 (cache read $0.20/MTok, 0.05x of $4 input; 5m write $5, 1h write $8; per `.scratch/compaction-policy-opus.md` and `-fable.md` price tables) and is out of scope for the tables, but see Cost framing.

## Table A: cwd = random_llm_projects/claude_code_research (session c6140215)
First-request total MEASURED: 43,909 tokens (2 uncached + 27,969 created + 15,938 read). Other same-cwd sessions: 43,330 / 43,569.

| Component | Chars | Tokens (est) | Source | Method |
|---|---|---|---|---|
| System prompt + built-in tool schemas | 7,630 prompt text | ~15,938 | harness | MEASURED (cache-read prefix); incl. prompt text ~2.8k est |
| Skill listing (69 skills) | 25,315 | ~9,450 | skill_listing; ~/.claude/skills + plugins + anthropic-skills | chars/2.68 |
| Global CLAUDE.md | 12,799 | ~4,780 | ~/.claude/CLAUDE.md | chars/2.68 |
| Agent listing (13 types) | 6,976 | ~2,600 | ~/.claude/agents + built-ins | chars/2.68 |
| MEMORY.md index | 6,570 | ~2,450 | ~/.claude/projects/<root>/memory/MEMORY.md | chars/2.68 |
| skill-hygiene.md rule | 6,295 | ~2,350 | random_llm_projects/.claude/rules | chars/2.68 |
| SOUL.md | 3,754 | ~1,400 | ~/.claude/SOUL.md | chars/2.68 |
| Deferred tool names (25) | 3,592 | ~1,340 | deferred_tools_delta | chars/2.68 |
| Env/model/session ctx/date/etc | ~2,400 | ~900 | harness attachments | chars/2.68 |
| claude_code_research-notes.md | 2,242 | ~840 | subproject .claude/rules | chars/2.68 |
| MCP instructions (Claude Docs) | 2,157 | ~800 | claude.ai connector | chars/2.68 |
| Root CLAUDE.md | 1,565 | ~580 | random_llm_projects/CLAUDE.md | chars/2.68 |
| Subproject CLAUDE.md | 866 | ~320 | claude_code_research/CLAUDE.md | chars/2.68 |
| Hooks per prompt (date, repo/queue) | ~165 | ~60 | UserPromptSubmit | chars/2.68 |
| MACHINE.md | 202 | ~80 | ~/.claude/MACHINE.md | chars/2.68 |
| Sum | | ~43.9k | | prefix measured + message side calibrated to total |

CAVEAT: AC1's "within 10%" holds by construction: the 2.68 chars/token ratio was fitted to the total. The only independent evidence is the cross-cwd stability of the ratio (2.67 in poc vs 2.68 here). The per-component split remains an estimate.

## Table B: cwd = describe_data/poc_planning_tool (session d7cc3ee2)
First-request total MEASURED: 69,367 (2 + 69,367 created + 0 read; cold). Sibling sessions with warm prefix: 33,004 + 36,857 read = 69.9k.
Cache-read prefix (system + tools) = 36,857 => ~20.9k MORE than Table A prefix. Inferred cause (NOT verified): non-deferred MCP tool schemas from `.mcp.json` (gitnexus, postgres, context7, sequential-thinking; deferred list covers only context7/postgres/seq-thinking/Docs names, gitnexus tools absent from it).
Message side ~32.5k tokens for 86.7k chars (2.67 c/t): CLAUDE.md files 12,357+6,108+2,229+12,975 chars (global 4.6k tok, poc CLAUDE.md 2.3k, container-lifecycle 0.8k, claude-workflow.md 4.8k), MEMORY.md 8,860c (3.3k), skill listing 27,076c (10.1k), agents 7,565c (2.8k), deferred 3,918c, MCP instr 2,830c, extra hook "Usage" line.

## Ranked trim candidates (Table A cwd; per-request saving at steady state)
Savings USD per request = tokens x rate; read 0.10/MTok => 1k tokens = $0.0001/request ($0.10 per 1,000 requests). One-off cold-start write: 1k tokens = $0.0025 (5m) / $0.0040 (1h). An Opus 5.5 main thread would be 2x on reads ($0.20/MTok vs Sonnet's $0.10).

| # | Candidate | Tokens saved (est) | Risk | Rec |
|---|---|---|---|---|
| 1 | Drop the 9 `anthropic-skills:*` listing entries (9,711c) | ~3,600 | low (connector/desktop skills; unused in CLI work); confirm a disable mechanism exists | trim |
| 2 | Scope skill-hygiene.md: move chezmoi/zsh/gh-merge rules to an on-demand note or path-scoped rule (6,295c, ~60% movable) | ~1,400 | low-med (rules then not always seen) | trim |
| 3 | Disable claude.ai Claude Docs connector (MCP instructions 2,157c + 8 deferred names) | ~1,200 | low if unused | remove |
| 4 | Shorten verbose skill descriptions (dataviz 1,447c, code-review 994c, deep-research dupes, plugin skills 6,766c total, ~half) | ~1,300 | low (trigger accuracy may drop) | trim |
| 5 | Prune agent listing: drop `claude`, `statusline-setup`; shorten claude-code-guide (1,066c), general-purpose-xhigh (945c), stress-tester (842c) - ~2,200c | ~820 | low | trim |
| 6 | MEMORY.md: collapse closed/negative-result project entries (~8 of 31 lines) | ~700 | low-med | trim |
| 7 | Move claude_code_research-notes.md bulleted tips to on-demand note | ~500 | med | keep/trim later |
| 8 | Compress global CLAUDE.md (Subagent Orchestration 6,261c, Workflow Gates 5,021c) ~15% | ~700 | HIGH (behavioural rules; user-owned policy) | keep |
Not candidates: system prompt/tool schemas (15.9k, harness), SOUL.md, plan mode on Opus.
Total of #1-6: ~9.0k tokens (~20% of 43.9k) = ~$0.0009/request at read rate; ~$0.036 per cold start at 1h write (9.0k x $4/MTok). See Cost framing: the read-rate figure understates the real saving by 2-4x, yet the saving is still small.

Poc cwd extras (inferred, larger than all above): MCP tool schemas ~21k tokens (verify by running with `.mcp.json` servers disabled one at a time and diffing the first-turn cache-read prefix); claude-workflow.md ~4.8k tok; MEMORY.md ~3.3k tok.

## Per-component "what it buys / costs if removed" (AC2 top five, by size)
1. Skill listing 9.4k: lets model auto-trigger skills; removing unused entries loses nothing, removing used ones loses auto-invocation (explicit /name still works for disable-model-invocation skills).
2. Global CLAUDE.md 4.8k: user's orchestration/workflow gates; removal changes behaviour fundamentally - keep.
3. Agent listing 2.6k: subagent_type choice; unused types are dead weight.
4. MEMORY.md 2.5k: cross-session feedback; stale entries cost, but each prevents a repeated correction.
5. skill-hygiene.md 2.4k: repo hard rules (issue/branch policy) matter every session; chezmoi/zsh trivia does not.

## Could not do read-only
- `/context` breakdown (interactive only); fresh-session first-request capture (used existing transcripts instead).
- Exact tokenizer counts (no offline tokenizer/API count); per-component tokens are estimates. System vs built-in tool schema split not recoverable.
- Poc 21k prefix gap cause not verified. Work-account run (AC4) deferred until billing mode known; method above is portable.
- AC3 (filing issues) requires user approval; not done.

## Cost framing
Cost per request at the cache-read rate understates the true cost of fixed context by roughly 2-4x. Figures below were re-derived from `.scratch/compaction-policy-opus.md` (523 main-thread transcripts, Aug-Oct 2026) and `-fable.md`; for a 9k-token trim:

- Baseline rewrites on `opusplan` model toggles (about 1.1% of requests; each toggle is a fresh cache on the other model, Opus 1h write $8/MTok) and gaps over 1h (about 0.9% of requests, $4/MTok on Sonnet): 9k x (0.011 x $8 + 0.009 x $4)/MTok = about +$0.0011 per request, against $0.0009 at the read rate. Reproduces.
- Each subagent spawn rewrites the CLAUDE.md and skill/agent listings at the 5m write rate (subagents and compaction use a 5m TTL): 9k x $2.50/MTok = about $0.0225 per Sonnet spawn. Median is 13 Agent calls per session (22 in the highest-delegation third), so about $0.29 per median session, up to about $0.50 in high-delegation sessions. Arithmetic reproduces; that each spawn rewrites the full 9k is an ASSUMPTION, not measured here.
- Total for the 9k trim: roughly $0.4-0.7 per session (reads ~$0.19 over ~216 requests, toggles/gaps ~$0.24, spawns $0.29-0.50).
- Share of spend: 9k is about 4% of a ~206k mean replayed context, so at most 3% of main-thread spend and at most 1.5% of total spend (main thread is roughly 40-60% of total). NOT VERIFIED: the 206k mean replayed context does not appear in either policy file; the sourced figure is median peak context 369k (45 largest, subagent-heavy transcripts; the 460-session set gives 278-316k by delegation tercile).

Conclusion: session length is the lever, not the baseline. Context-proportional cost (reads plus large rewrites) is about 65% of main-thread spend, and a median session grows about 1.2-2.2k tokens per request.

## Findings
- The 9 `anthropic-skills:*` entries come from the claude.ai-synced Anthropic Directory. They are not in `enabledPlugins` (`~/.claude/settings.json`) and no toggle is known. This is a trigger-hygiene problem, not a cost one: near-duplicate triggers (`deep-research` vs `anthropic-skills:deep-research`, `docs` vs `docx`, `skill-creator` vs `write-a-skill`). No issue to be filed.
- MEMORY.md (about 2.5k tokens) is the only monotonically growing fixed component. Prune it within the /reflect cadence.
- Per-prompt hook injections recur every turn (about 3k tokens over a 50-prompt session): trivial.
- The Sep to Oct baseline drop (about 90k to 43k) is unattributed; presumably dotfiles#265 (tool-search deferral). Not verified.
- The poc 21k prefix gap (suspected non-deferred MCP schemas from `.mcp.json`) is unverified. Check with one `/context` in the 2026-10-21 poc proxy session.
- Live-fire check of the context hook should also confirm it reads start-of-session context correctly in a cwd with a different baseline (poc, about 69k).

## Decisions
- No broad trim.
- Thresholds stay provisional.
- AC4 (work-account run) is folded into the work-account billing-mode item (week of 2026-10-12) rather than keeping #146 open.
- AC3 (trim issues) not filed.

## 2026-10-10: poc_planning_tool MCP trim result
- Before (2026-10-09 `/context`, poc_planning_tool): 59.8k total, MCP tools 24.9k loaded (31 tools).
- Cause: `"alwaysLoad": true` on the gitnexus server in poc_planning_tool's `.mcp.json` exempted its 19 tools (24.3k tokens) from MCP tool-search deferral, although `ENABLE_TOOL_SEARCH` was on globally. Per code.claude.com/docs/en/mcp ("Exempt a server from deferral").
- After (fresh-session `/context`, user-run 2026-10-10): 34.2k total (6% of 600k window); MCP tools "23 tools · 0 tokens (loaded on-demand)". Saving 25.6k. Tool count fell from 31 to 23; the 8 missing are likely the claude.ai Claude Docs connector tools (unconfirmed).
- The user ran a gitnexus smoke test and judged deferred loading acceptable.
- Audit evidence: `claude_code_research/.scratch/poc-mcp-audit.md` (local only). Caveat: its usage counts (gitnexus 649 calls / 156 sessions; 20 of 31 tools never called) may include sessions from other projects (it reports 6,799 sessions scanned); treat the counts as unverified.
- Lesson: `alwaysLoad` on a many-tool MCP server is a large per-request cost; check `/context` for it.
