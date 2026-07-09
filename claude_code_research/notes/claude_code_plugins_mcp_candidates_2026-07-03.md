# Claude Code plugins / MCP servers / skills — candidates to assess per-project

Researched 2026-07-03. Load this file into other project sessions as a checklist —
for each item, look it up, check activity/maintenance, and judge fit against that
project's stack before installing anything.

Star counts and framing are pulled from post-launch blog/SEO coverage, not all from
primary Anthropic sources — treat exact numbers as approximate. Relative ranking
(official repo > wshobson/agents & obra/superpowers > GitHub/Playwright/Context7 MCP)
was consistent across independent sources.

## 1. Official Anthropic marketplaces

- **claude-plugins-official** — bundled marketplace, installed via
  `/plugin install <name>@claude-plugins-official` or `/plugin` → Discover.
  Anthropic-authored plugins plus vetted partner/community ones.
  https://github.com/anthropics/claude-plugins-official
- **claude-plugins-community** — Anthropic-hosted, community-submitted, passes
  automated validation/safety screening before listing. Add manually:
  `/plugin marketplace add anthropics/claude-plugins-community`.
- Docs: https://code.claude.com/docs/en/discover-plugins

**To assess:** browse `/plugin` in each project and note anything relevant to that
project's language/framework/CI setup.

## 2. Community plugin marketplaces (high traction)

- **wshobson/agents** — largest third-party marketplace: 88 plugins, 194 agents,
  158 skills, 106 commands. Cross-compatible with Codex CLI, Cursor, OpenCode,
  Copilot, Gemini CLI from one Markdown source. ~36.6k★. Single maintainer, no
  pinned releases — tracks `main`, so check for breaking changes before pulling in.
  https://github.com/wshobson/agents
- **obra/superpowers** — largest skill library (not a marketplace): full SDLC
  workflow chained as composable skills — brainstorm → worktree → plan → TDD →
  review. ~40.9k★. Cited as the most complete dev-workflow built purely on skills.
  https://github.com/obra/superpowers
- **hesreallyhim/awesome-claude-code** — curated discovery list (not itself a
  marketplace) covering skills, hooks, slash-commands, orchestrators, plugins.
  Good starting point when scanning a new project for candidates.
  https://github.com/hesreallyhim/awesome-claude-code
- Secondary/lower-confidence: ComposioHQ/awesome-claude-plugins,
  subinium/awesome-claude-code, alirezarezvani/claude-skills (~5.2k★, 330+ skills,
  multi-agent-tool compatible).

**To assess:** for wshobson/agents and superpowers specifically — check whether
individual skills/agents overlap with skills you already have in `~/.claude/skills/`
before installing wholesale; these are broad collections, not everything applies.

## 3. Commonly recommended MCP servers

Convergent picks across independent "best MCP server" roundups:

- **GitHub MCP** — issues/PRs/CI triggers/commit history from the terminal.
  Highest practical impact for most repos.
- **Playwright MCP** (Microsoft-maintained) — real browser automation/verification.
  >30k★, called the 2nd-most-popular MCP server in the ecosystem. Relevant for any
  project with a web frontend or E2E test needs.
- **Context7** — live library/API docs lookup; reduces wrong-API-signature errors.
  Worth it for projects using fast-moving or less-common libraries.
- **Sequential Thinking** — step-by-step reasoning scratchpad. Already in use in
  this session (`mcp__sequential-thinking__sequentialthinking`); value is
  situational since Claude plans reasonably well natively.
- **Filesystem MCP** — generally skip for Claude Code; redundant with the built-in
  Read/Edit/Write/Glob/Grep tools.

**Practical consensus:** Context7 + GitHub MCP + Playwright MCP covers most real
workflows. Assess per-project: does the project have a browser-facing surface
(→ Playwright)? Does it lean on fast-moving/unfamiliar libraries (→ Context7)?
Is GitHub the primary issue/PR tracker (→ GitHub MCP)?

## 4. Code-intelligence / repo-graph tools

- **GitNexus** (abhigyanpatwari/GitNexus) — code-intelligence/knowledge-graph
  engine. Ingests a repo (GitHub/GitLab/Azure/local/ZIP) and builds a structured
  graph of functions, classes, imports, inheritance, interface implementations,
  and call/execution flow via Tree-sitter AST parsing; hybrid BM25 + semantic
  search. Ships a client-side Web UI (no server, code stays local) plus a
  CLI/MCP mode for coding agents. Exposes ~16-17 MCP tools: hybrid search,
  symbol/"360-degree" context, blast-radius impact analysis, uncommitted-diff
  change detection, multi-file rename/refactor coordination. Claude Code
  integration goes deepest: MCP tools + agent skills (Exploring, Debugging,
  Impact Analysis, Refactoring) + PreToolUse hooks injecting graph context +
  PostToolUse hooks auto-reindexing after commits. Also supports Cursor, Codex,
  OpenCode, Windsurf.
  Languages covered (14): TypeScript, JavaScript, Python, Java, Kotlin, C#, Go,
  Rust, PHP, Ruby, Swift, C, C++, Dart — feature depth (import resolution, type
  inference) varies per language, not explicitly ranked by the maintainer.
  **Caveat:** star count (~28k vs ~43.6k) and license (MIT vs PolyForm
  Noncommercial 1.0.0) were reported inconsistently across sources — verify
  directly on the repo before relying on either, especially license if used
  commercially.
  https://github.com/abhigyanpatwari/GitNexus

**To assess:** relevant for projects where cross-file impact analysis or
codebase-wide structural queries are a recurring pain point — check the
language list above against the target project's stack first, and confirm
license terms if commercial use is in play.

## 5. Skill/agent collections

Same top two as section 2 — wshobson/agents and obra/superpowers dominate.
Other "awesome-claude-code" forks (travisvn, BehiSecc, GetBindu variants) are
discovery indexes, not maintained collections in their own right — treat as
pointers, not sources to install directly from.

## Assessment checklist (per project)

For each candidate above, when reviewing in a specific project:

- [ ] Does it solve a real friction point in this project's current workflow?
- [ ] Is the source actively maintained (recent commits, issue responses)?
- [ ] Single-maintainer risk — does it track `main` with no pinned releases?
- [ ] Overlap check — does it duplicate a skill/agent/MCP server already configured
      here or in `~/.claude/skills/`?
- [ ] Trust/safety — official Anthropic listing (validated) vs. unvetted GitHub repo?
