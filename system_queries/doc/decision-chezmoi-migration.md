# Chezmoi Migration — Decision Document

_Synthesised 2026-06-16 from home survey, sysadmin_files repo analysis, chezmoi mechanics research, and Claude Code config sync options analysis._

---

## Current State Assessment

Two machines (skikk, uhet) share a `sysadmin_files` git repo that was designed around a symlink installer (`setup_conffiles.sh`). Neither machine has ever run that installer — live dotfiles are regular files, not symlinks, and both have drifted ahead of or behind the repo. Skikk's `.zshrc` has accrued the `zsh-claude-code-shell` plugin, a preexec/precmd race fix, and Antigravity CLI PATH; `.gitconfig` has a typo fix, `gh auth git-credential`, and `log.date`. uhet is 2 commits behind skikk at the repo level and smaller at the file level. Neither machine is using `sysadmin_files` as a live source of truth. Meanwhile, `~/.claude/` — which contains high-value workflow config including `settings.json` with 7 hardcoded absolute paths, `CLAUDE.md`, `SOUL.md`, hooks, skills, and keybindings — is entirely untracked. The problem to solve: establish working, multi-machine dotfiles management that covers all high-value configs including `~/.claude/`, resolves the existing drift, and doesn't create new maintenance overhead.

---

## The Three Options

### Option A: Convert sysadmin_files to chezmoi

Convert the existing repo in place: add `.chezmoiroot = "home"`, rename `conffiles/` files to `dot_` convention, add `.chezmoi.toml.tmpl`. All existing content (`utilities/`, `dockerfiles/`, `llm_files/`, `data_collection/`) stays in the repo root alongside the chezmoi-managed `home/` subtree.

**Workflow:** `chezmoi init git@github.com:kaybenleroll/sysadmin_files.git` on each machine; chezmoi uses the `home/` subdirectory as its source. Non-dotfile content coexists but isn't managed by chezmoi.

**Pros:** One repo; preserves full git history; no new GitHub repo to create; no split-repo coordination overhead.

**Cons:** The repo was not designed for this. `conffiles/` currently contains `.oh-my-zsh/` (a full framework install that should not be chezmoi-managed), `.emacs.d/` (ELPA packages, not config), and historical detritus like `.gitconfig.old` and `.shell.pre-oh-my-zsh`. You'd be converting a repo that was already not working into a chezmoi source directory, carrying all its accumulated cruft. More critically: the non-dotfile content in `sysadmin_files` (`utilities/`, `llm_files/`, `data_collection/`, `dockerfiles/`) has no business being in a dotfiles repo. Dotfiles tools are designed around the assumption that the source repo contains only home-directory files. Mixing sysadmin scripts and LLM templates into the same repo creates confusion about what the repo is and makes the chezmoi source layout harder to reason about.

### Option B: New chezmoi repo, retire sysadmin_files dotfiles

Create a fresh `dotfiles` repo (private on GitHub). Migrate only the dotfiles from the high-priority list below into chezmoi. Keep `sysadmin_files` as a scripts/reference repo for `utilities/`, `data_collection/`, `dockerfiles/`, `llm_files/` — but stop expecting it to manage dotfiles. Two repos with clean responsibilities.

**Workflow:** `chezmoi init` locally, `chezmoi add` each dotfile from the candidate list, push to a new `dotfiles` repo. On uhet: `chezmoi init --apply git@github.com:kaybenleroll/dotfiles.git`. The sysadmin_files repo stays alive but its `conffiles/` directory becomes a historical artifact — either delete it or leave it in place, it no longer does anything.

**Pros:** Clean start. The chezmoi source dir contains exactly and only what chezmoi manages. The `sysadmin_files` repo retains a coherent identity (scripts and templates) without being contaminated by dotfile management responsibilities. Chezmoi's source layout stays readable. No need to untangle `.oh-my-zsh/` or legacy backups from the migration path.

**Cons:** Two repos instead of one. Some files currently in `sysadmin_files/conffiles/` (e.g. `.Rprofile`, `.condarc`, `.psqlrc`) need a decision: migrate to chezmoi, or leave in sysadmin_files as-is. This is a feature, not a bug — it forces an explicit inventory rather than bulk-importing old files.

### Option C: Keep sysadmin_files as-is, add chezmoi separately

Use chezmoi only for `~/.claude/` config (the urgent, untracked use case). Leave everything else unchanged.

**Workflow:** Minimal — `chezmoi init`, add `~/.claude/` files only, push to a small dedicated repo or incorporate into sysadmin_files.

