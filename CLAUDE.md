# random_llm_projects

@.claude/rules/skill-hygiene.md

---

## ⚠ Wrong directory — check before assuming this applies

This file is also injected into subproject sessions (`system_queries/`, `leisure/`, etc.) as an ancestor CLAUDE.md — its presence in context does **not** by itself mean the session's cwd is this root directory. **Check the injected working-directory context (or run `pwd`) before acting on this section.**

**If cwd genuinely is the root of `random_llm_projects/`:** this directory is a holding repo, not a workspace. Real work lives in the subprojects:

- `system_queries/` — Linux system management, Justfiles, health queries
- `leisure/` — games, puzzle apps, desktop setup
- `tvfilm_recommendations/` — TV/film recommendation tooling
- `update_cv/` — CV and resume work
- `hardware_research/` — hardware buying and reviewing research (tablets, LLM inference machines, etc.)
- `claude_code_research/` — Claude Code capability research and experiments

Exit this session, `cd` into the relevant subfolder, and relaunch Claude Code there. Machine-specific context (hardware, active fixes, quirks) loads only in `system_queries/` sessions — any machine, hardware, or system-fix question asked from this root must be answered only after relaunching there, not from memory or guesswork. The only legitimate reason to run from this root is to edit shared config (`.claude/rules/skill-hygiene.md`, `mise.toml`) or do cross-project housekeeping.

**If cwd is actually a subproject:** this section doesn't apply — carry on there normally.
