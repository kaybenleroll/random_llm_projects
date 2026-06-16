# Chezmoi Dotfiles Setup: A Technical Reference

**Author:** Claude Code  
**Date:** 2026-06-16  
**Audience:** Machine owner — technically capable, not involved in the implementation

---

## What This Document Is

This report explains the dotfiles synchronisation system now running on your machines. It covers what was set up, why each decision was made, what you need to do next, and how to operate the system going forward. Read it once end-to-end before touching anything — the "why" matters as much as the "what".

---

## The Problem That Needed Solving

You run Claude Code (CC) on two machines:

- **skikk** — your local workstation (SKIKK Thor 16, Ubuntu 26.04)
- **uhet** — a headless remote server in a data centre, accessed only over SSH

CC stores everything meaningful about how it behaves in `~/.claude/`. Over time this directory accumulated a significant amount of configuration that is genuinely valuable and took real effort to develop: custom skills, agent definitions, hook scripts, a memory system, a SOUL.md file governing CC's intellectual disposition and communication style, a CLAUDE.md with project-level instructions, plus `settings.json` and `mcp.json` controlling permissions and MCP server integrations.

Managing these manually across two machines was unsustainable. Making a change on skikk meant remembering to also apply it to uhet. Running `git pull` and copying files by hand is error-prone and easy to forget. Eventually the two machines diverge silently, and you stop being able to trust that CC behaves consistently across them.

---

## Why Chezmoi

Several tools exist for managing dotfiles: symlinking from a Git repo, Ansible playbooks, GNU Stow, and dedicated dotfile managers like chezmoi or yadm. The choice here was **chezmoi**, for a specific set of reasons.

Chezmoi uses an **additive, opt-in model**: you explicitly add files to its source repo, and everything else on disk is left alone. This is the right model for `~/.claude/` because the directory contains a mix of managed configuration (skills, SOUL.md, settings.json) and machine-local runtime state (session transcripts, daemon sockets, credentials, cache) that must never be shared or committed anywhere. A symlink-the-whole-directory approach would require constantly excluding the runtime files; with chezmoi you only opt-in what you want, and the rest is invisible to it.

The second reason is **Go template support**. Your two machines have legitimately different MCP server permission requirements. Rather than maintaining two separate settings.json files, chezmoi lets you write one template file that generates the correct output for each machine at apply time. The template is rendered locally on each machine — nothing machine-specific ever leaves the machine in rendered form.

Third, the source of truth is a **standard Git repository**, hosted at `kaybenleroll/dotfiles` on GitHub. There is no chezmoi-specific sync daemon, no cloud service, no proprietary format. The repo is just files. You can inspect it, clone it with any Git client, and understand its structure without knowing anything about chezmoi.

---

## The Source Repository Layout

Chezmoi stores its source files at `~/.local/share/chezmoi/`. This directory is a Git repo, currently pushed to `git@github.com:kaybenleroll/dotfiles.git`.

Chezmoi uses a naming convention to map source files to their real destinations. A file stored as `dot_claude/SOUL.md` in the source repo is written to `~/.claude/SOUL.md` on disk. The `dot_` prefix becomes `.` in the real path. A file with a `.tmpl` extension is treated as a Go template and rendered before being written.

The initial commit (439b992) added 86 files. A second commit (b75b024) added the uhet hostname-conditional block to `settings.json.tmpl`. The full set of tracked files breaks down as follows.

**CC configuration files:**