**Pros:** Lowest friction. Solves the immediate `~/.claude/` tracking problem without touching the existing messy state.

**Cons:** Doesn't solve the drift problem. `.zshrc`, `.gitconfig`, and the rest remain untracked and continue diverging. You'd have partial chezmoi coverage alongside an inactive sysadmin_files repo — two half-solutions that together form no solution.

---

## Recommendation

**Option B.** Create a new `dotfiles` repo; migrate the dotfile candidates below into chezmoi; let sysadmin_files live on as a scripts/reference repo without dotfile responsibilities.

The central reason to prefer B over A: `sysadmin_files` was already failing at its stated purpose before this migration began. The symlink installer was never run; both machines drifted; the repo accumulated content (`oh-my-zsh/`, `.emacs.d/ELPA packages`, `.gitconfig.old`) that should never be in a dotfiles manager. Converting it to chezmoi means inheriting all of that baggage and spending migration effort on files that should be excluded, not migrated. A fresh start with an explicit candidate list is less work, not more.

The reason to prefer B over C: the drift in `.zshrc` and `.gitconfig` is already real. The preexec/precmd race is a correctness fix; the credential helper and `log.date` additions are durable workflow preferences. These belong under version control. Solving only `~/.claude/` tracking while leaving shell and git config untracked creates a false sense of coverage.

`sysadmin_files` doesn't disappear. It retains real value as the home for `utilities/`, `llm_files/` prompt templates, `dockerfiles/`, and `data_collection/` Perl scripts. That content has nothing to do with dotfiles management and chezmoi should never touch it.

---

## What Goes in chezmoi

### Track immediately (high value, machine-independent)

| File | Notes |
|------|-------|
| `~/.zshrc` | Full oh-my-zsh config; has drifted ahead of repo — use live version |
| `~/.zshenv` | EDITOR, PAGER, PATH additions |
| `~/.zsh_aliases` | Rich alias set (SSH, ytdl, AI tools, sfw wrappers) |
| `~/.bashrc` | Bash equivalent of zshrc |
| `~/.bash_aliases` | Bash alias subset |
| `~/.bashenv` | Bash env vars + SSH_AUTH_SOCK logic |
| `~/.bash_profile` | Thin wrapper |
| `~/.profile` | Standard login PATH |
| `~/.tmux.conf` | Non-trivial: 50k scrollback, mouse, custom splits, base-index 1 |
| `~/.emacs` | MELPA, backup redirect, ido, hooks |
| `~/.emacs.mini` | Stripped variant |
| `~/.pam_environment` | Irish locale (en_IE.UTF-8, A4 paper) |
| `~/.config/gh/config.yml` | gh aliases (`co`, `prv`), git_protocol; **not** `hosts.yml` |
| `~/.config/btop/btop.conf` | Customised layout |
| `~/.config/htop/htoprc` | Likely customised |
| `~/.claude/CLAUDE.md` | Global CC instructions |
| `~/.claude/SOUL.md` | Behaviour doc |
| `~/.claude/keybindings.json` | Key bindings |
| `~/.claude/rules/` | Project rules files (add individually, not recursive) |

### Track with templating (needs `{{ .chezmoi.homeDir }}` or hostname conditionals)

| File | What to template |
|------|-----------------|
| `~/.gitconfig` | Could contain email that differs by machine; at minimum note the personal/work email toggle |
| `~/.ssh/config` | References `~/.ssh/id_ed25519` — use `{{ .chezmoi.homeDir }}`; also contains GCE auto-section (see Gotchas) |
| `~/.config/mise/config.toml` | Tool paths may be home-relative |
| `~/.claude/settings.json` | **7 hardcoded `/home/mcooney/` paths** in `permissions.allow`, `hooks`, and `statusLine.command` — replace with `{{ .chezmoi.homeDir }}/` |

### Evaluate separately (secrets, auto-generated, or framework installs)

| File | Reason |
|------|--------|
| `~/.claude.json` / `~/.claude.json.backup` | API credentials — never track |
| `~/.ssh/id_*` (all private keys) | Machine-specific secrets — never track |
| `~/.gnupg/` | GPG keyrings — never track |
| `~/.config/gh/hosts.yml` | OAuth token — never track |
| `~/.config/rclone/rclone.conf` | Remote credentials — never track |
| `~/.gemini/`, `~/.gemini-personal/`, `~/.gemini-work/` | Google API credentials — never track |
| `~/.azure/`, `~/.config/gcloud/` | Cloud credentials — never track |
| `~/.oh-my-zsh/` | Framework install — bootstrap via install script, not chezmoi |
| `~/.emacs.d/` | ELPA packages are runtime, not config; only track `~/.emacs` and `~/.emacs.mini` |
| `~/.config/user-dirs.dirs` | XDG paths may legitimately differ per machine |
| `~/.aider/` | Check for API keys before adding |
| `~/.claude/` runtime dirs | `backups/`, `sessions/`, `projects/` (JSONL transcripts), `cache/`, `store/`, `ide/` — never add recursively |

