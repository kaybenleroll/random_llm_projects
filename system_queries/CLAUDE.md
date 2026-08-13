# system_queries — multi-machine Linux admin workspace

## File layout
```
doc/                        — decision logs, runbooks, machine history, doc/machines/<slug>.md per-machine context
.scratch/                   — all working files, scripts, outputs
```

## Working approach
- **When a session diagnoses or fixes a machine/system-specific issue, document it directly in the same session — don't defer to the `/reflect` learnings queue for this.** Route findings to `doc/machines/<slug>.md` for the machine named by the injected `<!-- machine-context: <slug> -->` sentinel; if no sentinel was injected, stop and fix the registry rather than guessing which machine's file to edit. Keep the entry there terse: a one-line Active fixes table row or Known-quirks bullet, plus a pointer (e.g. `doc/skikk-thor-history.md §2.N`). The narrative — root cause, what was tried, revert steps — goes in that machine's own history doc (e.g. `doc/skikk-thor-history.md` for skikk-thor) as a new dated `§2.N` decision-log entry (or a standalone `doc/decision-<topic>.md` for a large self-contained investigation), read on demand rather than paid for every turn.
- All temp and output files go in `.scratch/` — never `/tmp/`. Exception: a script meant to run *after* `wsl --shutdown`, or handed to the user as a native Windows/PowerShell script, must live on the Windows filesystem (e.g. under `/mnt/c/...`), not `.scratch/` — `.scratch/` is inside the WSL filesystem and becomes unreachable (`\\wsl.localhost\...` unmounts) the moment the shutdown it's meant to survive happens.
- Scripts that need root use `sudo` internally; run them as `bash .scratch/script.sh`, not `sudo bash`
- Subagents do implementation; this session orchestrates
- This repo's disposable scratch layer (`.scratch/` contents, one-off diagnostic scripts) is fair game to tear down and rebuild without ceremony. This does **not** extend to `doc/`, `registry.json`, the `.claude/hooks/` machine-context mechanism, or the `Justfile` — those are the load-bearing record and interface (registry resolution, health-check targets tracked in issue #31), not scratch, and the administered machines themselves carry their own real (sometimes hard-to-reverse) risk — see each machine's own Hard constraints.
- This repo's docs have drifted from actual implementation state more than once (a README status line claiming a landed refactor hadn't happened; `doc/machines/skikklaptop.md` describing a container-runtime setup that had since migrated) — verify live state (config files, running processes/services) before trusting a doc's claim, especially right after a refactor or migration.
- After adding, renaming, or removing a Justfile recipe, run `just docs-check` — it diffs recipe names against this file's target tables and flags undocumented or stale rows.

## Recurring operations

**"Do a comprehensive health check"** → `just health-all` on SKIKK Thor 16 only (see `†` legend below); on other machines, run the unmarked targets individually.
Runs full diagnostics + SMART + security. Some checks require sudo — if the session can't authenticate, bundle them: write `.scratch/health_sudo.sh` and ask the user to run `sudo bash .scratch/health_sudo.sh`. On SKIKK Thor 16, the sudo checks are: DSDT OEM revision, dmesg nvidia-PM events, UFW status, smartctl on both NVMe drives — this enumeration does not apply on other machines.

### Health targets
`†` = requires SKIKK Thor 16 hardware; fails or misbehaves off-Thor. Two failure modes: most `†` targets fail outright off-Thor, but `health-journal` and `health-network` hardcode Thor's specific noise filters and NIC assertions, so off-Thor they can return a plausible *wrong* answer rather than failing. As a result `just health-all` fails on WSL (`skikklaptop`) and the headless server (`s3rbase`). Portability tracked in issue #31.

`health-all` calls all 9 domains in sequence. `health-save` saves `health-all` output to a timestamped file in `logs/`.

| Target | Domain | Sudo |
|--------|---------|------|
| `health-quick`† | 5 key spot-checks (failed units, GPU PM, ASPM, D3cold, disk) | partial |
| `health-full`† | Core hardware/firmware, incl. power wakeups (depends on health-quick) | yes |
| `health-boot` | Uptime, boot time, installed kernels, pending reboot, coredumps, failed timers | no |
| `smart-check`† | NVMe SMART diagnostics on both drives | yes |
| `security-check` | UFW firewall, external listeners, SSH hardening | yes |
| `health-packages` | Upgradable packages, security updates, purge candidates, disabled snaps | no |
| `health-containers` | Podman disk usage, dangling images, stopped containers | no |
| `health-cruft` | Home dir sizes (Downloads/.cache/Trash/containers), files >500 MB | no |
| `health-journal`† | Journal error counts (24h/7d), failed SSH login attempts | no |
| `health-network`† | Active connections, WiFi signal, DNS resolution, ethernet state | no |
| `health-all`† | Calls all 9 above — **use this for "do a health check" requests** | yes |
| `health-save`† | Saves `health-all` output to `logs/health-TIMESTAMP.txt` | yes |
| `health-snapshot` | Append one metrics row to `logs/health-metrics.tsv` (trend tracking) | no |

