<!-- DRAFT — for review before committing to doc/ -->

# SKIKK Thor 16 — Sysadmin History

_Last updated: 2026-06-16. Written from handover files, CLAUDE.md, and SKIKK_Support_Dossier.md._

---

## 1. Machine Identity

| Item | Value |
|------|-------|
| Brand / chassis | SKIKK Thor 16 · Tongfang GM6HG7Y |
| CPU | AMD Ryzen 9 9955HX3D (Zen 5, 16-core) |
| GPU | NVIDIA RTX 5070 Ti (Blackwell GB203M) |
| Ethernet | Realtek RTL8125 2.5GbE (PCIe ID 10ec:8125) |
| OS | Ubuntu 26.04 LTS |
| Kernel | 6.17.0-23-generic |
| NVIDIA driver | nvidia-open 580.126.09 |
| BIOS revision | Dec 2025 (OEM revision `0x01072009`, ACPI offset 24–28) |
| Tuxedo drivers | tuxedo-drivers DKMS 4.22.2 |

### Known platform quirks (hardware, not bugs)

- GPE07 fires ~320/sec — EC Dynamic Boost polling, hardware characteristic, not a bug.
- `ite_8291` logs 125 LED rename warnings at boot — cosmetic RGB driver issue.
- `NVreg_EnableGpuFirmware=0` in modprobe.d is silently ignored; GSP firmware is mandatory on Blackwell and cannot be disabled.
- Battery cycle count always reads 0 — EC does not expose wear data.
- DIMM 1 reaches 53–54°C under load; high alarm threshold is 55°C. Monitor during memory-intensive work.

---

## 2. Chronological Decision Log

### 2.1 — ACPI RTAC bug and the pcie_aspm=force workaround (pre-May 2026)

**Root cause.** The BIOS shipped with a broken SSDT (`UPEPRPL`). The AMD PEP `_DSM` method referenced `\_SB.ACDC.RTAC`, a symbol that does not exist in the ACPI tables. Every power state transition triggered:

```
ACPI BIOS Error: Could not resolve symbol [\_SB.ACDC.RTAC], AE_NOT_FOUND
ACPI Error: Aborting method \_SB.PEP._DSM due to previous error
```

When `_DSM` aborted, ASPM timing parameters for the Realtek r8125 NIC were never negotiated. The NIC entered an unstable PCIe power state, flooding the bus with AER errors, which caused `watchdog: BUG: soft lockup - CPU stuck for 20s+` and unrecoverable freezes.

**Fix applied.** Added `pcie_aspm=force` to GRUB kernel cmdline. This forces ASPM link negotiation to proceed regardless of the missing firmware hint, allowing r8125 to reach a stable state.

**Constraint created.** `pcie_aspm=force` must remain in the GRUB cmdline until the r8125 ASPM issue is resolved by upstream firmware or driver. Note: `/etc/default/grub` does not exist on this system — GRUB is configured via `/etc/default/grub.d/` drop-ins (`10-skikk-platform.cfg` for platform params, `99-nvidia-pm.cfg` for nvidia PM). Removing `pcie_aspm=force` causes hard ethernet freezes on system state transitions.

---

### 2.2 — NVPCF / D3cold storm from nvidia-open 580.126.09 (May 2026)

**Date.** Driver upgraded to nvidia-open 580.126.09 on approximately 2026-05-03.

**Root cause.** nvidia-open 580.126.09 introduced a bug in `rm_acpi_nvpcf_notify()`: it calls `os_ref_dynamic_power()` unconditionally without checking the GPU's D3Cold state. The EC query byte `0x84` fires the `_Q84` ACPI handler (dsdt.dsl line 9468), which calls `INOU.PWUP`, which sends `Notify(NPCF, 0xC0)` and `Notify(GPP0.PEGP, 0xC5)`. With fine-grained dynamic power management (`NVreg_DynamicPowerManagement=0x02`), the GPU was runtime-suspended. The NVPCF notify woke it; the EC re-asserted before the GPU finished waking; this produced a 321/sec notify storm, pushing GPU idle temperature to ~84°C.