---

## Migration Steps

These steps assume Option B: new `dotfiles` repo on GitHub (`kaybenleroll/dotfiles` — create it first as a private repo).

### 1. Capture the live state before doing anything

```bash
# Confirm live .zshrc is ahead of repo (it is — use it):
diff ~/.zshrc ~/sysadmin_files/conffiles/.zshrc

# Same for .gitconfig:
diff ~/.gitconfig ~/sysadmin_files/conffiles/.gitconfig
```

The live files on skikk are canonical. The sysadmin_files repo is behind on both.

### 2. Install chezmoi

```bash
sh -c "$(curl -fsLS get.chezmoi.io)"
```

### 3. Initialise an empty source directory

```bash
chezmoi init
# Creates ~/.local/share/chezmoi/ as an empty git repo
```

### 4. Create `.chezmoi.toml.tmpl`

```bash
$EDITOR ~/.local/share/chezmoi/.chezmoi.toml.tmpl
```

Minimal content:

```toml
{{- $hostname := .chezmoi.hostname -}}

[data]
    hostname = {{ $hostname | quote }}
```

### 5. Add files in priority order

Add shell and editor configs first — these are the ones that have drifted and need tracking most urgently:

```bash
# Shell config — use live versions (they're ahead of sysadmin_files)
chezmoi add ~/.zshrc ~/.zshenv ~/.zsh_aliases
chezmoi add ~/.bashrc ~/.bash_aliases ~/.bash_profile ~/.bashenv ~/.profile
chezmoi add ~/.tmux.conf ~/.emacs ~/.emacs.mini ~/.pam_environment

# Git — add as template in case email differs on future machines
chezmoi add --template ~/.gitconfig

# SSH — config only, never keys
chezmoi add ~/.ssh/config
# (chezmoi auto-creates private_dot_ssh/ with 0700 perms)

# Tool configs
chezmoi add ~/.config/gh/config.yml
chezmoi add ~/.config/btop/btop.conf
chezmoi add ~/.config/htop/htoprc
chezmoi add ~/.config/mise/config.toml

# Claude Code — specific files only, never recursive
chezmoi add ~/.claude/CLAUDE.md
chezmoi add ~/.claude/SOUL.md
chezmoi add ~/.claude/keybindings.json
# Add rules/ files individually:
find ~/.claude/rules -type f | xargs -I{} chezmoi add {}

# settings.json — add as template
chezmoi add --template ~/.claude/settings.json
```

### 6. Edit the settings.json template

```bash
# Replace all hardcoded home paths:
sed -i 's|/home/mcooney/|{{ .chezmoi.homeDir }}/|g' \
  ~/.local/share/chezmoi/dot_claude/settings.json.tmpl

# Verify it's valid JSON after template render:
chezmoi execute-template < ~/.local/share/chezmoi/dot_claude/settings.json.tmpl \
  | python3 -m json.tool
```

### 7. Create `.chezmoiignore`

```bash
$EDITOR ~/.local/share/chezmoi/.chezmoiignore
```

Contents:

```
# SSH — private keys and runtime files
private_dot_ssh/id_*
private_dot_ssh/authorized_keys
private_dot_ssh/known_hosts

# Claude Code — runtime directories (never add these)
dot_claude/backups
dot_claude/sessions
dot_claude/projects
dot_claude/cache
dot_claude/store
dot_claude/ide
dot_claude/*.log
dot_claude/.credentials.json
```

### 8. Verify before committing

```bash
chezmoi diff    # should show nothing (files already match live state on skikk)
chezmoi status  # all managed files should be clean
```

### 9. Push to the new repo

```bash
chezmoi cd
git add -A
git commit -m "initial: chezmoi dotfiles from skikk"
git remote add origin git@github.com:kaybenleroll/dotfiles.git
git push -u origin main
```

### 10. Handle the sysadmin_files relationship

No immediate action required on `sysadmin_files`. The `conffiles/` subdirectory becomes a historical artifact. Optionally, to make the split explicit:

