# system_queries — SKIKK Thor 16 admin workspace

## Machine
SKIKK Thor 16 (Tongfang GM6HG7Y) · AMD Ryzen 9 9955HX3D · RTX 5070 Ti (Blackwell GB203M)
Ubuntu 26.04 LTS · kernel 6.17.0-23-generic · nvidia-open 580.126.09 · tuxedo-drivers 4.22.2

## Hard constraints
- **Keep `pcie_aspm=force` with `pcie_aspm.policy=default`** — `force` is required for s2idle (PCIe root ports cannot gate power without it); `policy=default` avoids over-aggressive L1 on remaining devices. Original r8125 hard-freeze resolved by blacklisting the driver — if NIC is ever re-enabled, test `policy=default` carefully before considering `powersave`
- **This system has no `/etc/default/grub`** — GRUB is configured exclusively via `/etc/default/grub.d/` drop-ins; after any `update-grub` run, verify `/proc/cmdline` on next boot to confirm all params survived
- **BIOS updates may change the DSDT** — check NVPCF fix status after any firmware update; the current initrd override is superseded (BIOS Dec 2025 already contains the empty-method fix) and harmless but not active (kernel rejects it as OEM revision is not greater)

## Active fixes
| Fix | File | Status |
|-----|------|--------|
| NVPCF D3cold storm (nvidia-open bug) | `.scratch/nvpcf_fix.asl` → `/boot/nvpcf_override.cpio` | Superseded |
| pm_runtime_work freeze (Blackwell + fine-grained PM) | `/etc/modprobe.d/nvidia-power.conf` | Live |
| pm_runtime_work cmdline override (definitive fix) | `/etc/default/grub.d/99-nvidia-pm.cfg` | Live |
| Platform cmdline params (pcie_aspm, amd_pstate, nvidia-drm) | `/etc/default/grub.d/10-skikk-platform.cfg` | Live |
| r8125/r8169 NIC disabled (ASPM ESD ~250/day) | `/etc/modprobe.d/blacklist-r8125.conf` | Live |
| Gemini wrong-fix artifacts | Deleted | Done |
| GRUB cleanup (wrong CPIO, stale flags) | `.scratch/grub_cleanup.sh` | Done |
| GNOME suspend triggers disabled (power-button/lid s2idle freeze) | `gsettings` (power-button-action, lid-close-*-action = 'nothing') | Live |
| logind suspend/hibernate key ignored (defense-in-depth) | `.scratch/logind_suspend_key_fix.sh` → `/etc/systemd/logind.conf.d/98-suspend-key.conf` | Pending sudo+reboot |
| unattended-upgrades honours mozillateam PPA pin (firefox downgrade ping-pong) | `/etc/apt/apt.conf.d/50unattended-upgrades` (`Allowed-Origins` += `LP-PPA-mozillateam`) | Live |

**NVPCF fix status:** superseded by BIOS (Dec 2025 fixes it natively); initrd override harmless but inert. Full detail: `doc/machine-history.md` §2.16.

**pm_runtime_work fix:** cmdline param is the definitive fix (modprobe.d alone was insufficient — cmdline takes precedence over modprobe.d load order). Revert trigger: nvidia-open 610.x+ fixing Blackwell RTD3/D3cold. Full detail: `doc/machine-history.md` §2.17.

**s2idle suspend freeze (2026-07-09):** GNOME's power daemon has a suspend trigger path independent of `logind.conf`'s `HandleLidSwitch` — both must be disabled. Fixed live (GNOME) + logind drop-in staged (pending sudo+reboot). Full detail and recovery steps: `doc/machine-history.md` §2.18.

**yt6801 out-of-tree taint (2026-07-10):** Motorcomm NIC driver (TUXEDO DKMS bundle), loaded but inert — no matching PCI hardware on this chassis (RTL8125 only), 0 refcount. Taint is a DKMS/MOK signing artifact, no functional impact (Secure Boot disabled). Blacklisting recommended but not yet applied — needs sign-off. Full detail: `doc/machine-history.md` §2.19.

**NVRM `nvAssertFailedNoLog` boot assertions (2026-07-10):** 3x at ~18s post nvidia-drm init, different code path than the §2.17/§2.18 bugs, boot-only, no freeze followed. Monitoring only. Full detail: `doc/machine-history.md` §2.20.

**Firefox "downgrade" on `apt full-upgrade`, fixed (2026-07-23):** not a real regression — Ubuntu's own repo ships a snap-stub firefox with an epoch-prefixed version (`1:1snap1-...`) that always outranks the real mozillateam-PPA build in version comparison, so apt reports reverting to the PPA build as a "downgrade". `unattended-upgrades` wasn't honouring the PPA's priority-1001 pin, causing repeated ping-pong between the stub and the real build. Fixed by adding the PPA origin to `unattended-upgrades`' `Allowed-Origins`. Full detail: `doc/machine-history.md` §2.25.