**Upstream fix.** Community PR #1181 on `NVIDIA/open-gpu-kernel-modules`: "Don't wake a runtime-suspended dGPU to service NVPCF/GPS ACPI notifies." Filed 2026-06-06. As of Jun 2026, unmerged. Neither 580.159.04 nor 610.43.02 contains the fix.

**Fix applied.** Set `NVreg_DynamicPowerManagement=0x01` (coarse-grained power management, no D3cold transitions) in `/etc/modprobe.d/nvidia-power.conf` and `/etc/modprobe.d/nvidia.conf`. This prevents the GPU from entering runtime suspend, eliminating the stale-state re-notification loop.

**Note: modprobe.d fix alone was insufficient.** The machine froze twice with the modprobe.d fix active — Steam loading `nvidia-drm` was the trigger, which can override modprobe.d load order. Definitive fix applied 2026-06-24: `/etc/default/grub.d/99-nvidia-pm.cfg` sets `nvidia.NVreg_DynamicPowerManagement=0x01` as a kernel cmdline parameter. The cmdline parameter takes absolute precedence over all modprobe.d settings regardless of module load order. Both the modprobe.d files and the cmdline override are now active.

**Status.** Live. Coarse-grained PM means the GPU idles higher than optimal but does not freeze the machine.

**Watch item.** `nvidia.conf` sets `NVreg_DynamicPowerManagement=0x01` in three places across two files. All three must be updated in sync if the value ever changes. See revert checklist (§5).

---

### 2.3 — DSDT/NVPCF investigation and why the DSDT patch was superseded (May–Jun 2026)

**Investigation.** An ACPI DSDT patch (`nvpcf_fix.asl` → `/boot/nvpcf_override.cpio`) was developed to null out the `INOU.PWUP` call in `_Q84`, preventing the notify storm at the ACPI level. The patch was built against the decompiled DSDT (`dsdt.dsl`, `dsdt.dat`).

**Why it was superseded.** The Dec 2025 BIOS already ships `\_SB.INOU.PWUP` as an empty method — the same fix the DSDT patch applied. The patch was therefore redundant. Additionally, the kernel rejects the override CPIO because its OEM table revision is equal to the running firmware (not greater), so the kernel never loads it.

**Current status.** The CPIO at `/boot/nvpcf_override.cpio` is harmless and inert (kernel ignores it). The GRUB `GRUB_EARLY_INITRD_LINUX_CUSTOM` entry pointing to it was cleaned up as part of the Gemini artifact cleanup (§2.4). The DSDT source files (`dsdt.dsl`, `dsdt.dat`) are retained as the source of truth for any future ACPI work.

**Constraint.** BIOS updates invalidate any DSDT override — rebuild against the new DSDT after any firmware update. Check OEM revision at ACPI offset 24–28 (not 32–36, which is Creator Revision):

```bash
sudo python3 -c "import struct; hdr=open('/sys/firmware/acpi/tables/DSDT','rb').read(36); rev=struct.unpack('<I',hdr[24:28])[0]; print(hex(rev))"
# Current firmware: 0x01072009
```

---

### 2.4 — Gemini artifact cleanup (Jun 2026)

**Context.** A prior AI session (Gemini) applied a set of fixes, some of which were incorrect or counterproductive. These were identified and removed.

**Removed / corrected:**

| Artifact | Action | Reason |
|----------|--------|--------|
| `GRUB_EARLY_INITRD_LINUX_CUSTOM="acpi_override.cpio"` | Removed from GRUB config (note: `/etc/default/grub` does not exist; drop-ins in `/etc/default/grub.d/` used instead) | Wrong fix; DSDT patch superseded anyway |
| `acpi_osi='!Windows 2020'` | Removed | Inert on this firmware |
| `processor.max_cstate=5` | Removed | Counterproductive; limits CPU power savings |
| `pcie_aspm=force` | Kept | Correct — r8125 hard freeze without it |
| `/etc/modprobe.d/blacklist-r8169.conf` | Kept | Correct — r8125 is the right driver |

