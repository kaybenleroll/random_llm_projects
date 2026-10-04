# Skill Hygiene

Promoted from session captures. Review with `/reflect`.

This file holds portable, machine-agnostic rules only. It loads as a rules file
from the repo's `.claude/rules` directory in every subproject on every machine
(the `@import` in the root `CLAUDE.md` adds nothing).
Hardware/firmware/chassis-specific findings belong in
`system_queries/doc/machines/<slug>.md` instead.

---

### GitHub Issue Repo Policy — HARD RULE

- **HARD RULE:** File a GitHub issue about Claude Code skill/agent/hook/config work in `kaybenleroll/dotfiles`, not `kaybenleroll/random_llm_projects`, whenever the work touches any file under dotfiles' chezmoi source (`dot_claude/skills/`, `dot_claude/agents/`, hooks, `settings.json`, etc.) — even when the same task also touches random_llm_projects files. Dotfiles wins any tie. Only file in `random_llm_projects` when the work touches zero dotfiles files (pure claude_code_research notes/experiments/artifacts with no dotfiles-implemented change).

### Issue Work Branch Policy — HARD RULE

- **HARD RULE:** All work on a GitHub issue (this repo or `kaybenleroll/dotfiles`) goes on a dedicated feature branch and merges via PR — never commit directly to `main`, even mid-task from a subagent. Any subagent prompt that delegates issue implementation must explicitly instruct it to create/checkout the branch before its first commit, not just tell it to commit.
  - **How to apply:** when delegating issue implementation, name the branch (derive from issue number + short slug, e.g. `issue-101-keep-max-dedup`) in the subagent prompt and require it to branch before committing; open a PR referencing the issue (`Closes #N` same-repo, full `owner/repo#N` cross-repo — a bare `reponame#N` in a PR body silently fails to close a cross-repo issue) once the final step's tests are green; verify ACs against the diff (`/check-acs` or manually) before merging.

### General

- When `rm -rf` is blocked by deny rules, remove directory contents file-by-file then `rmdir` empty directories.
- In `settings.json` bash allowlists, use `**` to match paths containing `/` — single `*` only matches within one directory level and silently fails on multi-segment paths.
- Shell aliases that use interactive flags (e.g. `rm -i`, `mv -i`) block CC Bash tool execution in non-interactive contexts — guard such aliases with `[[ -o interactive ]]` so they only apply in interactive shells.
- When making count or list claims about structured data files (YAML, JSON, TOML, Markdown lists), run a script to derive the value rather than reading and asserting manually — visual inspection of structured files produces hallucinated counts.
- Chezmoi's built-in `.chezmoi.hostname`/`.chezmoi.fqdnHostname` detection can be corrupted by an unrelated but legitimate `/etc/hosts` loopback entry (e.g. for a local dev tool) — define an explicit `[data] hostname = "..."` per machine in `chezmoi.toml` and reference `.hostname` (not `.chezmoi.hostname`) in host-conditional `.tmpl` files instead.
- `chezmoi status` flags pure file-permission-mode drift (umask differences, e.g. 664/775 vs 644/755) the same as real content drift — diff actual file contents before treating a modified status as unsafe.
- Verify a dotfile is chezmoi-managed (`chezmoi managed | grep ...` or `chezmoi source-path`) before recommending a direct edit — if managed, edit the chezmoi source repo and apply/push so the change propagates instead of drifting on next sync.
- Use an unquoted heredoc terminator (`<<EOF`, not `<<'EOF'`) when the heredoc body needs `$(...)` command substitution to actually execute — quoted terminators suppress all expansions, which silently breaks constructs like `gh pr create --body "$(cat <<EOF ... EOF)"`.
- GitHub auto-closes a dependent/stacked PR when its base branch is deleted, even though the underlying commit is safe — open a fresh PR from the same branch/commit against the updated base (e.g. `main`) rather than trying to reopen the closed one.
- Before cutting new feature branches, verify local main has no unpushed commits and reset feature branches to `origin/main` — unpushed commits ride along into every branch cut from that head, silently polluting each branch's diff and PR scope.
- A validation hook demanding taxonomy labels absent from the repo's actual label set creates a circular blocker — both `gh issue create` and label assignment fail; reconcile the hook's expected taxonomy against `gh label list` before creating issues or labels.
- Network-mounted directories (e.g. rclone OneDrive/GoogleDrive FUSE mounts) can hang `find`, `rg`, `fd`, `du`, or any recursive walker indefinitely during whole-home scans — this is a genuine blocking-I/O hang (the walker blocks on `lstat` of the mountpoint itself when the daemon is unresponsive), not slowness, and `-xdev`/`-mount` does not reliably prevent it. Exclude such mounts by explicit path before running any whole-home scan.

<!-- demoted from global — global copy pending removal in a follow-up PR -->
- Chezmoi tracks `~/.claude/`: run `chezmoi update` (not `apply` — `apply` doesn't pull) before editing tracked files, then `chezmoi add`, branch, commit, push, and open a PR against `kaybenleroll/dotfiles` (same workflow as any other repo — no direct-to-main commits). If `update` fails (e.g. rebase conflict), resolve before editing/committing. Never create project-local copies of global `~/.claude/` files — edit the source.
- `~/.claude.json` is NOT chezmoi-tracked (only files inside `~/.claude/` are) — handle its edits separately by hand.
- zsh script traps: glob deletes via `find <dir> -maxdepth 1 -name 'pattern' -delete 2>/dev/null || true` (`nomatch` aborts the whole command on no-match, silently leaving files); quote every `$VAR` (zsh word-splitting differs from bash — unquoted guards silently mis-match); never name a variable `status` (read-only special parameter — assignment errors).
- Verify machine ownership before recommending it for the user's personal infrastructure — access/technical control (e.g. `s3rbase`) doesn't imply availability for that.
- GitHub REST/GraphQL expose only `allow_*_merge` permission booleans, not a repo's default PR merge method — never infer the preference from the API; in non-interactive contexts always pass an explicit `--squash`/`--merge`/`--rebase` to `gh pr merge` (omitted, it prompts interactively and blocks).