- `dot_claude/CLAUDE.md` — global CC behavioural instructions
- `dot_claude/SOUL.md` — intellectual disposition and communication style rules
- `dot_claude/settings.json.tmpl` — CC permissions, MCP server configs, effort level (template)
- `dot_claude/mcp.json.tmpl` — MCP server definitions (template)
- `dot_claude/hooks/precompact-reminder.py` — fires before context compaction
- `dot_claude/hooks/pre-tool-use.py` — fires before tool use
- `dot_claude/memory/MEMORY.md` — persistent memory index
- `dot_claude/memory/*.md` — individual memory files
- `dot_claude/agents/triage-phase2.md` — subagent definition
- `dot_claude/agents/triage-phase3.md` — subagent definition
- `dot_claude/skills/*/SKILL.md` — all custom skills (new-session, stress-test, reflect, grill-me, diagnose, tdd, zoom-out, run-project-triage, and others)
- `dot_claude/skills/run-project-triage/bin/render_graph_mermaid.py` — skill helper script
- `dot_claude/skills/*/learnings.md` — per-skill accumulated learnings
- `dot_claude/rules/skill-hygiene.md` — project-level rules

**Shell configuration:**

- `dot_bashrc`, `dot_bash_profile`, `dot_zshrc`, `dot_zshenv`, `dot_gitconfig`

---

## What Is Excluded and Why

The `.chezmoiignore` file at the root of the source repo lists paths that chezmoi must never manage. Understanding these exclusions is as important as understanding what is tracked.

**CC runtime and session state** is excluded entirely:

- `.claude/.credentials.json` — authentication tokens. These are machine-specific secrets. Committing them to any repo, even a private one, is a security risk. Each machine must log in to CC independently.
- `.claude/daemon*` — the CC daemon socket and PID files. These are ephemeral OS-level state. Syncing them would break CC on the receiving machine.
- `.claude/backups/` — CC auto-backups of edited files. Local, transient, large.
- `.claude/file-history/` — CC file edit history. Local runtime data.
- `.claude/projects/` — session transcripts and per-project runtime data. This is the most important exclusion. Session transcripts are large, contain sensitive conversation history, are entirely machine-specific (each machine has different active projects), and there is no value in sharing them. Syncing these would bloat the repo and expose private information.
- `.claude/cache/` — CC download cache.
- `.claude/capture-state.json`, `debug/`, `downloads/`, `jobs/`, `hooks/__pycache__`, `*.log`, `*.lock` — all ephemeral.

**Credentials and keys** are excluded:

- `.gnupg/` — GPG keyring. Never commit private keys.
- `.azure/`, `.gemini*`, `.config/gcloud` — cloud provider credentials, machine-specific.
- `.config/gh/hosts.yml` — the GitHub CLI authentication token. Per-machine.
- SSH private keys: `id_*`, `known_hosts`, `authorized_keys`.
- `rclone.conf` — rclone remotes, which contain access credentials.

**Framework directories** are excluded:

- `.oh-my-zsh/` — this is an installed framework, not configuration. It is installed separately on each machine and can be updated independently. Tracking its thousands of files in chezmoi would be wrong.

**The sysadmin_files repo** is excluded. This is discussed in detail below.

---

## The Template System: Handling Per-Machine Differences

The most technically interesting part of the setup is how `settings.json` handles the two machines having different requirements.

Your two machines need different MCP permission configurations. uhet needs 27 additional `mcp__filesystem__*` and `mcp__github__*` allowlist entries, an `additionalDirectories` setting pointing at `~/.claude`, and `autoCompactEnabled: true`. skikk does not need these.

Rather than maintaining two separate `settings.json` files and manually keeping them in sync, `settings.json` is stored as `settings.json.tmpl` — a Go template. When `chezmoi apply` runs, it renders the template using data about the current machine, producing the correct `settings.json` for that machine.

Two template variables are used:

**`{{ .chezmoi.homeDir }}`** expands to the user's home directory. This is used throughout `settings.json` wherever absolute paths to `~/.claude/` appear. On both current machines this happens to be `/home/mcooney`, but using the template variable instead of a hardcoded path means the config works correctly if you ever add a machine where the home directory is different (a cloud VM running as root, for example, where it would be `/root`).

**`{{ .chezmoi.hostname }}`** expands to the machine's hostname. The uhet-specific block in the template looks like this:

```
{{- if eq .chezmoi.hostname "s3rbase" }}
  ... 27 additional MCP permission entries for uhet ...
  "additionalDirectories": ["/home/mcooney/.claude"],
  "autoCompactEnabled": true,
{{- end }}
```

`s3rbase` is uhet's actual hostname. When `chezmoi apply` runs on skikk (hostname: `skikk`), the condition is false and the entire block is omitted from the rendered output. When run on uhet (hostname: `s3rbase`), the block is included. One source file, two correct outputs.

`mcp.json` is also a template, though only to substitute `{{ .chezmoi.homeDir }}/` in place of hardcoded `/home/mcooney/` paths. There is no hostname-conditional logic in `mcp.json`.

---

## The sysadmin_files Situation

You had an existing Git repo (`kaybenleroll/sysadmin_files`) that contained shell configuration files, scripts, and utilities. It also had a custom installer script (`setup_conffiles.sh`) intended to deploy dotfiles.

The key finding was that `setup_conffiles.sh` was **never actually run** on either machine. Both machines had manually diverged from the repo over time. The repo was effectively abandoned as a dotfiles manager in practice, even if it nominally still contained dotfiles.

The decision was not to migrate sysadmin_files into chezmoi. The rationale: chezmoi now owns dotfiles management. sysadmin_files retains value for its `utilities/` and `dockerfiles/` directories — scripts and utilities that are installed or used, not managed as configuration. Those directories should stay in sysadmin_files. The dotfile-adjacent content in sysadmin_files can be left as-is; it is no longer the source of truth for anything chezmoi manages, and that is fine. No migration work is needed.

---

## Current State of Each Machine

### skikk

Chezmoi is fully installed and configured. The source repo is at `~/.local/share/chezmoi/` and has been pushed to GitHub. All 86+ files are tracked.

There is **one pending action**: you have not yet run `chezmoi apply` on skikk. When you do, chezmoi will normalize `settings.json` — specifically, it will remove a `poc_planning_tool` allowlist entry that was added during a project session and is project-specific, not something that belongs in the global config. This is a minor cleanup, but you should review it before applying.

Run these commands on skikk:

```bash
chezmoi diff        # shows exactly what apply would change — review this first
chezmoi apply       # applies changes (writes managed files from source to real disk locations)
```

### uhet

Chezmoi has been installed on uhet (via `mise use --global chezmoi` during this session), but the dotfiles repo has **not yet been bootstrapped**. The managed configuration does not yet exist on uhet. This is the most important pending action.

---

## Bootstrapping uhet

SSH into uhet and run the following:

```bash
# Clone the dotfiles repo as the chezmoi source
gh repo clone kaybenleroll/dotfiles ~/.local/share/chezmoi
# OR, if gh auth is not configured on uhet:
git clone git@github.com:kaybenleroll/dotfiles.git ~/.local/share/chezmoi

# See what chezmoi would write — review this carefully before applying
chezmoi diff

# Apply
chezmoi apply
```

What `chezmoi apply` does on uhet: it writes CLAUDE.md, SOUL.md, all skills, agents, hooks, and memory files to `~/.claude/`; it renders `settings.json.tmpl` with the `s3rbase` hostname block active (producing a settings.json with the 27 additional MCP entries, `additionalDirectories`, and `autoCompactEnabled: true`); and it writes the shell configs (`.bashrc`, `.zshrc`, `.gitconfig`, etc.).

It does **not** touch anything not tracked by chezmoi. `.credentials.json`, session transcripts in `.claude/projects/`, and all other excluded paths are completely ignored. If uhet already has an existing `settings.json` that differs from what chezmoi would write, `chezmoi diff` will show you the diff. Review it. If you want chezmoi's version to win, run `chezmoi apply`. If you want to preserve something from the local version, edit the template in the source repo first, re-add, commit, push, then apply.

---

## Adding a New Machine