**Stremio x265/HEVC black screen (2026-07-13):** Chrome has no HEVC decoder on Linux (RealDebrid links bypass Stremio's server-side transcode, so this is the full explanation, not just a contributing factor); Flathub's "stable" Stremio Flatpak is the broken NVIDIA/wgpu shell (`stremio-linux-shell #30`), reconfirmed dead, uninstalled. **Working fallback:** grab the resolved URL from `podman logs stremio-server` (`opensubHash?videoUrl=...` line) → `mpv <url>` (NVDEC now default via `~/.config/mpv/mpv.conf`) — confirmed real GPU decode via `nvidia-smi`. Automated browser→mpv handoff (Tampermonkey userscript + `mpv-handler`) installed but not working yet — userscript's CSS selector likely stale, parked mid-debug. Full detail: `doc/machine-history.md` §2.21.

**ExpressVPN journal flood, resolved (2026-07-16):** `journal-watch.sh` alerted on a 52K-line/10-min spike; root cause was an IPC "payload too large" bug in the installed `4.1.1-beta+10039` client cascading into thousands of parse errors. Recurred 2026-07-13 and 2026-07-16 (661K entries over 7 days). Fixed by updating to `14.2.0+13656` via the official installer (no apt repo configured) — flood confirmed stopped post-update. If it recurs on 14.2.0, it's a new bug. Full detail: `doc/machine-history.md` §2.23.

**VS Code Remote-SSH crashes to uhet, workaround only (2026-07-17):** intermittent renderer SIGABRT + extension host crash tied to a VS Code core transport bug (malformed JSON on the remote socket) plus an unrelated known Copilot Chat chatParticipant bug. Kill+relaunch (`pkill -f '/usr/share/code/'`) clears it short-term; root cause unresolved. Full detail: `doc/machine-history.md` §2.24.

## File layout
```
acpi/                       — DSDT firmware artifacts (dsdt.dsl source, dsdt.dat binary, nvpcf_fix.asl patch)
doc/                        — decision logs, runbooks, machine history
SKIKK_Thor_ASPM_Bug_Report.md  — r8125 ASPM crash bug report filed with SKIKK (historical; see Resolution section)
.scratch/                   — all working files, scripts, outputs
```

## Working approach
- **When a session diagnoses or fixes a machine/system-specific issue, document it directly in this repo's own docs in the same session — don't defer to the `/reflect` learnings queue for this.** CLAUDE.md is loaded into every turn's context regardless of relevance, so it stays terse: a one-line Active fixes table row or Known-quirks bullet, plus a pointer (e.g. `doc/machine-history.md §2.N`). The narrative — root cause, what was tried, revert steps — goes in `doc/machine-history.md` as a new dated `§2.N` decision-log entry (or a standalone `doc/decision-<topic>.md` for a large self-contained investigation), read on demand rather than paid for every turn.
- All temp and output files go in `.scratch/` — never `/tmp/`
- Scripts that need root use `sudo` internally; run them as `bash .scratch/script.sh`, not `sudo bash`
- Subagents do implementation; this session orchestrates
- Check DSDT OEM revision (offset 24-28, not 32-36 which is Creator Revision): `sudo python3 -c "import struct; hdr=open('/sys/firmware/acpi/tables/DSDT','rb').read(36); rev=struct.unpack('<I',hdr[24:28])[0]; print(hex(rev))"` — firmware is `0x01072009` (Dec 2025 BIOS; Python prints as `0x1072009` with leading zero dropped)

## Recurring operations

**"Do a comprehensive health check"** → `just health-all`
Runs full diagnostics + SMART + security. Some checks require sudo — if the session can't authenticate, bundle them: write `.scratch/health_sudo.sh` and ask the user to run `sudo bash .scratch/health_sudo.sh`. The sudo checks are: DSDT OEM revision, dmesg nvidia-PM events, UFW status, smartctl on both NVMe drives.

### Health targets
`health-all` calls all 9 domains in sequence. `health-save` saves `health-all` output to a timestamped file in `logs/`.

| Target | Domain | Sudo |
|--------|---------|------|
| `health-quick` | 5 key spot-checks (failed units, GPU PM, ASPM, D3cold, disk) | partial |
| `health-full` | Core hardware/firmware (depends on health-quick) | yes |
| `health-boot` | Uptime, boot time, installed kernels, pending reboot, coredumps, failed timers | no |
| `smart-check` | NVMe SMART diagnostics on both drives | yes |
| `security-check` | UFW firewall, external listeners, SSH hardening | yes |
| `health-packages` | Upgradable packages, security updates, purge candidates, disabled snaps | no |
| `health-containers` | Podman disk usage, dangling images, stopped containers | no |
| `health-cruft` | Home dir sizes (Downloads/.cache/Trash/containers), files >500 MB | no |
| `health-journal` | Journal error counts (24h/7d), failed SSH login attempts | no |
| `health-network` | Active connections, WiFi signal, DNS resolution, ethernet state | no |
| `health-all` | Calls all 9 above — **use this for "do a health check" requests** | yes |
| `health-save` | Saves `health-all` output to `logs/health-TIMESTAMP.txt` | yes |
| `health-snapshot` | Append one metrics row to `logs/health-metrics.tsv` (trend tracking) | no |

### Other common targets
| Target | What it does |
|--------|-------------|
| `temps` | CPU / GPU / DIMM temperatures |
| `gpu-pm-status` | Verify GPU PM fix is active (should show `0x01`) |
| `aspm-status` | Verify PCIe ASPM policy |
| `disk-usage` | Storage consumers in /home and /var |
| `journal-trim` | Vacuum journal to 30 days then show size |
| `pkg-upgrade` | Update and upgrade packages |
| `pkg-purge` | Purge removed-package config leftovers |
| `snap-clean` | Remove disabled snap revisions |
| `stremio` | Start Stremio server + Chrome |
| `stremio-stop` | Stop Stremio server |

### Journal size
Journald runs on defaults — no `SystemMaxUse` set, but systemd auto-caps at ~4 GB. On a 921 GB root this is fine; 1–2 GB is normal. Run `just journal-trim` to vacuum to 30 days if it looks large. Only add a `SystemMaxUse` drop-in if a specific service is generating log spam.

When the journal is pinned at its size cap and self-vacuuming, disk-usage checks report 0 growth regardless of actual write rate — detect real journal growth via log volume per interval (e.g. `journalctl` line counts), not disk usage.

A journal anomaly threshold calibrated for one check interval doesn't transfer to a different interval — rescale it proportionally when changing check frequency, or a shortened interval (e.g. hourly to 10-minute) loses sensitivity and a lengthened one generates false positives.

## Known platform quirks
- GPE07 fires ~320/sec (EC Dynamic Boost polling) — hardware characteristic, not a bug
- `ite_8291` logs 125 LED rename warnings at boot — cosmetic, RGB driver issue
- `NVreg_EnableGpuFirmware=0` in modprobe.d is silently ignored (GSP mandatory on Blackwell)
- Battery cycle count always reads 0 — EC doesn't expose wear data
- `yt6801` (Motorcomm NIC driver, TUXEDO DKMS bundle) loads and taints kernel at every boot but binds to no hardware on this chassis — cosmetic, see `doc/machine-history.md` §2.19
- `NVRM: nvAssertFailedNoLog @ osapi.c:1939` x3 at boot, ~18s after nvidia-drm init — logged-only, no freeze observed, see `doc/machine-history.md` §2.20
- **r8125/r8169 blacklisted** — `pcie_aspm=force` caused ~250 ESD recovery events/day even with no cable connected. NIC is unused (WiFi only). Blacklist at `/etc/modprobe.d/blacklist-r8125.conf`. To re-enable: `sudo rm /etc/modprobe.d/blacklist-r8125.conf && sudo update-initramfs -u -k all && reboot`.
- **io_uring/podman hung-task warnings (unconfirmed, monitoring)** — kernel hung-task warnings (ioq worker threads blocked 122–368s on mutex, kernel tainted G W OE) correlating with container creation failures (conmon exit 255) and container churn. Observed 2026-07-06 and 2026-07-09 (health-save log). Unlike the other quirks above, not yet confirmed benign/expected — watch for recurrence.
- UFW block-log volume spikes from routine LAN neighbour discovery/broadcast traffic (e.g. KDE Connect port 1716, SSDP/mDNS) are expected noise from active LAN hosts, not an attack signal
- HP USB-C dock: display and ethernet don't work (USB peripherals do) — dock uses HP's proprietary MUX alt-mode (SVID `03f0`), not standard DP Alt-Mode; HP ships no Linux driver, no fix exists. See `doc/machine-history.md` §2.22

- rclone's `--fast-list` is a no-op on `rclone mount` (rclone logs a NOTICE) — it only speeds up one-shot commands (sync/copy). To reduce directory cache stalls on a live mount, tune `--dir-cache-time` instead.
- Any package pinned to priority ≥1000 in `/etc/apt/preferences.d/` (e.g. mozilla-firefox → `LP-PPA-mozillateam`) must have its PPA origin added to `Unattended-Upgrade::Allowed-Origins` in `/etc/apt/apt.conf.d/50unattended-upgrades`, or unattended-upgrades will silently install the unpinned (lower-priority, possibly epoch-inflated) alternative on its own schedule and the next manual `apt full-upgrade` will "downgrade" it back — a ping-pong, not a real regression. When adding or reviewing a pin file under `preferences.d/`, cross-check `50unattended-upgrades`' `Allowed-Origins` for the matching origin (find it via `apt-cache policy <pkg>` or the source's `Release` file `Origin:` field). See `doc/machine-history.md` §2.25.

## tmux / Byobu
- Byobu bypasses `~/.tmux.conf` entirely — it launches via its own profile chain and hardcodes `mouse off`/other overrides (e.g. `/usr/share/byobu/keybindings/mouse.tmux.enable` sets `set -g mouse off` despite the filename) and only sources user config from `~/.config/byobu/.tmux.conf` (or its chezmoi-managed template), loaded last. Put tmux settings there, not in `~/.tmux.conf`.
- tmux silently no-ops `run`/`run-shell` when the referenced file (e.g. a missing tpm plugin manager) doesn't exist — no error or status-bar message. If a tmux config feature isn't working, verify the referenced path actually exists before assuming the config itself is broken.