Script: `.scratch/grub_cleanup.sh`. Status: Done.

---

### 2.5 — pcie_aspm.policy=powersave → policy=default (Jun 2026)

**Date.** Config change made 2026-06-14; reboot and verification 2026-06-15.

**Root cause.** With `pcie_aspm=force` in GRUB, `pcie_aspm.policy=powersave` (the prior setting) aggressively pushed PCIe devices including r8125 into L1 ASPM. The Realtek NIC would strand itself in a low-power state overnight: `enp5s0` showed `state DOWN` on the following morning.

**Fix applied.** Changed `pcie_aspm.policy=powersave` to `pcie_aspm.policy=default` in `/etc/default/grub.d/10-skikk-platform.cfg` (note: `/etc/default/grub` does not exist on this system; platform cmdline params live in this drop-in), ran `sudo update-grub`, rebooted. Post-reboot: `/proc/cmdline` confirmed `pcie_aspm.policy=default` live; `enp5s0` healthy (NO-CARRIER only because no cable was plugged in at time of check; driver state clean).

**Constraint created.** The combination `pcie_aspm=force` + `pcie_aspm.policy=default` is the required stable state. `policy=powersave` + `force` together strand the NIC. Do not change `policy` without testing ethernet stability over multiple sleep/wake cycles.

---

### 2.6 — TCC fan profile (date unrecorded, pre-Jun 2026)

**Context.** Tuxedo Control Center (TCC) manages fan profiles. Fan profile configuration is stored in a file owned/written by the `tccd` daemon. The relevant script is `.scratch/apply_max_fan.sh`.

**Known constraint.** `tccd` rewrites its config file on restart. To safely edit TCC config: stop `tccd` → write config → start `tccd`. Editing while the daemon runs causes changes to be silently overwritten.

---

### 2.7 — rsyslog ACPI EC spam filter (2026-06-14)

**Problem.** Systemd journal was accumulating ~785 MB/day of ACPI EC debug messages. This was causing disk pressure and making journal searches slow.

**Fix applied.** Created `/etc/rsyslog.d/10-drop-acpi-ec.conf` to filter ACPI EC log entries. Post-fix log rate: ~1 MB/day.

---

### 2.8 — System disk cleanup (2026-06-14)

**~18 GB freed:**

| Source | Size |
|--------|------|
| Android Studio snap | included in snap cleanup |
| Old snap revisions | multiple GB |
| `~/.android` | 8.3 GB |
| LM Studio models | 3.2 GB |
| Android SDK | 11 GB |

`snap set system refresh.retain=2` applied — 8 disabled snap revisions are normal going forward.

**Disk state after cleanup.** Root: 76%, 222 GB free. `/data`: 25%, 701 GB free.

---

### 2.9 — rclone OneDrive token renewal (2026-06-14)

**Problem.** rclone OneDrive token expired; `OneDrive` mount was unmounted.

**Fix.** Reconnected interactively, restarted rclone service. Both `GoogleDrive` and `OneDrive` mounts verified healthy post-reboot (2026-06-15).

---

### 2.10 — Waydroid investigation and park (2026-06-14)

**Goal.** Run Android apps (originally for Kindle; Foliate installed as workaround).

**Root cause diagnosed.** `vendor.hwcomposer-2-1` crashes with SIGSEGV approximately 1–20 seconds after start on every attempt. SurfaceFlinger detects the hwcomposer death and aborts with SIGABRT. Android init restarts both in a loop every ~2–5 seconds. The Wayland compositor (GNOME) runs on the NVIDIA GPU; the waydroid MAINLINE vendor image targets AMD iGPU (`renderD129`) for GBM buffer allocation. In discrete GPU BIOS mode, the AMD iGPU render node is present but half-powered, causing GBM init to fail. With GNOME running on NVIDIA and the waydroid stack trying to use AMD DRM, cross-device dma-buf sharing fails.

**Contributing issues (secondary, do not cause the UI crash):**