The process is the same for any new machine — a home network PC, a cloud VM on GCP or AWS, whatever. Here is the full sequence from a blank machine.

**Step 1: Install prerequisites**

```bash
# Install mise (universal package manager — handles chezmoi and other tools)
curl https://mise.jdx.dev/install.sh | sh
# Alternatively on Ubuntu: sudo apt install mise

# Install chezmoi via mise
mise use --global chezmoi

# Install GitHub CLI (needed to clone the private repo easily)
sudo apt install gh
gh auth login
```

On a cloud VM, the process is identical. The VM needs SSH access (which you already have), a way to install mise or chezmoi directly, and a GitHub credential to clone the repo.

**Step 2: Clone and apply**

```bash
gh repo clone kaybenleroll/dotfiles ~/.local/share/chezmoi
chezmoi diff    # always review before applying
chezmoi apply
```

**Step 3: Add machine-specific config if needed**

If the new machine needs different MCP permissions or other settings that don't apply to skikk, add a new hostname-conditional block to `settings.json.tmpl`. Do this edit on skikk (where the source repo lives), not on the new machine:

```bash
# On skikk:
$EDITOR ~/.local/share/chezmoi/dot_claude/settings.json.tmpl
# Add: {{- if eq .chezmoi.hostname "new-machine-hostname" }} ... {{- end }}

chezmoi re-add ~/.claude/settings.json   # pull in any current skikk-local changes too
cd ~/.local/share/chezmoi
git add -p
git commit -m "add hostname block for new-machine-hostname"
git push
```

Then on the new machine:

```bash
chezmoi update   # pulls latest from GitHub and applies
```

**Step 4: Set up machine-local things chezmoi doesn't manage**

Some things legitimately differ per machine and are not worth templating into the dotfiles repo:

- **SSH config** (`~/.ssh/config`) — different hosts, jump hosts, and key paths per machine. Not tracked.
- **`.credentials.json`** — always excluded. Log in to CC on each machine independently with `claude login` or equivalent.
- **`.config/gh/hosts.yml`** — GitHub CLI token, per-machine. Run `gh auth login` on each machine.
- **Cloud credentials** (`.azure/`, `.config/gcloud`, `rclone.conf`) — per-machine, set up manually.

These are not failures of the chezmoi setup. They are intentionally outside it.

---

## The Ongoing Workflow

Once everything is bootstrapped, the daily workflow is straightforward.

**Changing a config file:**

Edit the file normally in its real location (e.g., `~/.claude/CLAUDE.md`). Chezmoi does not intercept writes — you edit files the same way you always have. After editing, pull the change back into the chezmoi source:

```bash
chezmoi re-add ~/.claude/CLAUDE.md
```

This copies the current state of `~/.claude/CLAUDE.md` into the source repo at `~/.local/share/chezmoi/dot_claude/CLAUDE.md`. Then commit and push:

```bash
cd ~/.local/share/chezmoi
git add dot_claude/CLAUDE.md
git commit -m "update CLAUDE.md: <what you changed>"
git push
```

**On the other machine, pulling the update:**

```bash
chezmoi update
```

This is equivalent to running `git pull` in the source repo followed by `chezmoi apply`. It fetches the latest from GitHub and writes the updated files to their real locations. If a file differs from what chezmoi would write, you will see the diff.

**Checking what's out of sync:**

```bash
chezmoi status    # shows which managed files differ from the chezmoi source version
chezmoi diff      # shows the actual diff for each diverged file
```

Run `chezmoi status` periodically on each machine to confirm nothing has drifted. It is fast and non-destructive.

**Adding a new file to tracking:**

```bash
chezmoi add ~/.claude/newfile.md
cd ~/.local/share/chezmoi
git add .
git commit -m "track newfile.md"
git push
```

Then on the other machine: `chezmoi update`.

**Browsing the source repo directly:**

```bash
chezmoi cd        # cd into ~/.local/share/chezmoi
ls                # browse the source tree
git log --oneline # see commit history
```