### Other common targets
`†` as above — requires Thor hardware.

| Target | What it does |
|--------|-------------|
| `temps`† | CPU / GPU / DIMM temperatures |
| `gpu-pm-status`† | Verify GPU PM fix is active (should show `0x01`) |
| `power-wakeups`† | `powertop --dump` power-usage/wakeup-count report (read-only, ~15-20s sample; called from health-full) |
| `aspm-status`† | Verify PCIe ASPM policy |
| `fan-performance`† | Switch TCC fan profile to gaming/performance |
| `fan-balanced`† | Switch TCC fan profile to balanced (TUXEDO default) |
| `fan-auto`† | Switch TCC fan profile back to automatic/default |
| `disk-usage` | Storage consumers in /home and /var |
| `journal-trim` | Vacuum journal to 30 days then show size |
| `journal-watch` | Check journal entry-count growth vs last check; warns on unusual volume or cap proximity |
| `logs-cleanup` | Remove `health-save` snapshot files older than 30 days |
| `logs-trim-cron` | Trim `logs/health-snapshot-cron.log` to last 5000 lines if over 5 MB |
| `logs-maintain` | Runs `logs-cleanup` + `logs-trim-cron` together — safe to cron weekly |
| `dotfiles-diff` | Show pending chezmoi dotfile changes |
| `dotfiles-apply` | Apply chezmoi dotfile changes |
| `dotfiles-update` | Pull upstream and apply chezmoi dotfile changes |
| `ports` | List listening TCP/UDP sockets with owning processes |
| `docs-check` | Diff Justfile recipes against this file's target tables — flags undocumented/stale rows |
| `pkg-upgrade` | Update and upgrade packages |
| `pkg-purge` | Purge removed-package config leftovers |
| `snap-clean` | Remove disabled snap revisions |
| `stremio`† | Start Stremio server + Chrome |
| `stremio-server`† | Start Stremio server container only (podman, no Chrome) |
| `stremio-stop`† | Stop Stremio server |

### Journal monitoring
When the journal is pinned at its size cap and self-vacuuming, disk-usage checks report 0 growth regardless of actual write rate — detect real journal growth via log volume per interval (e.g. `journalctl` line counts), not disk usage.

A journal anomaly threshold calibrated for one check interval doesn't transfer to a different interval — rescale it proportionally when changing check frequency, or a shortened interval (e.g. hourly to 10-minute) loses sensitivity and a lengthened one generates false positives.

## Known platform quirks
- rclone's `--fast-list` is a no-op on `rclone mount` (rclone logs a NOTICE) — it only speeds up one-shot commands (sync/copy). To reduce directory cache stalls on a live mount, tune `--dir-cache-time` instead.
- Any package pinned to priority ≥1000 in `/etc/apt/preferences.d/` (e.g. mozilla-firefox → `LP-PPA-mozillateam`) must have its PPA origin added to `Unattended-Upgrade::Allowed-Origins` in `/etc/apt/apt.conf.d/50unattended-upgrades`, or unattended-upgrades will silently install the unpinned (lower-priority, possibly epoch-inflated) alternative on its own schedule and the next manual `apt full-upgrade` will "downgrade" it back — a ping-pong, not a real regression. When adding or reviewing a pin file under `preferences.d/`, cross-check `50unattended-upgrades`' `Allowed-Origins` for the matching origin (find it via `apt-cache policy <pkg>` or the source's `Release` file `Origin:` field).
- When `health-save` snapshots (or any timestamped metrics captures) look identical by timestamp or file size, diff the actual metrics data (wear counters, temperatures, journal line counts) before assuming duplication and deleting files — near-identical size does not mean identical content.
- The legacy Ookla `speedtest-cli` Python client is unreliable — Ookla restricts its API access, returning only distant servers instead of nearby alternatives, yielding false results (e.g. 656ms/1.48Mbit). Use Ookla's official CLI (snap) or the web interface for network diagnostics instead.

## tmux / Byobu
- Byobu bypasses `~/.tmux.conf` entirely — it launches via its own profile chain and hardcodes `mouse off`/other overrides (e.g. `/usr/share/byobu/keybindings/mouse.tmux.enable` sets `set -g mouse off` despite the filename) and only sources user config from `~/.config/byobu/.tmux.conf` (or its chezmoi-managed template), loaded last. Put tmux settings there, not in `~/.tmux.conf`.
- tmux silently no-ops `run`/`run-shell` when the referenced file (e.g. a missing tpm plugin manager) doesn't exist — no error or status-bar message. If a tmux config feature isn't working, verify the referenced path actually exists before assuming the config itself is broken.