- `ro.hardware.vulkan=radeon` in `waydroid.prop` — wrong for an NVIDIA system; harmless while swiftshader is active but should be corrected.
- Ubuntu 26.04 uses nftables; waydroid's `waydroid-net.sh` calls `iptables-legacy`, failing NAT setup → no container network. Fixing: `sudo update-alternatives --set iptables /usr/sbin/iptables-nft`.
- `lxc.hook.post-stop = /dev/null` exits 126 (not executable) on every stop — cosmetic only.

**Attempted but didn't fix.** Setting `ro.hardware.egl=mesa` in `waydroid.cfg`.

**What would fix it.** Switching BIOS to hybrid GPU mode (AMD iGPU primary) would give waydroid a functioning DRM render node. User won't do this — discrete GPU mode is required for the external monitor (mini-DP → HDMI video + USB-C power). Alternatively, nvidia-open 610+ with improved Blackwell GBM support may enable proper NVIDIA-backed Waydroid.

**State left in.** `waydroid session stop` (clean). `waydroid.cfg`: `background_start=false` (prevents focus-stealing crash loop on login), `ro.hardware.egl=mesa`.

**Important note.** `waydroid.prop` is regenerated from `waydroid.cfg` on every session start. Persist any configuration changes in `waydroid.cfg`, not `waydroid.prop`.

**Unfinished fix steps (tested options, still viable to try):**

1. Add `ro.hardware.hwcomposer=ranchu` to `waydroid.prop` (ranchu is the AOSP emulator software compositor; bypasses HWC2 crash entirely). Not yet attempted.
2. Fix iptables backend: `sudo update-alternatives --set iptables /usr/sbin/iptables-nft`. Required for container networking even if display is fixed.
3. Fix vulkan property: change `ro.hardware.vulkan=radeon` to empty or `pastel`.

**Cloud routine.** `trig_01JUnBV6BGNv5pJsbQeGNSvw` scheduled for 2026-07-07 to check nvidia-driver-610 availability.

---

### 2.11 — Foliate installed as Kindle/EPUB workaround (2026-06-14)

Since Waydroid (and therefore the Kindle Android app) is non-functional, Foliate v3.3.0 was installed (`sudo apt install foliate`) as a native Linux EPUB reader for the Calibre library.

---

### 2.12 — chezmoi dotfiles setup (Jun 2026)

**Context.** User has two machines. The existing `sysadmin_files` symlink installer was never run on the SKIKK. Live dotfiles have drifted from the repository. A chezmoi migration was analysed.

**Analysis.** Three options were evaluated:

- **Option A:** Convert `sysadmin_files` to chezmoi — high effort, existing structure fights chezmoi conventions.
- **Option B:** New dotfiles repository managed by chezmoi — clean slate, recommended in the migration report.
- **Option C:** chezmoi for `~/.claude/` only — minimal scope, doesn't address the broader drift.

**Recommendation from migration report:** Option B. Key candidate files: `.zshrc` (needs machine-conditional templating for GCE SSH section), `.emacs.d/`, `~/.claude/` (with caveats — Claude Code writes `settings.json` and `conversations/` at runtime; use chezmoi `run_once_` scripts not direct management).

**Status.** Analysis complete (`chezmoi-migration-report.md`, `chezmoi-explainer-report.md`, `chezmoi-setup-log.md` in `.scratch/`). Migration not yet executed.

---

### 2.13 — Portable monitor setup (2026-06-14)

**Requirement.** External monitor requires:
1. BIOS set to **discrete GPU mode** (not hybrid/iGPU mode).
2. Mini-DP → HDMI adapter for video signal.
3. USB-C cable for monitor power.

Both connections are required simultaneously. This BIOS mode setting is the reason Waydroid cannot use the AMD iGPU render node (§2.10).

---

### 2.14 — PySol sluggishness diagnosed (2026-06-14)

**Cause.** Chrome and PySol competing for XWayland resources, causing PySol to stutter.

**Fix.** Marvellous Suspender extension installed in Chrome to auto-suspend inactive tabs, reducing XWayland contention.

---