```bash
# In sysadmin_files, mark conffiles/ as deprecated:
git -C ~/sysadmin_files rm -r --cached conffiles/
git -C ~/sysadmin_files commit -m "remove conffiles: dotfiles now managed by chezmoi in kaybenleroll/dotfiles"
```

Or leave `conffiles/` in place — it won't conflict with chezmoi since chezmoi's source directory is `~/.local/share/chezmoi/`, entirely separate from `~/sysadmin_files/`.

### 11. Bootstrap uhet

On uhet, the situation is: regular files (not symlinks), 2 commits behind skikk in sysadmin_files, and some configs (`.zsh_aliases`, `.zshenv`) not present because the zsh migration happened after uhet was last updated.

```bash
# Install chezmoi and clone the dotfiles repo (don't apply yet):
sh -c "$(curl -fsLS get.chezmoi.io)" -- init git@github.com:kaybenleroll/dotfiles.git

# Review what would change before applying:
chezmoi diff

# Expect: uhet's .zshrc will differ (smaller, missing plugins).
# The skikk version in chezmoi is the one you want — chezmoi source wins.
# For any file where uhet has uhet-specific config you want to keep,
# decide before applying.

# Apply once satisfied:
chezmoi apply
```

The `settings.json.tmpl` template will render correctly on uhet because `.chezmoi.homeDir` resolves to `/home/mcooney` there too. The 7 previously hardcoded paths will be identical on both machines.

### Ongoing workflow

```bash
# After editing a tracked file in place:
chezmoi re-add ~/.some/config

# After editing via chezmoi source:
chezmoi edit ~/.some/config   # opens source file in $EDITOR
chezmoi apply                 # propagates to home dir

# Pull changes from remote and apply (uhet or any machine):
chezmoi update

# Commit and push current state:
chezmoi cd && git add -A && git commit -m "..." && git push
```

---

## Gotchas Specific to This Setup

**`.oh-my-zsh/` is tracked in sysadmin_files — don't migrate it.**
The repo includes a full oh-my-zsh install. This is a framework with its own git repo, not user config. On any new machine, install it with `sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"` and let it manage itself. If you add it to chezmoi you will be tracking thousands of framework files that auto-update separately, creating perpetual chezmoi drift.

**SSH `config` has a GCE auto-managed section.**
`gcloud compute config-ssh` appends a `# Added by google-cloud-sdk` block to `~/.ssh/config`. This block contains ephemeral instance entries and changes every time you run it. Options: (a) make `~/.ssh/config` a template and keep only the static Named hosts section, with a comment that the GCE block is managed by gcloud; (b) accept that `chezmoi diff` will always show the GCE section as an "extra" on any machine where gcloud has run — chezmoi won't remove it (non-exact mode), it just won't be in the source. Option (b) is usually fine unless you want the GCE entries to propagate across machines.

**`~/.claude/` runtime writes will cause false chezmoi divergence.**
Claude Code rewrites `settings.json` when you change settings via the UI. After any such UI-driven change, `chezmoi diff` will show `settings.json` as modified. This is correct behaviour — it means your in-repo version and the live version differ. Workflow: after an intentional settings change, run `chezmoi re-add ~/.claude/settings.json && chezmoi cd && git commit -m "update settings"` to capture it. Never run `chezmoi apply` blindly on `settings.json` without checking the diff first.

**`~/.claude/` rules/ subdirectory.**
`~/.claude/rules/` contains project-specific rules files that have been promoted to global rules. Add these individually with `chezmoi add`, not `chezmoi add --recursive ~/.claude/` which would sweep in runtime state. The `skill-hygiene.md` file in the project-level `.claude/rules/` is already tracked in its project repo; the global one in `~/.claude/rules/` is what belongs in chezmoi.

**`.emacs.d/` in sysadmin_files contains ELPA packages.**
Don't migrate `.emacs.d/` — it contains compiled ELPA packages that are platform-specific and managed by Emacs's own package system. Migrate only `~/.emacs` (which installs packages on first run via the MELPA config it contains) and `~/.emacs.mini`.

**`settings.json` absolute paths — same username on both machines means this is not a blocking problem today.**
Both skikk and uhet use username `mcooney`, so the 7 hardcoded `/home/mcooney/` paths in `settings.json` will resolve identically on both machines even without templating. The template conversion in Step 6 is the right thing to do for correctness and forward compatibility (third machine, different username), but if you want to get chezmoi running before tackling it, the raw file will work on uhet as-is.
