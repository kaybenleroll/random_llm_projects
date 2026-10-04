# Claude Code Research Notes

Subproject-scoped learnings from `/reflect` that don't belong in the shared root rules file (`../../../.claude/rules/skill-hygiene.md`).

## Where to file issues

GitHub issue repo placement (dotfiles vs random_llm_projects) is a **HARD RULE** in the root
rules file — see "GitHub Issue Repo Policy" in `../../../.claude/rules/skill-hygiene.md`. Read
it before running `gh issue create` from this subproject.

- Claude Code keys session-transcript storage by the literal launch directory (slashes to dashes), not the git repo root, so when searching past sessions in a repo with several subproject directories, enumerate every cwd-derived project store rather than only the repo-root one.
- When recommending analysis approaches, default to Bayesian posterior intervals and contrasts with explicit credible bounds over p-value significance testing.
- Hooks spawned by Claude Code may not inherit the D-Bus session address `notify-send` needs — a notify-based hook guard can fail silently; forward the session address explicitly or implement a fallback delivery mechanism.
- When wiring gitleaks into a pre-commit hook, always pass an explicit `-c <hardened-config-path>` — without it, gitleaks falls back to any in-repo `.gitleaks.toml`, and a permissive or malicious in-repo config can silently disable the security gate.
- When searching Claude Code transcript JSONL files for `tool_use` content, search recursively — `tool_use` objects nest inside `message.content` arrays, not at each line's top level, so a top-level-only search produces false negatives (content wrongly reported absent when it's just nested).
- Bash traps are replace-on-set, not additive — a new `trap 'cmd' EXIT` silently overwrites any earlier EXIT trap (including one set by a sourced library) with no error; compose/chain onto the existing handler instead of overwriting it.
- `os.replace()` breaks `flock()`-based locking — the lock is held on the old inode, which replace unlinks, so a process opening the path afterward acquires an independent lock on the new inode and mutual exclusion silently fails. Keep the atomic replace for the data file itself, and take the lock on a persistent sidecar `.lock` path that is never replaced.