### §2.15 — r8125/r8169 NIC blacklisted (2026-06-28)

**Symptom:** ~250 ESD recovery events/day in the kernel journal (`enp5s0: pci link is down`) even with no ethernet cable attached. Root cause: `pcie_aspm=force` pushes ASPM on all devices including the RTL8125; the NIC cannot negotiate L1 correctly, generating continuous Error State Detection events. No hard freeze (unlike the original `pcie_aspm=off` era) but significant journal noise and false-positive health-check errors.

**Resolution:** Blacklisted both `r8125` (vendor driver) and `r8169` (kernel fallback) via `/etc/modprobe.d/blacklist-r8125.conf`. `pcie_aspm=force` + `policy=default` retained — required for s2idle. NIC is unused; system runs on WiFi exclusively.

**Re-enable:** `sudo rm /etc/modprobe.d/blacklist-r8125.conf && sudo update-initramfs -u -k all && reboot`. Expect ESD recovery events to resume; verify `policy=default` prevents hard freeze before considering ASPM policy changes.

---

## 3. Active Constraints

Things that must not be changed without understanding the downstream impact:

| Constraint | File | Why |
|------------|------|-----|
| Keep `pcie_aspm=force` | `/etc/default/grub.d/10-skikk-platform.cfg` (note: `/etc/default/grub` does not exist; use drop-ins) | r8125 hard-freezes without ASPM negotiation being forced; root cause is BIOS RTAC bug in PEP `_DSM` |
| Keep `pcie_aspm.policy=default` | `/etc/default/grub.d/10-skikk-platform.cfg` | `policy=powersave` + `force` together strand r8125 in L1 ASPM overnight |
| Keep `NVreg_DynamicPowerManagement=0x01` | `/etc/modprobe.d/nvidia-power.conf`, `/etc/modprobe.d/nvidia.conf`, and `/etc/default/grub.d/99-nvidia-pm.cfg` (cmdline takes precedence) | Fine-grained (0x02) causes `pm_runtime_work` to block the system workqueue on Blackwell GB203M, hard-freezing the machine |
| After any GRUB drop-in edit: run `sudo update-grub` + reboot | `/etc/default/grub.d/` drop-ins (`/etc/default/grub` does not exist on this system) | Changes do not take effect until grub regenerates and the kernel cmdline is updated at next boot |
| After any BIOS update: rebuild DSDT override | `.scratch/nvpcf_fix.asl` | BIOS update changes ACPI table revision; old override is silently rejected by kernel |
| `NVreg_EnableGpuFirmware=0` is silently ignored | Any modprobe.d file | GSP firmware is mandatory on Blackwell; this option has no effect |
| `waydroid.prop` is overwritten on every session start | `/var/lib/waydroid/waydroid.prop` | Persist waydroid config changes in `waydroid.cfg`, not `waydroid.prop` |
| Stop `tccd` before editing TCC fan config | `/var/lib/tuxedo-control-center/` | `tccd` rewrites config on clean exit; edits made while running are overwritten |
| External monitor requires discrete GPU BIOS mode | BIOS setting | Hybrid mode disables the discrete output path needed for the mini-DP port |
| r8125/r8169 NIC blacklisted | `/etc/modprobe.d/blacklist-r8125.conf` | Both drivers blacklisted 2026-06-28. NIC unused; system on WiFi. `pcie_aspm=force`+`policy=default` retained for s2idle. Re-enable: `sudo rm /etc/modprobe.d/blacklist-r8125.conf && sudo update-initramfs -u -k all && reboot` |

---

## 4. Pending Work

