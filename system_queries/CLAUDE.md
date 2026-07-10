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

**NVPCF fix status (Jun 2026):** BIOS Dec 2025 ships `\_SB.INOU.PWUP` as an empty method — the same fix our DSDT patch applied. The initrd override is no longer needed. The kernel rejects our cpio anyway (OEM revision equal, not greater) so it's harmless to leave in place.

**pm_runtime_work fix (Jun 2026):** `NVreg_DynamicPowerManagement=0x01` (coarse-grained) set in `/etc/modprobe.d/nvidia-power.conf` and `/etc/modprobe.d/nvidia.conf`. Fine-grained (`0x02`) causes pm_runtime_work callbacks to block the system workqueue on Blackwell GB203M, eventually hard-freezing the machine. Root cause: nvidia-open 580.126.09 (upgraded May 3 2026) introduced a bug in `rm_acpi_nvpcf_notify()` — calls `os_ref_dynamic_power()` unconditionally without D3Cold state check. Fix is in community PR #1181 (open-gpu-kernel-modules, filed Jun 6 2026, unmerged as of Jun 24 2026). Latest available driver: 595.84 (Jun 17 2026) — does not contain the fix. **The modprobe.d fix alone was insufficient** — machine froze twice with it active (Steam loading nvidia-drm was the trigger); `cmdline` parameter takes absolute precedence over all modprobe.d load order. Definitive fix applied Jun 24 2026: `/etc/default/grub.d/99-nvidia-pm.cfg` sets `GRUB_CMDLINE_LINUX_DEFAULT` to include `nvidia.NVreg_DynamicPowerManagement=0x01`. **Revert when nvidia-open fixes Blackwell runtime PM** — watch 610.x+ release notes for "NVPCF", "RTD3", or "D3cold" fix, then: `sudo rm /etc/modprobe.d/nvidia-power.conf /etc/default/grub.d/99-nvidia-pm.cfg`, revert `nvidia.conf` to `0x02`, run `sudo update-grub && sudo update-initramfs -u -k all`, and reboot.

**s2idle suspend freeze via power/lid triggers (2026-07-09):** A spurious power/sleep-key input event (source unconfirmed — candidates: the "2.4G Mouse System Control" wireless dongle glitching, or ACPI/EC noise, given GPE07's already-documented high firing rate; ruled out: no GNOME keybinding maps to a suspend/lock action that could explain it, and `turbo-whisper`'s hotkey is `Ctrl+Space` not the key the user pressed) triggered `systemd-logind` → `The system will suspend now!`. `nvidia-suspend.service` then hit the same Blackwell s2idle bug as the pm_runtime_work freeze above — `NVRM: nvAssertFailedNoLog` MMU-walk assertion failures during GPU memory teardown — and the machine never resumed: both displays went blank while the CPU kept running, ending in a kernel soft-lockup (`Xwayland` stuck 26s+) ~34s after the suspend request. Required a hard reset; nothing else was logged afterward. Root gap: `logind.conf` only had `HandleLidSwitch*=ignore` — `HandleSuspendKey` was never set, and **GNOME's own power daemon has an independent trigger path** (`org.gnome.settings-daemon.plugins.power` `power-button-action`/`lid-close-*-action`, both still `'suspend'`) that `logind.conf`'s `HandleLidSwitch=ignore` does *not* cover — GNOME can request suspend on lid-close or power-button press regardless of the logind-level setting. Fixed by setting all three GNOME actions to `'nothing'` (live, no reboot) and staging a `HandleSuspendKey=ignore`/`HandleHibernateKey=ignore` logind drop-in for defense-in-depth (needs sudo+reboot, not yet applied — see Active fixes table). **If this recurs:** blank screens + machine still powered on this hardware means a hung s2idle resume, not a hang worth waiting out — hard power-cycle is the only recovery; try SSH from another device first if convenient, since this was a soft lockup (not a full panic) and another CPU may still answer.

## File layout
```
acpi/                       — DSDT firmware artifacts (dsdt.dsl source, dsdt.dat binary, nvpcf_fix.asl patch)
doc/                        — decision logs, runbooks, machine history
SKIKK_Thor_ASPM_Bug_Report.md  — r8125 ASPM crash bug report filed with SKIKK (historical; see Resolution section)
.scratch/                   — all working files, scripts, outputs
```

## Working approach
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
- **r8125/r8169 blacklisted** — `pcie_aspm=force` caused ~250 ESD recovery events/day even with no cable connected. NIC is unused (WiFi only). Blacklist at `/etc/modprobe.d/blacklist-r8125.conf`. To re-enable: `sudo rm /etc/modprobe.d/blacklist-r8125.conf && sudo update-initramfs -u -k all && reboot`.
- **io_uring/podman hung-task warnings (unconfirmed, monitoring)** — kernel hung-task warnings (ioq worker threads blocked 122–368s on mutex, kernel tainted G W OE) correlating with container creation failures (conmon exit 255) and container churn. Observed 2026-07-06 and 2026-07-09 (health-save log). Unlike the other quirks above, not yet confirmed benign/expected — watch for recurrence.

- rclone's `--fast-list` is a no-op on `rclone mount` (rclone logs a NOTICE) — it only speeds up one-shot commands (sync/copy). To reduce directory cache stalls on a live mount, tune `--dir-cache-time` instead.

## tmux / Byobu
- Byobu bypasses `~/.tmux.conf` entirely — it launches via its own profile chain and hardcodes `mouse off`/other overrides (e.g. `/usr/share/byobu/keybindings/mouse.tmux.enable` sets `set -g mouse off` despite the filename) and only sources user config from `~/.config/byobu/.tmux.conf` (or its chezmoi-managed template), loaded last. Put tmux settings there, not in `~/.tmux.conf`.
- tmux silently no-ops `run`/`run-shell` when the referenced file (e.g. a missing tpm plugin manager) doesn't exist — no error or status-bar message. If a tmux config feature isn't working, verify the referenced path actually exists before assuming the config itself is broken.