You can also just `ls ~/.local/share/chezmoi/` or open it in any editor or file manager. It is a plain directory.

---

## Conflict Resolution

Chezmoi does not auto-merge. When `chezmoi diff` shows that a file on disk differs from the chezmoi source version, you have two choices:

**Option A — Chezmoi wins:** Run `chezmoi apply` (or `chezmoi apply <file>`). The source repo version overwrites what is on disk. Use this when you want to propagate a change from the repo to this machine.

**Option B — Local disk wins:** Run `chezmoi re-add <file>`. The on-disk version is pulled into the source repo. Then commit and push. The other machine picks it up on next `chezmoi update`. Use this when you have made a local change you want to keep and propagate.

There is no third option. You choose which version wins, make it the source of truth in the repo, and the other machine follows.

---

## What Apply Does Not Touch

This is worth stating plainly, because it is one of chezmoi's most important properties for this use case.

Chezmoi only manages files that have been explicitly added to the source repo. It does not scan `~/.claude/` and try to reconcile everything there. Files that are not tracked are completely invisible to chezmoi — it will never delete them, overwrite them, or complain about them.

This means:

- Session transcripts in `.claude/projects/` — untouched on every `chezmoi apply`.
- Credentials in `.claude/.credentials.json` — untouched.
- Any CC-generated runtime files — untouched.
- Local customizations in files that aren't tracked — untouched.

If you later decide a currently-untracked file should be managed, run `chezmoi add <file>` to opt it in. Until you do that, chezmoi has no awareness of it.

---

## Reference: Current Machine States

| Machine | chezmoi installed | Source repo bootstrapped | Action needed |
|---------|-------------------|--------------------------|---------------|
| skikk | Yes | Yes, pushed to GitHub | `chezmoi diff && chezmoi apply` to normalize settings.json |
| uhet | Yes (via mise) | **No** | Clone dotfiles repo, `chezmoi diff && chezmoi apply` |
| New home machine | No | No | Install mise + chezmoi + gh → clone → apply |
| New cloud VM | No | No | Same as new home machine |

---

## Reference: Key Paths

| Path | What it is |
|------|-----------|
| `~/.local/share/chezmoi/` | Chezmoi source repo (the dotfiles Git repo) |
| `~/.local/share/chezmoi/.chezmoiignore` | Files/patterns chezmoi must never manage |
| `~/.local/share/chezmoi/dot_claude/` | Source for `~/.claude/` (managed CC config) |
| `~/.local/share/chezmoi/dot_claude/settings.json.tmpl` | Go template for settings.json |
| `~/.local/share/chezmoi/dot_claude/mcp.json.tmpl` | Go template for mcp.json |
| `git@github.com:kaybenleroll/dotfiles.git` | Remote GitHub repo (source of truth) |
| `~/.claude/` | Real CC config directory on disk |
| `~/.claude/.credentials.json` | Auth tokens — **never tracked, never commit** |
| `~/.claude/projects/` | Session transcripts — **never tracked** |

---

## Reference: Cheat Sheet

```bash
# See what chezmoi would change before touching anything
chezmoi diff

# Apply (write managed files from source repo to real disk locations)
chezmoi apply

# Pull latest from GitHub and apply in one step
chezmoi update

# Pull a changed file back into the source repo
chezmoi re-add ~/.claude/CLAUDE.md

# Add a new file to tracking
chezmoi add ~/.claude/newfile.md

# See which managed files differ from the source
chezmoi status

# cd into the source repo
chezmoi cd

# Commit and push after re-add (run inside the source repo)
git add -p && git commit -m "message" && git push
```

---

## Appendix: Commit History

| Commit | Description |
|--------|-------------|
| 439b992 | Initial chezmoi setup — 86 files tracked from skikk |
| b75b024 | Add uhet (s3rbase) hostname-conditional block to settings.json.tmpl |