| Item | Status | Trigger to resume |
|------|--------|-------------------|
| Waydroid hwcomposer fix (try `ro.hardware.hwcomposer=ranchu`) | Parked | Any time; safe to attempt without GPU mode change. See fix steps in §2.10 |
| Waydroid iptables → nftables (`sudo update-alternatives --set iptables /usr/sbin/iptables-nft`) | Parked | Required for container networking even if display fix works |
| Waydroid vulkan property fix (`ro.hardware.vulkan=radeon` → empty) | Parked | Attempt alongside hwcomposer fix |
| Full Waydroid enablement on NVIDIA | Blocked | nvidia-open 610+ with Blackwell GBM support. Cloud routine `trig_01JUnBV6BGNv5pJsbQeGNSvw` checks 2026-07-07 |
| nvidia PM fine-grained (0x02) revert | Blocked | nvidia-open PR #1181 merged and released. Watch 610.x+ release notes for "NVPCF", "RTD3", or "D3cold" fix |
| SMART health check for NVMe drives | Pending | `sudo smartctl -a /dev/nvme0n1` and `/dev/nvme1n1`; needs `Bash(sudo smartctl**)` in allowlist |
| Root filesystem growth monitoring | Watch | Currently at 75%; run `du -sh /home/* /var/*` when convenient |
| DIMM 1 temperature monitoring | Watch | 53–54°C under load, alarm at 55°C; check during memory-intensive work |
| chezmoi dotfiles migration | Deferred | User decision; see §2.12 and `.scratch/chezmoi-migration-report.md` |
| `.scratch/` file triage / doc promotion | Deferred | See `.scratch/doc-promotion-proposal.md` for per-file recommendations |

---

## 5. Revert Checklist

### 5.1 — Revert nvidia PM fix (when upstream fixes Blackwell runtime PM)

**Trigger:** nvidia-open PR #1181 merged and available in a released driver (watch 610.x+ release notes for keywords: "NVPCF", "RTD3", "D3cold"). Confirm the specific fix is included — do not revert speculatively.

**Steps:**

```bash
# 1. Remove the modprobe.d workaround file
sudo rm /etc/modprobe.d/nvidia-power.conf

# 2. Remove the cmdline override (the definitive fix — must also be removed)
sudo rm /etc/default/grub.d/99-nvidia-pm.cfg
sudo update-grub

# 3. Revert nvidia.conf to fine-grained power management
# Edit /etc/modprobe.d/nvidia.conf — change all instances of
#   NVreg_DynamicPowerManagement=0x01
# to
#   NVreg_DynamicPowerManagement=0x02
# Note: the value appears three times across two files — update all three

# 4. Rebuild initramfs to pick up the change
sudo update-initramfs -u -k all

# 5. Reboot and verify
# After reboot: monitor GPU temperature at idle
# Baseline with fix: GPU should idle at ambient+5°C or better
# Red flag: GPU idle temp climbing above 50°C → storm has returned
# Check: sudo journalctl -k | grep -E "nvpcf|D3cold|pm_runtime_work"
```

### 5.2 — If r8125 ethernet freeze recurs after a GRUB change

If `enp5s0` shows `state DOWN` after a reboot involving GRUB changes:

1. Verify `/proc/cmdline` contains both `pcie_aspm=force` AND `pcie_aspm.policy=default`.
2. If either is missing, check `/etc/default/grub.d/10-skikk-platform.cfg` (note: `/etc/default/grub` does not exist on this system; use drop-ins), correct, re-run `sudo update-grub`, reboot.
3. If both are present but NIC is still DOWN: check `dmesg | grep r8125` and `dmesg | grep -i aspm` for regression.

### 5.3 — DSDT override after a BIOS update

1. Dump new DSDT: `sudo cp /sys/firmware/acpi/tables/DSDT dsdt.dat && iasl -d dsdt.dat`
2. Verify OEM revision has changed: compare output of the python3 offset check against `0x01072009`.
3. Re-examine `_Q84` handler (was at dsdt.dsl line 9468) in new DSDT — check if `INOU.PWUP` is still an empty method.
4. If `INOU.PWUP` is no longer empty and the D3cold bug is fixed upstream, no patch needed.
5. If patch is still needed: rebuild `nvpcf_fix.asl` with OEM revision incremented by 1, recompile, regenerate CPIO, update the relevant `/etc/default/grub.d/` drop-in (note: `/etc/default/grub` does not exist on this system), `sudo update-grub`, reboot.

---

_End of draft._
