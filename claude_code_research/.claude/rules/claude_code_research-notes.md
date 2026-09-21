# Claude Code Research Notes

Subproject-scoped learnings from `/reflect` that don't belong in the shared root rules file (`../../../.claude/rules/skill-hygiene.md`).

## Where to file issues

GitHub issue repo placement (dotfiles vs random_llm_projects) is a **HARD RULE** in the root
rules file — see "GitHub Issue Repo Policy" in `../../../.claude/rules/skill-hygiene.md`. Read
it before running `gh issue create` from this subproject.

- Claude Code keys session-transcript storage by the literal launch directory (slashes to dashes), not the git repo root, so when searching past sessions in a repo with several subproject directories, enumerate every cwd-derived project store rather than only the repo-root one.
