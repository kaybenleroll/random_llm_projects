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

### §2.16 — NVPCF fix superseded by BIOS update (Jun 2026)

**Status:** BIOS Dec 2025 ships `\_SB.INOU.PWUP` as an empty method — the same fix our DSDT patch (`nvpcf_fix.asl` → `/boot/nvpcf_override.cpio`) applied. The initrd override is no longer needed. The kernel rejects our cpio anyway (OEM revision equal, not greater) so it's harmless to leave in place. No action required; see §5.3 for what to check after any future BIOS update.

---

### §2.17 — pm_runtime_work freeze (Blackwell + fine-grained PM) (Jun 2026)

**Symptom:** Machine hard-freezes intermittently, no kernel panic or error logged. Root cause: nvidia-open 580.126.09 (upgraded May 3 2026) introduced a bug in `rm_acpi_nvpcf_notify()` — calls `os_ref_dynamic_power()` unconditionally without a D3Cold state check, causing `pm_runtime_work` callbacks to block the system workqueue on Blackwell GB203M. Fix is in community PR #1181 (open-gpu-kernel-modules, filed Jun 6 2026, unmerged as of Jun 24 2026). Latest available driver at the time, 595.84 (Jun 17 2026), did not contain the fix.

**First attempt (insufficient):** `NVreg_DynamicPowerManagement=0x01` (coarse-grained) set in `/etc/modprobe.d/nvidia-power.conf` and `/etc/modprobe.d/nvidia.conf`. Machine still froze twice with this active — Steam loading `nvidia-drm` was the trigger. Root cause: `cmdline` parameters take absolute precedence over all modprobe.d load order, so the modprobe.d-only fix could be overridden by load timing.

**Definitive fix (Jun 24 2026):** `/etc/default/grub.d/99-nvidia-pm.cfg` sets `GRUB_CMDLINE_LINUX_DEFAULT` to include `nvidia.NVreg_DynamicPowerManagement=0x01`.

**Revert when nvidia-open fixes Blackwell runtime PM:** watch 610.x+ release notes for "NVPCF", "RTD3", or "D3cold" fix, then `sudo rm /etc/modprobe.d/nvidia-power.conf /etc/default/grub.d/99-nvidia-pm.cfg`, revert `nvidia.conf` to `0x02`, run `sudo update-grub && sudo update-initramfs -u -k all`, reboot.

---

### §2.18 — s2idle suspend freeze via power/lid triggers (2026-07-09)

**Symptom:** A spurious power/sleep-key input event (source unconfirmed — candidates: the "2.4G Mouse System Control" wireless dongle glitching, or ACPI/EC noise given GPE07's already-documented high firing rate; ruled out: no GNOME keybinding maps to a suspend/lock action that could explain it, and `turbo-whisper`'s hotkey is `Ctrl+Space` not the key the user pressed) triggered `systemd-logind` → `The system will suspend now!`. `nvidia-suspend.service` then hit the same Blackwell s2idle bug as §2.17 — `NVRM: nvAssertFailedNoLog` MMU-walk assertion failures during GPU memory teardown — and the machine never resumed: both displays went blank while the CPU kept running, ending in a kernel soft-lockup (`Xwayland` stuck 26s+) ~34s after the suspend request. Required a hard reset; nothing else was logged afterward.

**Root gap:** `logind.conf` only had `HandleLidSwitch*=ignore` — `HandleSuspendKey` was never set. Separately, **GNOME's own power daemon has an independent trigger path** (`org.gnome.settings-daemon.plugins.power` `power-button-action`/`lid-close-*-action`, both still `'suspend'`) that `logind.conf`'s `HandleLidSwitch=ignore` does *not* cover — GNOME can request suspend on lid-close or power-button press regardless of the logind-level setting.

**Fix:** set all three GNOME actions to `'nothing'` (live, no reboot); staged a `HandleSuspendKey=ignore`/`HandleHibernateKey=ignore` logind drop-in for defense-in-depth (needs sudo+reboot — see doc/machines/skikk-thor.md Active fixes table for current status).

**If this recurs:** blank screens + machine still powered on this hardware means a hung s2idle resume, not a hang worth waiting out — hard power-cycle is the only recovery; try SSH from another device first if convenient, since this was a soft lockup (not a full panic) and another CPU may still answer.

---

### §2.19 — yt6801 out-of-tree taint at boot (2026-07-10)

**Symptom:** `health-20260710-131810.txt` showed `yt6801: loading out-of-tree module taints kernel` and `yt6801: module verification failed: signature and/or required key missing - tainting kernel` near the start of dmesg.

**Investigation:** `yt6801` is the Motorcomm YT6801 Gigabit Ethernet driver, shipped via the `tuxedo-yt6801` DKMS package (`dkms status` → `tuxedo-yt6801/1.0.31, 6.17.0-23-generic, x86_64: installed`), not part of the already-documented Realtek RTL8125 stack (§2.15). `lsmod` shows it loaded with 0 references (`yt6801 180224 0`) — not bound to any device. `lspci -nn` on this machine shows no PCI device matching the driver's PCI alias (`pci:v00001F0Ad00006801sv*sd*bc*sc*i*`, vendor `1f0a`) — this chassis has no Motorcomm NIC at all; the RTL8125 (vendor `10ec`) doesn't appear in `lspci` either post-blacklist. The module is part of TUXEDO's shared driver bundle that loads unconditionally across TUXEDO chassis models and only binds if matching hardware is present — on this machine it never binds. `modinfo` shows the module is signed (`sig_id: PKCS#7`, signer `skikk-thor Secure Boot Module Signature key`) but verification still fails; Secure Boot itself is disabled (`mokutil --sb-state` → `SecureBoot disabled`), so the taint is purely a DKMS auto-signing/MOK-enrollment artifact — the build-time signing key was never enrolled via `mokutil --import`, which is common for locally-built DKMS modules and has no functional effect while Secure Boot is off. No ASPM/ESD errors, no functional symptoms in the journal for this module.

**Conclusion:** Cosmetic boot-time taint only — module is loaded but inert (0 refcount, no matching hardware). Not the same driver path as the blacklisted r8125/r8169 (different vendor, different chip), so it carries no ASPM/ESD risk even if it were to bind.

**Recommendation (not yet applied):** Low priority — optionally blacklist `yt6801` via a new `/etc/modprobe.d/blacklist-yt6801.conf` (same pattern as `blacklist-r8125.conf`) purely to remove the taint flag from future boots, since the driver serves no function on this chassis. This needs explicit user sign-off before applying, same as any other modprobe.d change. Current status: monitoring, no action taken.

---

### §2.20 — NVRM `nvAssertFailedNoLog` boot-time assertions (2026-07-10)

**Symptom:** `health-20260710-131810.txt` showed 3x `NVRM: nvAssertFailedNoLog: Assertion failed: 0 @ osapi.c:1939` at 11:01:41–11:01:42 during boot.

**Investigation:** Journal timeline (`journalctl -k -b`) shows: NVIDIA driver load at 11:01:23 (`NVRM: loading NVIDIA UNIX Open Kernel Module ... 580.126.09`), `nvidia-drm` init and `GPS ACPI DSM called before _acpiDsmSupportedFuncCacheInit` warnings at 11:01:23–25, then the three `nvAssertFailedNoLog` lines at 11:01:41–42 — roughly 16–18 seconds after DRM init, in the window where GDM/gnome-shell typically starts probing the display. This is a different assertion (`osapi.c:1939`) and a different code path than the already-documented `pm_runtime_work`/D3cold bug (§2.17, which lives in `rm_acpi_nvpcf_notify()`) and the s2idle MMU-walk teardown assertions from §2.18 — this one fires once at boot and does not recur, and no freeze followed this boot.

**Conclusion:** Boot-time-only, logged-but-non-fatal assertion in nvidia-open 580.126.09 on this Blackwell GPU (GB203M) — consistent with the driver's broader pattern of internal assertion firing under ACPI/GSP interaction on this hardware generation, but this particular instance had no observed functional impact (no freeze, no display glitch reported).

**Status:** Monitoring, no action taken. Watch for recurrence or escalation to an actual freeze — if it starts correlating with a hang (as the similar-looking assertions in §2.18 did during s2idle resume), escalate; a one-off logged assertion at boot with no consequence does not currently warrant a fix.

---

### §2.21 — Stremio x265/HEVC black-screen: Chrome has no Linux HEVC decoder; Flathub's "stable" Stremio is now the broken NVIDIA shell (2026-07-13)

**Symptom:** x265/HEVC streams in the container+Chrome Stremio setup (`.scratch/stremio-options.md`, §"Current Setup") play audio but show a black screen.

**Root cause:** Google Chrome ships no HEVC/x265 video decoder on Linux at all (proprietary codec, excluded from Linux builds regardless of GPU) — confirmed by Chrome CPU sitting flat at ~19-20% during a "stuck" stream (idle-level, not a struggling software decoder) while audio (separate codec) played fine. This is unrelated to machine power; no Linux Chrome build can decode HEVC.

**Diagnostic technique:** live-sampling Chrome's process CPU against the `stremio-server` podman container's CPU (via the Monitor tool) during playback cleanly isolates a client-side software-decode bottleneck from a server/container-side one — client CPU spiking while the container stays flat points at Chrome-side decode, not the server; reusable for any future container+browser playback stutter investigation.

**Flatpak retested and reconfirmed broken:** Installed `com.stremio.Stremio` from Flathub (`flatpak install flathub com.stremio.Stremio`) to test as an alternative. Version resolved was `1.0.3` — this is **not** the old v4.4.168 Qt shell that `.scratch/stremio-options.md` (2026-06-16) evaluated and recommended as safest; Flathub's "stable" channel has since been repointed to the GTK4/WebKitGTK/Rust rewrite that doc labeled the **v5 beta**, which carries an open, unresolved NVIDIA bug (upstream: `stremio-linux-shell #30`) — a wgpu "Unable to get gpu adapter" crash on Blackwell-class GPUs (originally reported on RTX 4080 Super / driver 580.105.08, same generation/branch as this machine's RTX 5070 Ti / 580.126.09). Reproduced the crash here (`** ERROR **: Connection: failed to receive credentials...`, GUI shell dies immediately, only the bundled Node server survives). Ruled out `flatpak override --device=all/dri` (added then fully reset — crash persists identically either way) and both of the doc's documented workarounds, `GDK_BACKEND=x11` and `LIBGL_ALWAYS_SOFTWARE=1` (both failed, matching other reporters). **Verdict: still a dead end, uninstalled** (`flatpak uninstall com.stremio.Stremio`).

**NVDEC hardware decode confirmed available on this machine, just unused by any current Stremio path:** `hevc_cuvid` decoder present via `libnvidia-decode-580`; native `mpv` (installed `sudo apt install mpv`) lists `hevc-nvdec`/`hevc_cuvid-cuda` in `mpv --hwdec=help`. No sandboxing blocks this the way Flatpak blocks VAAPI — NVIDIA's official `.run` driver bundle ships `libnvcuvid.so` as part of the same artifact used for the Flatpak GL.nvidia extension, so NVDEC (unlike VAAPI) actually would have worked in a sandboxed Flatpak mpv too, had the Stremio GUI shell itself not been broken. Caveat for any future Flatpak app needing GPU video decode on this machine: the bundled `org.freedesktop.Platform.GL.nvidia-XXX` extension must exactly match the host driver version (here, `nvidia-580-126-09`) — a mismatch silently falls back to software decode or fails outright, it isn't a generic "NVIDIA GL extension installed" check.

**Chosen path forward:** bypass Stremio's GUI/video-element entirely — Stremio web Settings → Player → Advanced → External player → **M3U playlist**, which exports the resolved stream URL as a downloaded `.m3u` file; open that with `mpv --hwdec=nvdec` for real GPU-decoded playback. Friction: file-based handoff, not a clean pipe — no in-app "open in mpv" button. A small `inotifywait` watcher on `~/Downloads` would auto-launch mpv on new `.m3u` files if the manual step proves annoying. Not yet built — end-to-end NVDEC playback via this path not yet verified live (mpv installed and `hevc-nvdec` confirmed present; the M3U export + actual playback test is pending).

**If Flatpak Stremio is reconsidered later:** check whether Flathub's stable channel has repointed back to a fixed v4/v5 build, or whether upstream `stremio-linux-shell #30` has closed, before retrying — don't re-diagnose from scratch.

**End-to-end NVDEC playback verified (manual path):** pulled the resolved RealDebrid stream URL straight from `podman logs stremio-server` (look for the `opensubHash?videoUrl=...` line — the URL-decoded `videoUrl` param is the direct playable link) and opened it with `mpv --hwdec=nvdec`. Confirmed: `Using hardware decoding (nvdec)`, `VO: [gpu-next] ... cuda[nv12]`, and `mpv` appeared in `nvidia-smi`'s process list using GPU memory. This proves the fix works — the remaining question is only how much manual friction is acceptable. `~/.config/mpv/mpv.conf` now sets `hwdec=nvdec` / `hwdec-codecs=all` as defaults so any future `mpv <url>` invocation gets NVDEC automatically without needing the flag.

**Important correction on why the black screen happens at all:** Stremio's server-side transcoding ("Stremio only direct plays h264, HEVC always undergoes transcoding" — [Stremio/stremio-features#865](https://github.com/Stremio/stremio-features/issues/865)) does **not** apply to RealDebrid-resolved links. Those bypass the local container's torrent/ffmpeg pipeline entirely and serve the raw cached file directly from RealDebrid's CDN — confirmed by zero ffmpeg/transcode activity in `podman logs stremio-server` during a black-screen playback attempt. So for RD-backed streams specifically, the original "Chrome has no Linux HEVC decoder" diagnosis is the complete explanation, not just a contributing factor.

**Automation attempt (in progress, not yet working):** tried wiring up automatic browser→mpv handoff via [ang3lo-azevedo/open-stremio-links-on-mpv](https://github.com/ang3lo-azevedo/open-stremio-links-on-mpv) (Tampermonkey userscript that injects a "Play on MPV" option into stream-selection right-click menus) + [akiirui/mpv-handler](https://github.com/akiirui/mpv-handler) (native `mpv-handler://` protocol handler).

- **mpv-handler (native, done):** binary at `~/.local/bin/mpv-handler`, desktop files in `~/.local/share/applications/`, protocol registered via `xdg-mime default mpv-handler.desktop x-scheme-handler/mpv-handler` (and `-debug` variant). Verified with `xdg-mime query default x-scheme-handler/mpv-handler`. There is **no separate "mpv-handler Chrome extension"** — that was an earlier wrong claim in this session; the native app + xdg-mime registration is the whole story on the browser-integration side, Chrome talks to it via the OS protocol handler.
- **Tampermonkey + userscript (installed, not functioning):** installed via Chrome Web Store + the raw `.user.js` URL (needed Developer Mode enabled in `chrome://extensions` first, otherwise Chrome downloads the raw file instead of triggering Tampermonkey's install prompt). Right-clicking a stream entry in stremio-web shows only the native Chrome context menu — no "Play on MPV" entry injected.
- **Suspected cause, unconfirmed:** the userscript targets `a.stream-container-JPdah`, a CSS-modules-hashed class name. These hashes are build-specific and likely don't match the current stremio-web release running in this container. Needs live DevTools inspection (check actual class name on a stream-list anchor element, check Tampermonkey dashboard for the script's enabled/match status, check console for errors) to confirm and fix the selector.

**Practical status:** the manual `podman logs | mpv --hwdec=nvdec` path is confirmed working today and requires no further setup. The automated userscript path is parked mid-debug — pick up by inspecting the live DOM class name and updating the userscript's selector, or abandon in favor of the manual path / a small wrapper script if the payoff doesn't justify further debugging time.

---

### §2.22 — HP dock DisplayPort/ethernet fail — proprietary MUX alt-mode has no Linux driver (2026-07-16)

**Symptom:** User plugged in an HP-branded USB-C docking station. Initially reported as "not detected at all"; investigation showed partial detection — USB peripherals (mouse/keyboard, storage, audio) work through the dock, but display and ethernet do not.

**Investigation:**

- **USB-C/Type-C layer:** the dock IS detected at the Type-C level — `/sys/class/typec/port0-partner` and `port0-cable` are present, `data_role: host` is correct. The laptop correctly recognizes it as a USB-C peripheral.
- **USB topology:** the dock enumerates as 3 cascaded USB hubs (Bus 001) with HID and mass-storage devices bound correctly. A separate Bus 002 device carries a Realtek RTL8152 USB-Ethernet adapter (`r8152` driver bound) plus USB audio interfaces (`snd-usb-audio` bound). **RTL8152 is a different chipset from the already-blacklisted RTL8125/r8169 PCIe NICs (§2.15/known quirks)** — the existing `blacklist-r8125.conf` is unrelated to this device and does not affect it.
- **Ethernet:** `enx9cebe88dcecc` exists with `r8152` bound but stays DOWN/NO-CARRIER; `ethtool` confirms `Link detected: no` on both dock USB-C ports tested. Could be no cable in the dock's ethernet port, or gated behind the same MUX handshake as display — not conclusively distinguished.
- **Display:** `xrandr` never shows anything but the internal panel (`eDP-2`) — no external monitor detected via the dock on either USB-C port.
- **Billboard device:** a USB "Billboard" class device (used for USB-PD/Alt-Mode capability advertisement) enumerates with no driver bound, both before and after an unplug/replug cycle.
- **Root cause:** the dock's typec altmode nodes (`port0-partner.0`/`.1`, and `port1-partner.0`/`.1` after moving to the second USB-C port) both advertise SVID `03f0` — **HP's own USB vendor ID**, used for HP's proprietary "MUX" alt-mode signaling protocol, not the standard DisplayPort Alt-Mode SVID `ff01`. All four nodes show `active: no` on both ports.
- **Port-independence confirmed:** identical behavior (USB works, ethernet DOWN, no altmode activation) on both port0 and port1 — rules out a port-specific hardware fault on the laptop side.
- **power_role instability:** observed to differ between two separate connection events (sink, then later source) — consistent with the dock's MUX logic retrying a handshake it can't complete, not conclusively diagnosed further.
- **Manual activation attempted:** `echo 1 | sudo tee /sys/class/typec/port1-partner/port1-partner.0/active` returned `Permission denied (os error 13)` even as root — confirms the kernel's typec/altmode driver has no write handler for manual activation on this node; no userspace lever exists to force it.
- **Cross-machine test (user-confirmed):** the same dock works fully, including display, on a different laptop — also a SKIKK machine, but running Windows. This rules out "requires HP-brand host hardware" as the mechanism; the gate is OS/driver-level, not a hardware vendor lock.
- **Web research:** HP does not publish Linux drivers for these USB-C docks (Windows/Mac only per HP's own support pages). Some HP dock models (e.g. G4) use standard DP Alt-Mode and need no driver; this dock is evidently a model requiring HP's proprietary Windows-only MUX trigger sequence, which Linux's generic `ucsi_acpi`/`typec` stack has no equivalent for.
- **Driver stack confirmed clean:** `ucsi_acpi` → `typec_ucsi` → `typec`, loaded via the AMD `CPMUCSI` ACPI SSDT. No errors logged by this stack — negotiation simply never starts, because the dock only advertises its proprietary SVID and no Linux driver implements a trigger for it.

**Diagnostic evidence:** `.scratch/dock-diagnostics-20260716.txt` (baseline), `.scratch/dock-reconnect-20260716.txt` (unplug/replug capture), `.scratch/dock-typec-controller-20260716.txt` (PD/altmode driver identification), `.scratch/dock-port2-20260716.txt` (second-port test).

**Conclusion:** No Linux-side fix exists. This is a vendor driver gap — HP ships no Linux driver for the proprietary MUX trigger — not a bug in this machine's configuration, and not fixable via kernel params, sysfs, or udev rules. USB peripherals work fully through the dock since they don't depend on the alt-mode handshake; ethernet and display do not.

**Suggested workarounds (untested, not yet executed):**
- A direct USB-C-to-HDMI/DisplayPort/VGA adapter plugged straight into the laptop's own USB-C port (bypassing the dock) should work for display, since it only needs the laptop's own standard DP Alt-Mode support — confirmed present (`port0.0` altmode SVID `048d`, `active: yes`) — not the dock's proprietary negotiation.
- Use the dock only when booted into Windows, if dual-boot is ever set up — not currently applicable, this machine is Linux-only.
- Replace with a dock that uses standard DP Alt-Mode (SVID `ff01`) instead of a proprietary MUX.

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

### §2.23 — ExpressVPN IPC buffer-overflow journal flood (recurring, 2026-07-13 / 2026-07-16)

**Symptom:** `journal-watch.sh` (20,000-line/10-min threshold) alerted at 2026-07-16T20:19:46 — 52,286 lines in the window (2.6x threshold), journal at 3.2 GB. Root cause traced to `expressvpn-client.desktop`, which logged 51,940 entries in that single 10-minute window. Confirmed recurring: 182,988 entries around 2026-07-13T01:00, 375,523 around 2026-07-16T20:00, 88,805 aftershock at 2026-07-16T21:00 — 661,228 expressvpn journal entries over the trailing 7 days, concentrated in these spike windows.

**Root cause:** A malformed IPC message with a 1,150,808-byte payload (exceeding the daemon's buffer limit) hits `src/ipc.cpp:553` ("Invalid message: payload too large"), then cascades into thousands of "missing or incorrect magic tag" parse errors (`ipc.cpp:522`) as the daemon tries to resync on corrupted buffer fragments. `DaemonConnectionError` warnings appear on the client side during the incident. The daemon itself does not crash or restart — it stays up but floods the journal while failing to reconnect the client.

**Version finding:** installed ExpressVPN is `4.1.1-beta+10039` (built Sept 2025), custom install at `/opt/expressvpn/` (no apt repo configured), service `expressvpn-service.service`. Current public stable is `14.2.0` (June 2026) — a 10-major-version gap. Plausible that the IPC framing bug was fixed somewhere in that range; not confirmed against changelogs line-by-line.

**Status:** Resolved 2026-07-16T21:17 — user reinstalled via the official Linux installer, updating `4.1.1-beta+10039` → `14.2.0+13656` (confirmed at `/opt/expressvpn/share/version.txt`). Service restarted cleanly (`expressvpn-service.service` active since 21:17:25). Flood confirmed stopped: expressvpn logging dropped from ~8,000 lines/min during the incident to ~18 lines/min afterward, overall journal rate back to normal (~125 lines/min). If it recurs on 14.2.0, treat as a new bug (not the same 4.1.1-beta IPC framing issue) and investigate from scratch.

---

### §2.24 — VS Code crashing on Remote-SSH to uhet — VS Code core transport bug + unrelated Copilot Chat bug (2026-07-17)

**Symptom:** VS Code repeatedly failing/crashing while using Remote-SSH to connect to host `uhet` (`~/.ssh/config` alias for `144.76.230.169`). Multiple distinct crash signatures observed across the day, not a single reproducible failure.

**Timeline:**

- **~09:29–09:30:** initial report of a failed Remote-SSH connection. SSH itself and VS Code's own connection logs from this window showed a clean, successful connect — no reproducible failure at the time; likely transient.
- **~09:40:** extension host crash-looping locally ("Extension host (LocalProcess pid: N) terminated unexpectedly", respawning every 3–4s), each crash immediately preceded by `MainThreadChatAgents2#$updateAgent: No agent with handle N registered` and `chatParticipant must be declared in package.json: claude-code`. Initially misattributed to the Anthropic `claude-code` extension (v2.1.212) or a conflict with `saoudrizwan.claude-dev` (Cline). WebSearch established this is actually a known **Microsoft/GitHub Copilot Chat bug**: Copilot Chat (bundled, v0.50.1 in Stable) registers a chatParticipant named `claude-code` that it never declares in its own `package.json` `contributes.chatParticipants`. Fixed upstream in Copilot Chat 0.51 (VS Code Insiders only as of this date), not yet in Stable. Tracking issues: `microsoft/vscode#319423`, `#276860`, `#286303`, `#285730`; `anthropics/claude-code#11178`, `#9713`. **Not an Anthropic extension bug.** Firing once at startup is harmless (activation continues normally); the crash-loop appearance only occurs when something else is repeatedly killing the whole extension host, causing repeated re-activation and repeated one-shot firing of this same error.
- **09:52:43:** separate renderer process crash, `reason: crashed, code: 135` (SIGABRT). No coredump/minidump captured — VS Code's own crashpad handler logged that it could not find its Crashpad attachments directory (crash reporter itself broken/misconfigured). No correlating kernel/GPU errors in `journalctl -k` for that window — ruled out NVIDIA driver / this machine's known GPU-PM quirks as a cause. Session is Wayland (`XDG_SESSION_TYPE=wayland`), Electron running the native Wayland ozone platform; no `argv.json` overrides existed at the time.
- **Attempted fix:** created `~/.config/Code/argv.json` with `{"ozone-platform-hint": "x11"}` to force XWayland instead of native Wayland (a common fix for Electron+Wayland renderer instability). Did **not** take effect even after a full process kill (`pkill -f '/usr/share/code/'`) and relaunch — VS Code processes continued showing `--ozone-platform=wayland` in `ps aux` across multiple relaunch attempts throughout the day. Root cause of `argv.json` being ignored not diagnosed (possibly needs a different setting name/value, a full logout/login, or is unsupported in this VS Code build) — flagged as unresolved.
- **17:02:14:** recurrence, this time with a real stack trace. An exthost `TypeError`, "Cannot read properties of undefined (reading '0')", inside `onBuffer`/`onRawMessage` handlers, traced to `workbench.desktop.main.js` — **VS Code core's** IPC/`ManagedSocket` transport layer, not any extension. Root cause: a `JSON.parse` call in the transport layer threw `SyntaxError` on a malformed/truncated payload (`Unexpected token 's'...`), which was mishandled, and the next buffer callback then dereferenced `[0]` on `undefined`. This killed the extension host before any extension activated ("No extensions were activated"), and the renderer SIGABRT (code 135) fired the same second — likely fallout from the same corrupted transport state. Confirms the crash is a **VS Code core bug in the remote transport/socket layer**, exercised by Remote-SSH (which opens the managed socket to remote hosts) but not caused by Remote-SSH's own extension code. No exact-match GitHub issue found (closest non-matches: `microsoft/vscode#317596`, `vscode-remote-release#10804`, `#10902`) — worth filing fresh against `microsoft/vscode` (core) if it recurs, with this stack trace.
- Remote-SSH extension was on `0.124.0`; marketplace had `0.125.2026062315` available — updated as reasonable hygiene, unrelated to this specific bug.
- **Remediation applied each time:** full process kill (`pkill -f '/usr/share/code/'` — precise pattern, avoids matching the Claude Code CLI process) + relaunch. Cleared the immediate symptom both times (no crash in the following ~8–25s window, chatParticipant error fires once harmlessly, no loop). Not a root-cause fix — the core transport bug and the inert X11 override remain unresolved. User confirmed as of ~20:40 IST this was sufficient for now.
- **Remote host `uhet` ruled out as a cause:** disk 30%/55% used, memory 98GB free of 251GB, no OOM kills in `dmesg`, remote `vscode-server` logs showed clean exits, remote SSH auth/connectivity healthy throughout. One unrelated finding: an orphaned remote `vscode-server` CLI process had been running 48+ days (stale install, separate from the active server) — noted as a cleanup opportunity, not acted on.

**Status:** Workaround only (kill + relaunch). Two distinct unresolved upstream issues:

1. GitHub Copilot Chat 0.50.1 chatParticipant registration bug (Microsoft-side, fixed in Insiders 0.51, will resolve itself when Stable catches up).
2. VS Code core transport/socket JSON-parse bug causing intermittent Remote-SSH connection crashes (SIGABRT + exthost death) — no confirmed matching upstream issue, not yet filed by user.

**Follow-up if it recurs:** check `uhet`'s shell startup files (`.bashrc`/`.profile`/`.bash_profile`/MOTD scripts) for anything printing non-JSON output on non-interactive SSH sessions, since the malformed payload likely originates from data returned over that channel. Also worth revisiting why `~/.config/Code/argv.json`'s `ozone-platform-hint` was never honored.

---

### §2.25 — Firefox "downgrade" ping-pong: unattended-upgrades ignores the mozillateam PPA pin (2026-07-23)

**Symptom:** User ran `sudo apt update && sudo apt full-upgrade` and saw firefox reported as a **downgrade** (`1:1snap1-0ubuntu8` → `153.0+build1-0ubuntu0.26.04.1~mt1`).

**Root cause:** Two `firefox` package sources are configured:
- Ubuntu's own repo ships a transitional snap-wrapper stub, versioned with an epoch prefix (`1:1snap1-0ubuntu8`). Epoch always outranks any non-epoch version in dpkg/apt version comparison, regardless of the actual number after it.
- The Mozilla Team PPA (`mozillateam/ppa`, origin `LP-PPA-mozillateam`) ships the real Firefox `.deb` build, pinned to priority **1001** in `/etc/apt/preferences.d/mozilla-firefox` (priority ≥1000 = install even if apt's version comparison calls it a downgrade).

`apt full-upgrade`, run manually, honours the pin and installs the real PPA build — correct behaviour, but reported as "Downgrade" purely because of the epoch-vs-no-epoch version-string comparison.

`unattended-upgrades`, however, does **not** honour that pin: its `Allowed-Origins` list (`/etc/apt/apt.conf.d/50unattended-upgrades`) only included `${distro_id}:${distro_codename}[-security]` and the ESM origins — the mozillateam PPA origin was never in the list. So on its own schedule it installs Ubuntu's snap-stub instead. Confirmed recurring in `/var/log/apt/history.log`: unattended-upgrade → `1:1snap1-0ubuntu8` (2026-07-15, 2026-07-23 13:52), next manual `apt full-upgrade` → real PPA build reported as "Downgrade" (2026-07-16, 2026-07-23 15:04). Net effect each cycle: no actual firefox regression, just repeated churn and a confusing "downgrade" message.

**Fix applied (2026-07-23):** Added `"LP-PPA-mozillateam:${distro_codename}";` to `Unattended-Upgrade::Allowed-Origins` in `/etc/apt/apt.conf.d/50unattended-upgrades` via `.scratch/fix_unattended_upgrades_firefox.sh`. This lets unattended-upgrades install from the PPA too, so it should stop reverting firefox to the Ubuntu stub.

**Verification pending:** watch `/var/log/apt/history.log` over the next few unattended-upgrade cycles for firefox entries — expect no more `Downgrade`/`Upgrade` ping-pong between `1:1snap1-...` and the PPA version. If the stub reappears after this fix, the origin string or codename variable may need adjusting.

---

### §2.26 — CPU/DIMM temp creep + weak airflow despite audible fan (open, 2026-07-28)

**Symptom:** User investigating unrelated intermittent SSH keystroke-echo lag to `uhet` (see below) asked about laptop heat. `just temps` showed CPU (Tctl) 78.4°C, GPU 65°C, both DIMMs in ALARM (HIGH) state (58.2°C / 62.8°C against a configured 55°C `sensors` threshold, crit at 85°C). User then reported: fan is audible under load but they cannot feel much air movement at the vents.

**Trend (pulled from `logs/health-*.txt` `Tctl` lines, not previously tracked as a series — `logs/health-metrics.tsv` only records `dimm1_temp`, not CPU):**

| Date | Peak CPU (Tctl) |
|---|---|
| 2026-06-28 | 59–61°C |
| 2026-06-29 | 73–81°C |
| 2026-07-05 | 61°C |
| 2026-07-06 | 88.9 / 89.2°C |
| 2026-07-09 – 07-11 | 62–69°C |
| 2026-07-14 | 80.4 / 94.9°C |
| 2026-07-15 | 83.6°C |
| 2026-07-18 | 76.8°C |
| 2026-07-28 | 78.4–85.0°C |

Peak temps climbed roughly 25–30°C over the month from a ~60°C late-June baseline and have held in the 80s–90s since mid-July.

**Fan control investigation:** No fan RPM sensor is exposed to userspace on this hardware (no `fan*_input` under `/sys/class/hwmon`, no matching `/sys/class/thermal/cooling_device*` fan type — only `Processor` and `PCIe_Port_Link_Speed` cooling devices). Fan control is entirely EC-managed via `tccd` (TUXEDO Control Center daemon, active). Active profile on AC power (`/etc/tcc/settings` → `stateMap.power_ac`) is a custom profile `thor_gaming` ("Thor Gaming" — *"Temperature-tracking fan curve optimised for gaming. Aggressive ramp, quiet at idle."*), with a custom CPU fan curve reaching **100% speed at 80°C**. Since Tctl is already sitting at 78–85°C, the curve should already be commanding near-max fan speed — so this is not a "curve too conservative" problem.

**Initial working hypothesis (superseded, see below):** fan audibly spinning but weak airflow at the vents, combined with the temp trend, pointed to **airflow obstruction** (dust in intake/exhaust vents, or vents blocked by surface placement) rather than fan/EC failure. Revisited same day after user reported hearing no fan at all at idle (68.4°C Tctl) — that observation didn't fit a dust-obstruction-only theory (dust would leave the fan audible-but-weak, not silent) and prompted deeper investigation into `tccd` itself.

**Root cause found (2026-07-28): `tuxedo-drivers` 4.22.2 → 4.22.3 regression broke fan control kernel modules.**

- `journalctl -u tccd` showed fan control genuinely working Jul 5–10 (`tuxedo-io ver 0.3.9 [interface: uniwill]` → `FanControlWorker: initializeFanControl: tuxedo-io available` → `Detected 2 fans`).
- `unattended-upgrades` bumped `tuxedo-drivers` 4.22.2 → 4.22.3 on **2026-07-10 23:59:53** (`/var/log/dpkg.log`).
- Every tccd start from **2026-07-13 08:57:53** onward logs `FanControlWorker: onStart: Fan API not available` — 34 occurrences through 2026-07-28, no exceptions. (Journal retention only goes back to 2026-07-05 per the 8G/persistent cap, so nothing earlier is visible, but the Jul 5–10 success logs already prove it wasn't always broken.)
- Currently `tuxedo_io` and `tuxedo_keyboard` kernel modules are **not loaded** — only `tuxedo_compatibility_check` is. No `/dev/tuxedo*`/`/dev/uniwill*` device nodes exist. Kernel log for the current boot shows `tuxedo_keyboard: module init` firing 4 times within ~1 second then the module disappearing from `lsmod` — a probe failure/crash-retry loop, not a clean load. `tuxedo_io` never even attempts to load this boot (it depends on `tuxedo_keyboard` staying resident).
- Not a stale-DKMS-vs-kernel mismatch: `dkms status` reports `tuxedo-drivers/4.22.3, 6.17.0-23-generic: installed (Original modules exist)`, and `modinfo` vermagic matches the running kernel. The module builds cleanly, it fails at runtime probe.
- Matches known upstream TUXEDO bug patterns on uniwill-interface hardware — see [tuxedo-control-center#486](https://github.com/tuxedocomputers/tuxedo-control-center/issues/486) and [#415](https://github.com/tuxedocomputers/tuxedo-control-center/issues/415) (fan detection breaking after a TCC/driver package upgrade). Nothing pins the exact 4.22.3 regression by name upstream.

**Practical implication:** since 2026-07-13, `tccd` has had no working connection to the EC fan control interface — the custom `thor_gaming`/`thor_max_fan` curves have not been reaching hardware at all. Actual fan behaviour since then has been whatever the EC's own firmware fallback does, unmanaged. This explains both the earlier "audible but weak" airflow report and the later "no fan audible at all at 68°C idle" report better than a pure dust-obstruction theory, and lines up with the CPU/DIMM temp creep timeline above.

**Fix, staged by risk (script: `.scratch/fix_tuxedo_fan_api.sh`, sudo required, user must run):**
1. Capture `dmesg` tuxedo/uniwill lines on a fresh boot (not visible in the buffer sampled during diagnosis — this boot hadn't logged any tuxedo-related lines yet).
2. Clean module reload: `sudo modprobe -r tuxedo_io tuxedo_keyboard tuxedo_compatibility_check && sudo modprobe tuxedo_io` (also reloads dependencies), then `sudo systemctl restart tccd` and check for `tuxedo-io available` / `Detected N fans` in the journal.
3. If that doesn't fix it: force a clean DKMS rebuild — `sudo dkms remove tuxedo-drivers/4.22.3 -k 6.17.0-23-generic && sudo dkms install tuxedo-drivers/4.22.3 -k 6.17.0-23-generic`.
4. If still broken: downgrade-test `sudo apt install tuxedo-drivers=4.22.2` to confirm the regression, then file upstream at `gitlab.com/tuxedocomputers/development/packages/tuxedo-drivers`.

**Correction (2026-07-28, same day):** the modprobe reload in `fix_tuxedo_fan_api.sh` failed with `modprobe: ERROR: could not insert 'tuxedo_keyboard': No such device` (-ENODEV from the module's own init, not a build/dependency issue). Root cause is NOT the 4.22.3 upgrade — it's a hardcoded compatibility gate in `tuxedo_compatibility_check.c`'s `tuxedo_is_compatible()`: it requires DMI vendor strings (`sys_vendor`/`board_vendor`/`chassis_vendor`) to read `"TUXEDO"` (this machine reads `"SKIKK"`) OR the CPU to be in a hardcoded exemption table capped at AMD family ≤25 (0x19). This machine's Ryzen 9 9955HX3D is family 26 (Zen5, "Fire Range") — not in the table at all. Confirmed via full source diff that this exact check is byte-identical between 4.22.2 (the version active during the confirmed-working Jul 5–10 window) and 4.22.3 — **downgrading tuxedo-drivers would not help**, this gate predates both versions. Full version history on this machine: `4.18.1` (installed 2026-01-10) → `4.22.2` (2026-05-24) → `4.22.3` (2026-07-10). What made fan control work Jul 5–10 specifically is unresolved (not the driver version, not the kernel — both unchanged across the window) but not worth chasing further; it doesn't change the current state.

**4.18.1 pin ruled out (2026-07-28):** checked whether the earliest apt-installed version (4.18.1, predating 4.22.2) lacked the gate — it doesn't. Confirmed via GitLab tag `v4.18.1`'s `tuxedo_compatibility_check.c`: identical family-≤25 AMD exemption table and identical `"TUXEDO"` DMI-vendor-string requirement. Pinning to 4.18.1 would fail identically (-ENODEV). The gate predates every version ever installed on this machine — there is no earlier apt-installed release to reconstruct a working module from. The Jul 5–10 working window remains unexplained (not chased further). Side note: a maintained AUR package `tuxedo-drivers-nocompatcheck-dkms` exists that patches out exactly this gate — same risk category (untested third-party patch on this exact board) as the community `clevo-drivers` fork already ruled out above; not pursued for the same reason, but its existence corroborates this is a known, common pain point rather than a quirk specific to this machine.

**BIOS-level Operating Mode found and changed (2026-07-28):** the BIOS/hotkey fan control avenue turned up something real, distinct from the driver issue. No dedicated fan hotkey exists on this chassis (only backlight controls on the function row). But BIOS setup (AMI Aptio, firmware version `2.22.0059`) has an **Operating Mode** selector (Office Mode / Balance Mode / Turbo Mode) explicitly documented in the BIOS UI as controlling "Fan Speed and CPU/GPU overall performance and heat dissipation" — a genuine EC-level, OS-independent lever. It was set to **Balance Mode** (not Turbo) this whole time; user changed it to **Turbo Mode**. This is plausibly a real contributor to the temp creep — a less aggressive EC fan curve running underneath `tccd`'s already-broken control (see above) the entire time. **Confirmed effective, post-reboot (2026-07-28):** idle temps dropped materially — CPU (Tctl) 73–75°C → 65.4°C, GPU 60–61°C → 56°C, DIMM1 54°C → 52°C, DIMM2 58°C (ALARM) → 55.5°C (still marginally over the 55°C `sensors` threshold, but no longer clearly in alarm territory). ~8–10°C idle improvement from a single BIOS setting, independent of the still-broken `tuxedo_io`/`tuxedo_keyboard` driver. This is the interim mitigation going forward until #376 lands. **Restress test under Turbo Mode (2026-07-28):** ran the same 8-thread synthetic load test. Result: Turbo Mode does NOT help under sustained load — Tctl hit ~97.2°C within 4s (vs 95.5°C in 6s under Balance) and stayed pinned near that ceiling for the full 60s load window, vs Balance Mode's ~87°C sustained plateau. Recovery after load stopped was faster (~30–40s back to ~67-71°C vs ~2min previously), but that doesn't offset holding near-throttle for the whole load period. Turbo Mode's benefit is idle/light-load only (confirmed ~8-10°C cooler at idle, above) — it does not change the EC's fan response under sustained heavy load, and may ride closer to the throttle ceiling there. **The "avoid sustained heavy load until #376 lands" guidance is unchanged** — Turbo Mode does not substitute for it.

**Alternative investigated and ruled out:** `nbfc-linux` (community EC-direct fan control, independent of TUXEDO's driver/compatibility gate) was evaluated as a bypass. No existing config covers this chassis (GM6HG7Y) or any close Tongfang sibling — only one unrelated Tongfang config exists in the whole repo (a different X6-series board). Building a config from scratch requires manual DSDT reverse-engineering and hand-written EC register writes; official nbfc-linux docs warn wrong writes risk unexpected shutdowns or permanent battery damage, recommending testing with the battery removed. Higher risk/effort than patching `tuxedo_keyboard` directly (which at least reuses TUXEDO's validated EC logic) — not pursued.

**Upstream precedent found:** [tuxedo-drivers#370](https://gitlab.com/tuxedocomputers/development/packages/tuxedo-drivers/-/work_items/370) — identical mechanism, different CPU: AMD Zen4/Hawk Point (family 25) was missing from the same skip-list and got added quickly (closed/fixed 2026-06-26). TUXEDO's pattern is incremental per-model whitelisting, not fixing the hardcoded-cap design — good odds of a fast fix if reported. No existing issue covers family 26/Zen5 or this board. Issue draft prepared at `.scratch/gitlab_issue_tuxedo_family26.md`, modeled on #370; filed manually by user via GitLab web UI 2026-07-28: [tuxedo-drivers#376](https://gitlab.com/tuxedocomputers/development/packages/tuxedo-drivers/-/work_items/376).

**Interim guidance (no software fan control until fixed):** EC firmware's own baseline thermal curve is still active and independent of the OS driver (standard on all laptops — critical-temp safety shutdown doesn't depend on `tuxedo_io`), so this is not "no cooling at all," just unmanaged/unconfirmed cooling. Recommended: avoid sustained heavy load (gaming, long compute/inference jobs) until resolved; do the compressed-air vent cleaning pass regardless (zero risk, independent contributor, doesn't depend on driver fix); monitor temps via `just temps`/`just health-snapshot` during any heavier session to see how hot the EC default curve actually allows. Do not pursue the community-patched `tuxedo_keyboard` fork (forces `tuxedo_is_compatible()` to return true) as a stopgap — untested EC-write code on this exact board is not worth the interim risk reduction; reconsider only if temps reach genuinely dangerous territory (sustained 90s, throttling, shutdown).

**Why it worked Jul 5–10 then stopped (resolved, moderate confidence):** the compatibility gate is not what changed — it's byte-identical between 4.22.2 and 4.22.3. What actually happened: DKMS rebuilding the module on the Jul 10 23:59 upgrade replaced the on-disk `.ko` but did not force-unload the already-resident module in memory, so the *old* (already-loaded, still-working) module kept running fan control through the rest of that boot session (~57h). The next reboot — **2026-07-13 08:57:49** — was the first to load the freshly-built, gated 4.22.3 module, and that timestamp matches the first `Fan API not available` failure to the minute. So it never really "worked under 4.22.3" — it kept running the old in-memory module until a reboot forced the reload. Journald's 30-day cap means boot history before 2026-07-05 isn't available, so it's not fully confirmed whether 4.22.2 (already gated per the source diff) was ever cleanly loaded before that — but no BIOS/firmware-flash evidence was found in `fwupdmgr get-history` or any log for the Jul 10–13 window, ruling out a DMI-vendor-string-change explanation for lack of supporting evidence (not fully eliminated, just unconfirmed).

**BIOS date discrepancy, resolved (2026-07-28):** `bios_date` reads `03/26/2026` — three months later than the "Dec 2025 BIOS" this repo's CLAUDE.md documented from earlier work. Investigated: `fwupdmgr get-history` shows only one entry, a UEFI dbx (Secure Boot forbidden-signature DB) update applied 2026-07-16 — unrelated capsule, doesn't touch `bios_date`/`bios_version`. No BIOS/UEFI firmware activity in `dpkg.log` (current + rotated) or `journalctl -u fwupd` across all retained boots (back to 2026-07-05). Critically, the DSDT OEM revision — the value that actually gates NVPCF fix logic — is unchanged at `0x01072009`, confirmed via the current boot's kernel ACPI table-load line. Conclusion: no real reflash happened; "Dec 2025 BIOS" was inferred from vendor changelog/OEM-revision matching, not read directly from the `bios_date` DMI field at the time — a documentation gap, not a silent update. NVPCF fix status stands as documented; no re-check needed.

**BIOS-level / hotkey fan control, investigated as a bypass:** no Thor 16/GM6HG7Y-specific documentation found, but TUXEDO's Sirius 15 has a precedent — a dedicated EC-level fan-boost key, fully independent of any OS driver. Not confirmed to exist on this chassis. User to test physically (zero risk): dedicated fan-icon key or Fn+F5/Fn+F6 while watching `just temps`; and BIOS setup (F2/Del at boot) → Advanced/Chipset for a Fan Control Mode option (typical on this AMI Aptio-style firmware family). Not yet tried.

**Stress-test result (2026-07-28), supporting evidence for #376:** synthetic 8-thread load (`yes` loops) confirmed the EC default curve is reactive (fan audibly ramped) but under-tuned: Tctl spiked 71.2°C → 95.5°C (CPU's own silicon throttle point) within ~6 seconds of load starting — the fan didn't react fast/hard enough to prevent hitting throttle. Plateaued ~87°C sustained; settled back to ~72°C within ~2 minutes of load stopping (not stuck elevated). Confirms the EC firmware fan isn't dead/silent, just soft compared to what the gated `thor_gaming` curve (100% at 80°C) would do.

**Status:** Root cause fully identified (compatibility gate, not fixable locally without patching EC-write code), and the working→broken transition mechanism now understood (DKMS module-reload timing on reboot, not a code regression). Upstream issue [tuxedo-drivers#376](https://gitlab.com/tuxedocomputers/development/packages/tuxedo-drivers/-/work_items/376) filed 2026-07-28 — primary remediation path, awaiting maintainer response. EC-direct bypass via nbfc-linux ruled out for now (no config exists for this chassis). BIOS/hotkey bypass untested, worth trying. Dust/airflow physical inspection (compressed air pass) still planned as an independent secondary check. Revisit `logs/health-metrics.tsv`/`health-*.txt` Tctl trend after any dust cleaning and separately once #376 lands a fix.

**Related, same session:** SSH keystroke-echo lag to `uhet` was separately investigated and the network-path-latency theory was ruled out (400-packet extended ping: 98.5% of samples in a tight 39–74ms band, sparse/non-periodic outliers up to 235ms, too rare to explain sustained lag) — current leading theories are host-side (`uhet` CPU/PTY scheduling) or client-side (Byobu/tmux redraw overhead), still unresolved. If local CPU is under load-induced scheduling pressure from the same thermal/airflow issue, that could plausibly connect to the terminal lag, but this has not been tested.

### §2.27 — Two freeze/cutoff events in short succession (2026-07-31)

**Two abrupt power-loss events occurred today:** ~10:23 IST and ~12:12 IST. Both showed as hard cutoffs in the journal — no shutdown target reached, no OOM/panic/MCE/thermal-trip logged. `journalctl --list-boots` showed boot -2 lasting only 24s and boot -1 running ~107min before cutting off mid-normal-operation.

**~10:23 event clarified, not benign:** user has since clarified the screen froze/hung (unresponsive) and they performed a **manual hard power reset** to recover — this is a genuine system freeze/fault symptom, not a voluntary reboot, and should not be treated as self-inflicted or dismissed as noise. It differs from the ~12:12 event in that the freeze itself was directly observed by the user before the cutoff, whereas at ~12:12 the journal simply stopped with no preceding hang witnessed — so from logs alone we cannot distinguish "froze then lost power" from "instantly lost power" for that second event; a freeze-then-cutoff mechanism is plausible there too.

**Possible shared root cause (unconfirmed):** these are now the second and third abrupt-loss/freeze-adjacent events surfaced in this session's investigation (following the prior GNOME/logind s2idle suspend freeze in §2.18). Two freeze/cutoff incidents within ~2 hours of each other raises — but does not confirm — the possibility of a common underlying trigger (e.g. a GPU/driver hang, or an EC/thermal fault causing unresponsiveness ahead of a full cutoff). No journal evidence currently links the two events; this is a hypothesis to watch, not a conclusion.

**Diagnostic steps taken for the 12:12 event:**
- `journalctl` boot analysis: no clean shutdown target reached, no error burst preceding the cutoff.
- sudo-level kernel ring buffer / MCE-EDAC grep / `dmesg` error-level check: all clean — no hardware error or thermal trip logged.
- SMART health on both NVMe drives: PASSED, 0 media errors. "Unsafe Shutdowns" counter = **67 on both drives** at time of check — recorded here as a baseline for future comparison.
- `health-save` log review: no failed systemd units, GPU PM fix still active (`NVreg_DynamicPowerManagement=0x01`), ASPM config as expected, no D3cold storm.

**Anomaly noted, not confirmed causal:** NVRM `nvAssertFailedNoLog @ osapi.c:1939` (previously documented in §2.20 as a boot-only/3x/benign pattern) fired **repeatedly throughout the 12:12 boot's runtime** — this deviates from the boot-only pattern and is worth tracking if it recurs.

**Root cause: INCONCLUSIVE.** Consistent with either:
1. An EC-level thermal cutoff — BIOS is in Turbo Mode (§2.26), documented as throttling ~97°C under sustained load; an EC-level thermal cutoff would bypass the OS ACPI thermal-trip logging path entirely, so absence of a logged trip doesn't rule it out.
2. Another EC/firmware-level power fault.

No software-side cause (OOM/panic/MCE/failed unit) is implicated.

**Independent corroboration:** the health-snapshot cron cadence (`*/2` min, from the ongoing §2.26 thermal trial) caught the gap — the 12:12:01 scheduled snapshot never ran (4-min gap between 12:10:01 and 12:14:01 in `logs/health-metrics.tsv`), independently confirming the cutoff time.

**Status: MONITORING.** Watch for recurrence; if the SMART "Unsafe Shutdowns" counter increments again without a known manual-reset explanation, that's stronger evidence of a real recurring hardware/firmware fault. User noted that going forward they will report any future freeze/reset events to Claude after getting back online, so future investigations know upfront which events were manual resets vs unexplained cutoffs.

**Decision (2026-07-28): run a multi-day real-usage trial before committing to the compatibility-gate-bypass patch.** BIOS Turbo Mode fixed idle temps (~8–10°C cooler) but confirmed NOT to fix sustained-load throttling (Tctl still pins ~97°C under sustained 8-thread load, see above). Rather than deciding on the community `tuxedo-drivers-nocompatcheck-dkms` patch (untested third-party EC-write code) from synthetic load data alone, plan is to use the laptop normally for the next few days under Turbo Mode and revisit the risk/benefit call using real usage data.

**Auto-logging set up to support the trial.** `just health-snapshot` (`Justfile`) previously logged `dimm1_temp` but not CPU Tctl, GPU temp, or system load — the metric that actually matters for this decision (sustained-load throttling) was invisible in the trend data. Extended the same recipe, append-only (existing 7 columns unchanged, 4 new columns added at the end: `cpu_tctl`, `gpu_temp`, `load1`, `dimm2_temp`) using the same `sensors`/`nvidia-smi`/`/proc/loadavg` commands as the `temps` target. Also fixed a pre-existing, unrelated bug hit along the way: `grep -c '^Z' || echo 0` for the zombie-process count — `grep -c` exits 1 (but still prints `0`) whenever there are zero zombies, the normal case, so `|| echo 0` fired spuriously and appended a duplicate field with an embedded newline, splitting the TSV row across two physical lines. This corrupted roughly a third of historical rows (confirmed: 199/1185 lines had 4 fields instead of 7) and would have corrupted every future row including the new columns; fixed by dropping the redundant `|| echo 0`. Automatic periodic execution was already in place and did not need new infrastructure: `crontab -l` shows `*/15 * * * * cd .../system_queries && just health-snapshot >> logs/health-snapshot-cron.log 2>&1`, confirmed actively firing (verified `cron.service` active, log entries current to the minute). No systemd --user timer was added — it would only duplicate the existing cron job. Verified end-to-end: post-fix rows are single-line, 11 fields, all populated (e.g. `cpu_tctl=94.5`, `gpu_temp=58`, `load1=1.65`, `dimm2_temp=55.5`).

**Note for a future session:** the auto-logging (existing cron entry, now extended) is expected to keep running unattended for the trial period — no action needed to keep it going. Revisit `logs/health-metrics.tsv` `cpu_tctl`/`dimm2_temp` columns after a few days of normal use to inform the compatibility-gate-bypass-patch decision; nothing needs to be manually stopped unless the trial is abandoned early, in which case just leave the cron entry running (it's cheap and useful for `journal-watch`-style trend history regardless).

---

### §2.28 — Boot-screen hard freeze — NVIDIA RM lock assertion during driver init (2026-08-04, RESOLVED)

**Symptom:** Laptop froze on the boot screen; user power-cycled repeatedly. Last known clean shutdown 2026-08-04 09:45:22 (`systemd-poweroff` completed). 6 failed boot attempts logged between 10:37–10:43 IST, followed by a recovery-mode (`nomodeset`) boot which came up stable — that recovery boot is the current state, not a resolved normal boot.

**Investigation:** `journalctl -b -1` (the boot attempt that got furthest, 10:37:46–10:38:04, ~18s) showed clean amdgpu init (`[drm] Initialized amdgpu 3.64.0 for 0000:07:00.0 on minor 2`) followed immediately by NVIDIA open-kernel-module (580.126.09) load, which hit repeated `NVRM: nvAssertFailedNoLog: Assertion failed: !rmapiLockIsOwner() @ rmapi.c:563` (5 occurrences total), then hung dead with no further log activity (11s gap then journal ends). The subsequent 5 boot attempts each died progressively earlier (fsck stage → modules-load → udevd), never reaching NVIDIA init at all; one showed "System Journal ... corrupted or uncleanly shut down". No ACPI/DSDT, PCIe/ASPM, NVMe, OOM, or watchdog errors were present anywhere in the window. `/etc/modprobe.d/nvidia-power.conf` and all `/etc/default/grub.d/*.cfg` drop-ins (`10-skikk-platform.cfg`, `99-nvidia-pm.cfg`, `50-tuxedo-fix-nvidia-preserve-vram-suspend.cfg`) were verified intact and unmodified — not implicated. No kernel/nvidia/grub package updates in `dpkg.log` correlate with this — single kernel `6.17.0-23-generic` installed, matches running kernel. Only loosely-correlated recent package change: `tuxedo-control-center` 3.0.7→3.0.8 upgraded 2026-08-03 13:25 (touches GPU/fan power profiles but no direct log evidence linking it).

**Root cause assessment:** Distinct failure class from the already-fixed `pm_runtime_work` runtime-PM freeze (§2.17). This is an NVIDIA RM (Resource Manager) internal locking-discipline assertion firing during driver *init*, not runtime PM. Not caused by this system's config — ASPM/PM cmdline params and `nvidia-power.conf` all verified intact. Leading hypothesis: intermittent driver-internal init race in nvidia-open 580.126.09 on Blackwell (RTX 5070 Ti), possibly triggered by GPU/EC state left over from pre-freeze session activity (suspend/sleep history) that a full power cycle (not just repeated quick power-button presses) would clear — the 5 repeat failures dying progressively earlier without reaching NVIDIA init at all is more consistent with insufficient state-reset between rapid power cycles than with a deterministic driver bug (a deterministic bug should hang at the same point every time).

**Status: RESOLVED (2026-08-04, same day).** Full power-off (30s+, not a quick power-cycle) followed by a normal (non-recovery) boot came up clean — confirms the "insufficient state-reset between rapid power cycles" hypothesis over a deterministic driver bug. `journalctl --list-boots` shows a genuinely new, distinct boot (`bf5bfb9081084ab9bac0fb9cb39ae84d`, 2026-08-04 11:12:30 IST) separate from the prior death sequence (boots -1 through -6, all within 10:37–10:47). `journalctl -b 0` contains **no** occurrence of `rmapiLockIsOwner()` / `rmapi.c:563`. NVIDIA driver init completed cleanly (`NVRM: loading NVIDIA UNIX Open Kernel Module ... 580.126.09`, modeset + DRM init, persistenced started), `nvidia-smi` reports the RTX 5070 Ti Laptop GPU functional and actively rendering the desktop session, no Xid/OOPS/BUG/Call Trace anywhere in the boot. `/proc/cmdline` still carries every expected param from `10-skikk-platform.cfg` and `99-nvidia-pm.cfg` (`pcie_aspm=force`, `pcie_aspm.policy=default`, `amd_pstate=active`, `nvidia-drm.modeset=1`, `nvidia.NVreg_DynamicPowerManagement=0x01`) — none dropped by the recovery-mode detour.

A separate, apparently benign NVRM debug assertion recurred ~30 times this boot, correlated with ordinary GUI/app activity (gnome-shell, Chrome, Guake launches): `NVRM: nvAssertFailedNoLog: Assertion failed: 0 @ osapi.c:1939`. This is a different code path from the freeze-causing `rmapi.c:563` assertion and did not cause any hang — driver stayed responsive and functional throughout. Not treated as resolved-or-not for this entry; flagged as a separate lower-severity item to watch (no independent action taken this session — revisit only if it correlates with an actual freeze or perf issue in future).

**Evidence (key log lines, `journalctl -b -1`):**

```
NVRM: loading NVIDIA UNIX Open Kernel Module for x86_64 580.126.09
NVRM: testIfDsmSubFunctionEnabled: GPS ACPI DSM called before ... init
NVRM: nvAssertFailedNoLog: Assertion failed: !rmapiLockIsOwner() @ rmapi.c:563  (x2)
[drm] Initialized amdgpu 3.64.0 for 0000:07:00.0 on minor 2
systemd-rfkill.service: Deactivated successfully.
--- 11s gap, no log activity ---
NVRM: nvAssertFailedNoLog: Assertion failed: !rmapiLockIsOwner() @ rmapi.c:563  (x3)
--- journal ends, boot dead ---
systemd-journald: File system.journal corrupted or uncleanly shut down, renaming and replacing.
systemd[1]: Finished systemd-poweroff.service - System Power Off. (last clean shutdown, 09:45:22)
```

---

### §2.29 — Post-upgrade boot hang, different signature from §2.28, AC-state hypothesis (2026-08-04, recurred 2026-08-06)

**Context:** Immediately after upgrading `nvidia-driver-580-open` (2:580.126.09-2tux1) → `nvidia-driver-595-open` (595.84-0ubuntu0.26.04.1) to address §2.28's `rmapiLockIsOwner()` freeze (clean apt install, DKMS rebuilt and signed all 5 modules without error — see `.scratch/upgrade_nvidia_595.log`), the user rebooted to activate the new driver. Boot hung again. User waited ~30s, unplugged the AC adapter, power-cycled — it booted successfully on the second attempt.

**Investigation:** The failed boot (`531b673baad149508fa467059ca1b813`, started 13:10:49 IST) is **not** a recurrence of §2.28's signature — `rmapiLockIsOwner()`/`rmapi.c:563` does not appear anywhere in its log, and it never reached GPU driver load at all. It died during early systemd userspace bring-up (last activity: `systemd-modules-load` inserting `yt6801`/`msr`/`ppdev`/`lp`, then `systemd-oomd.service` started, then journal capture stops mid-stream with no shutdown-target reached — no panic, OOPS, or `-p err` entries beyond benign `usbhid` warnings). A materially earlier and different failure point than §2.28.

The successful boot (`bbb354f5f1e7457293397981177b0b7b`, 13:12:46 IST, ~2 min after the hang) loaded `nvidia-driver-595-open` (595.84) cleanly — `NVRM: loading NVIDIA UNIX Open Kernel Module ... 595.84`, DRM/modeset init, persistenced registered the GPU — confirmed via `nvidia-smi` (`Driver Version: 595.84`, GPU active). No `rmapiLockIsOwner()` assertion. `/proc/cmdline` intact (`pcie_aspm=force`, `pcie_aspm.policy=default`, `amd_pstate=active`, `nvidia-drm.modeset=1`, `nvidia.NVreg_DynamicPowerManagement=0x01`).

**New data point — AC adapter state correlation (single occurrence, not yet confirmed causal):** the failed boot logged `ACPI: AC: AC Adapter [AC0] (on-line)` (AC plugged in); the successful boot logged `ACPI: AC: AC Adapter [AC0] (off-line)` (AC unplugged, confirming "took out the cable" = pulled the AC adapter, not some other cable). §2.28's resolution only recorded "30s+ power-off then normal boot" with no AC-state tracking, so this wasn't ruled in or out there. One data point each way is not enough to confirm causation — noting as a hypothesis to test on the next occurrence (check/vary AC state deliberately before power-cycling), not a settled explanation. Possible loose tie to §2.27 (unexplained abrupt power-loss event, EC-level thermal cutoff suspected but unconfirmed) if this points at EC/power-delivery flakiness generally, but no direct evidence links them yet.

**Separately, boot 0 (595.84) shows a new benign-so-far NVRM assertion during runtime GPU-context churn** (not at boot, not fatal): `NVRM: nvAssertFailedNoLog: Assertion failed: 0 @ osapi.c:2075`, ~31 occurrences correlated with RustDesk/Chrome creating GPU contexts. System stayed fully responsive throughout both bursts. Different code path from both `rmapi.c:563` (§2.28) and the previously-logged `osapi.c:1939` (580.126.09, see §2.28's closing note) — driver-version-specific assertion, same class of apparently-cosmetic NVRM logging noise. Watch only.

**Status (as of 2026-08-04): MONITORING.** The driver upgrade cannot be credited with fixing §2.28 yet — this incident didn't exercise that code path (never reached GPU driver load), so §2.28's original bug remains unconfirmed-fixed-or-not under 595.84. This is a distinct, not-yet-understood early-boot hang. If it recurs: (1) note AC adapter state before and during the power-cycle attempt to test the correlation hypothesis, (2) capture `journalctl -b -1` immediately after recovery per this entry's method, (3) if the *original* `rmapiLockIsOwner()` signature reappears under 595.84, that reopens §2.28 as unresolved-by-upgrade; if this early-userspace hang signature recurs instead, treat it as its own bug independent of NVIDIA driver version.

**Update 2026-08-06 — recurrence, same signature.** Timeline (verified via `journalctl --list-boots` / `journalctl -b`):

- Boot -2 ran normally 10:01–15:20 IST, then the journal abruptly stopped mid-stream at 15:20:26 with no shutdown-target, poweroff, panic, OOM, or thermal log — a hard freeze. Machine was hard-power-cycled.
- 72-minute gap with no journal activity (machine fully off).
- 16:32:45 IST: power-on attempt (boot -1) failed after ~31ms / 1126 log lines — died right after `systemd-oomd`/`systemd-resolved` start, before udev or GPU driver load. No NVIDIA driver lines, no panic/thermal/OOM signature. Structurally matches this entry's original 2026-08-04 pattern (early-userspace death, well before GPU init), not §2.28's NVRM assertion pattern.
- 16:33:29 IST: user unplugged the AC adapter, then retried — second attempt (boot 0) succeeded on battery power. This is the boot the investigation was run from.

**AC-power correlation update (confirmed both sides, 2/2):** AC was confirmed plugged in during the failed 16:32:45 attempt — consistent with the 2026-08-04 occurrence (AC on-line during that failure too), so "AC plugged in during hang" is now **2-for-2**. This time the user also deliberately unplugged AC before the successful 16:33:29 retry, so "AC unplugged → successful retry" is now confirmed for occurrence 2 as well, matching occurrence 1 (also AC-off-line on its successful retry). The correlation AC-plugged=fail / AC-unplugged=success is therefore **confirmed on both sides across both occurrences (2/2)**. n=2 is not exhaustive proof of causation — it does not rule out coincidence or a confound (e.g. a charger/PD negotiation transient that happens to correlate with AC presence rather than AC presence itself being causal) — but two-for-two on both halves of the pattern is a meaningfully stronger basis than the prior single-sided confirmation, and warrants treating AC state as the leading hypothesis pending a root-cause identification.

**Status (as of 2026-08-06): RECURRING PATTERN (2 occurrences, 2026-08-04 and 2026-08-06), same early-userspace-death signature both times.** AC-plugged-in-during-hang confirmed on both occurrences; AC-unplugged-during-successful-retry now also confirmed on both occurrences. Root cause not yet identified — see root-cause research notes below. Escalation trigger: if a third occurrence happens despite the AC-avoidance workaround (boot on battery, plug in after boot), treat as strong evidence of a distinct fault worth deeper EC/power-delivery investigation, per the loose §2.27 tie noted above.

**Cross-reference (2026-08-06, later same day):** This AC-boot-hang has now co-occurred with a §2.34 hard-freeze **twice in one day** — the 15:20 freeze immediately preceded the 16:32/16:33 occurrence above, and a second freeze at 17:04 was followed by another failed/successful AC-boot-hang pair at 17:05:13/17:05:54. §2.34 now tracks 6 total freeze occurrences across the Jul 23–Aug 6 window, with podman/container workload ruled out as a trigger, elevating this to a recurring-enough pattern to prioritize a BIOS/EC firmware check. See §2.34's 2026-08-06 (later) update for full detail — the working hypothesis is that this hang and the §2.34 freezes are the same underlying EC/PM fault manifesting two ways, though not yet proven at n=2 co-occurrences.

**Root-cause research (2026-08-06):** the failure profile — hangs before GPU driver load, in early userspace, specifically when AC is connected at cold boot — points toward EC/BIOS-level USB-C PD (or barrel-jack AC-detection) handshake stalling, not a kernel/NVIDIA driver bug. This class of fault is documented across vendors: AMD Framework laptops have known charger-negotiation compatibility issues with certain USB-C PD sources; several vendor forums (Dell, HP, Lenovo, generic Tongfang/Clevo barebone rebrand threads on badcaps.net and Win-Raid) report BIOS/EC firmware bugs where AC/USB-C power detection at boot stalls EC-to-BIOS handoff, fixable by BIOS/EC firmware updates or by an EC reset (power off, disconnect AC and battery if possible, hold power button 30s, reconnect, boot). No Tongfang GM6HG7Y-specific report was found (rebrand chassis, thin public documentation), so no confirmed matching erratum — this is pattern-matching to the general class of bug, not a verified root cause. Recommended next steps, easiest/lowest-risk first: (1) adopt "boot on battery, plug AC in after boot" as the standing workaround — trivial, zero risk, already validated 2/2; (2) check for a BIOS/EC firmware update beyond the current version (doc/machines/skikk-thor.md notes a Dec 2025 BIOS already fixed one unrelated bug, so the vendor is shipping updates) and check BIOS setup for a USB-C/Type-C PD charging toggle to test disabling; (3) test whether the phenomenon is charger-specific by trying a different PD source/wattage if a second charger is available; (4) if it recurs a third time despite the workaround, file with SKIKK/Tongfang's BIOS support channel with both journal captures attached.

---

### §2.30 — Microsoft Edge dock icon unpinnable — local .desktop override lost StartupWMClass (2026-08-05)

**Symptom:** Launching Microsoft Edge from its pinned ubuntu-dock icon spawned a second, unpinnable icon alongside the pinned one instead of activating the existing pinned favorite.

**Root cause:** `~/.local/share/applications/microsoft-edge.desktop` is a local override that shadows the vendor file at `/usr/share/applications/microsoft-edge.desktop` per XDG desktop-file precedence. The local copy had previously been hand-edited to add `--ozone-platform=x11` to its `Exec=` line, and that edit dropped the `StartupWMClass=microsoft-edge` line present in the vendor original. Without `StartupWMClass`, GNOME Shell (ubuntu-dock extension) cannot match the running Edge window back to the pinned favorite's `.desktop` identity, so it treats the launched window as a new, unpinned app and creates a second icon.

**Fix applied:** Added `StartupWMClass=microsoft-edge` back to the `[Desktop Entry]` section of `~/.local/share/applications/microsoft-edge.desktop`, then ran `update-desktop-database ~/.local/share/applications`. Session is Wayland, so GNOME Shell only picks up desktop-file changes on next login — a quick reload (Alt+F2 `r`) does not work under Wayland; logout/login required.

**Status: Live (fix applied), pending logout/login to take effect.** General lesson: any future hand-edit of a locally-overridden `.desktop` file's `Exec=` line must preserve `StartupWMClass=`, or dock/taskbar pinning breaks again.

---

### §2.31 — Guake landed on wrong monitor despite matching prior known-good display-n (2026-08-05)

**Context:** Builds on the existing GDK-index-vs-xrandr-index quirk for Guake's `display-n` setting (see `random_llm_projects/.claude/rules/skill-hygiene.md`, Desktop-Linux section) — this entry records a session-specific empirical finding, not a new mechanism.

**Symptom:** Guake dropdown terminal was opening on the external monitor instead of the laptop's built-in screen.

**Investigation:** Queried GDK monitor geometry directly (`Gdk.Display.get_default()` via `/usr/bin/python3`, not the mise-shimmed `python3`) and matched it to physical hardware: GDK index 1 = laptop built-in screen (`eDP-2`, model `NE160QDM-NZL`); GDK index 0 = external monitor (`DP-1`). `gsettings get guake.general display-n` returned `1` — which, per the established mapping, should have been correct — yet Guake was landing on the external monitor anyway. This contradicts the theoretical mapping and most likely reflects a GDK index reassignment (from a monitor hotplug or session restart) since `display-n` was last set, not a wrong understanding of the mapping itself.

**Fix applied:** `gsettings set guake.general display-n 0`, then restarted the Guake process (`guake --quit`, falling back to `pkill -x guake`, then relaunched detached). Existing shells inside open Guake tabs are unaffected by an app restart (Guake init only re-reads monitor assignment at startup; running shell processes live independently). User confirmed post-restart that Guake now lands on the correct (built-in/laptop) screen.

**Status: Resolved for this session.** General lesson: GDK monitor index → physical screen mapping for Guake is **not stable** across sessions/hotplugs on this machine — a previously-recorded `display-n` value can silently go stale after any monitor topology change. Always re-verify the GDK index-to-physical-screen mapping empirically (per skill-hygiene.md's documented method) before reapplying a remembered `display-n` value; don't assume yesterday's value is still correct.

**Addendum (2026-08-05, later same day):** Recurred a second time within hours — `display-n` went 0 (fix above) → 1 (re-fix after mapping flipped again) → 0 (this correction), all on the same day with no reported hotplug in between. Confirms the GDK index reassignment is more frequent than a one-off hotplug event; likely correlates with session/display state changes generally, not just physical monitor plug/unplug. Same fix procedure applied (`gsettings set` + Guake restart); no new mechanism, just faster recurrence than expected.

**Superseded by §2.32 (2026-08-06):** The "GDK index reassignment" theory was wrong. The real cause is that `window.move()` is a silent no-op under native Wayland — `display-n` was never actually being acted on, at any value, on any day. What looked like index instability was noise from that no-op; recurrence had nothing to do with monitor topology.

---

### §2.32 — Guake wrong-monitor bug, actual root cause: native Wayland `window.move()` is a no-op (2026-08-06, RESOLVED, supersedes §2.31)

**Context:** §2.31 (previous day) misdiagnosed this as GDK-index instability and "fixed" it by flipping `display-n` back and forth, which appeared to work only because Guake was being manually toggled/observed inconsistently. Today's session re-broke and properly root-caused it.

**Symptom:** Guake kept opening on the external monitor (`DP-1`) regardless of `display-n` value (0 or 1), regardless of restart method (`pkill`, `guake --quit`), and regardless of switching to `mouse-display=true` (cursor-follows) mode. Every fix attempt had zero observable effect.

**Investigation:**
1. Confirmed `gsettings get org.guake.general display-n` fails outright — `No such schema "org.guake.general"`. Guake 3.10.1 stores config via **dconf directly** under `/org/guake/general/`, not a registered GSettings schema — use `dconf read`/`dconf write /org/guake/general/<key>`, not `gsettings`. (Corrects the tool used in §2.31 and the original skill-hygiene.md note.)
2. Discovered Guake uses a **D-Bus single-instance model**: running `guake` (or `guake -t`) when an instance is already registered just sends it a toggle-visibility signal rather than starting a fresh process. `pkill -x guake` followed immediately by relaunch could race a GNOME media-key binding (`custom-guake` → `guake -t`) that auto-respawns it, making "restarts" not actually restart the process reading new settings. Confirmed via `pgrep -af`/PID/start-time checks.
3. Read Guake's source (`/usr/lib/python3/dist-packages/guake/utils.py`, `get_final_window_monitor` / `set_final_window_rect`): monitor selection logic (`display-n` lookup, `mouse-display` pointer query, primary-monitor fallback) was correctly resolving a target monitor every time. The bug is downstream: `window.move(x, y)` is called at the end, and **GTK3's Wayland backend silently no-ops `move()`** — Wayland's `xdg-shell` protocol has no client API for absolute window placement (a deliberate Wayland security/isolation design, unlike X11). No error, no log — the call just does nothing.
4. Verified fix: relaunching Guake with `GDK_BACKEND=x11` (forcing it through XWayland) made `window.move()` take effect — confirmed via `wmctrl -l -G` showing the window moving to a different absolute position between attempts, vs. the frozen position under native Wayland.
5. **Second-order gotcha:** GDK's monitor index-to-output mapping is *not* the same under the X11/XWayland backend as under native Wayland. Native-Wayland query: index 0 = `DP-1`, index 1 = `eDP-2` (`primary` flag unset on both — GDK reports no primary monitor at all on this Wayland session, which is also why `mouse-display`'s `get_primary_monitor()` fallback returns `None`). XWayland query (`GDK_BACKEND=x11 python3 ...`): index 0 = `eDP-2` (correctly flagged `primary=True`), index 1 = `DP-1` — **reversed**. Since Guake now runs under XWayland, the XWayland ordering is what matters; a `display-n` value tuned against the native-Wayland query will silently pick the wrong monitor.
6. **Third-order gotcha, noted but not fully resolved:** XWayland's coordinate space did not match `xrandr`'s reported physical geometry — a moved window's `wmctrl -G` position (e.g. x=9216) exceeded the real combined desktop width (~7680px per `xrandr`), consistent with GNOME's fractional/HiDPI scaling giving XWayland a virtual canvas larger than physical pixels (~2x observed). Mutter appears to clamp/map this back onto a real monitor rather than actually placing the window off-screen — final visual placement was correct despite the numeric mismatch — but the exact scale factor was not derived. Anyone debugging XWayland window coordinates on this machine should expect them to disagree with `xrandr` and not assume 1:1.

**Fix applied:**
- `dconf write /org/guake/general/display-n 0` (targets `eDP-2` under the now-relevant XWayland ordering) and `mouse-display false`.
- `~/.config/autostart/guake.desktop`: `Exec=guake` → `Exec=env GDK_BACKEND=x11 guake`, so the XWayland backend (and therefore working positioning) survives login/logout, not just this session's manually-launched process.

**Status: Superseded same day by §2.33** — the XWayland fallback worked but user flagged it as relying on legacy machinery rather than a proper fix; replaced with a GNOME Shell extension doing compositor-side placement instead. `GDK_BACKEND=x11` override removed from autostart.

---

### §2.33 — Guake wrong-monitor bug, proper Wayland-native fix via GNOME Shell extension (2026-08-06, RESOLVED, supersedes §2.32's XWayland workaround)

**Context:** §2.32 fixed the bug by forcing Guake through XWayland (`GDK_BACKEND=x11`), which works but is a compatibility-layer workaround, not a native fix, and introduced its own coordinate-scaling headache (§2.32 point 6). User asked for a genuinely modern alternative rather than falling back to legacy X11 positioning.

**Why client-side positioning can't be fixed on the client:** Wayland's `xdg-shell` protocol deliberately gives clients no API for absolute self-positioning (a security/sandboxing design choice, unlike X11). No GTK3 flag or Guake config change works around this — it's not a bug in Guake, it's the protocol. GNOME/Mutter also doesn't implement `wlr-layer-shell` (the protocol wlroots compositors like Sway/Hyprland use for native anchored dropdown terminals), so there's no clean cross-compositor answer on GNOME specifically. The one thing Wayland *does* still allow is the **compositor** moving a window on its own initiative — `window.move()` from inside the client is forbidden, but Mutter calling `MetaWindow.move_frame()` on a window it manages is not, because that's the compositor's own prerogative, not a client request.

**Fix:** Wrote a minimal GNOME Shell extension (`guake-reposition@skikk-thor.local`, `~/.local/share/gnome-shell/extensions/guake-reposition@skikk-thor.local/`) that:
1. Connects to `global.window_manager`'s `'map'` signal (fires each time Guake's window is (re)shown — Guake fully unmaps/remaps its surface on hide/show rather than just hiding).
2. Filters for `wm_class === 'Guake'`.
3. Looks up the target monitor by **connector name** (`eDP-2`) via `global.backend.get_monitor_manager().get_monitor_for_connector()`, not by numeric index — sidesteps the index-reordering problem entirely (§2.31/§2.32 point 5: GDK monitor index order is not stable across backends/sessions; connector name is).
4. Calls `win.move_frame(true, x, y)` to center it on that monitor — a genuine Mutter/compositor API call, not a client self-positioning request, so it isn't subject to the Wayland restriction.

**Eval/scripting note:** GNOME 45+ locks `org.gnome.Shell.Eval` behind `global.context.unsafe_mode`, which can only be toggled interactively via Looking Glass (Alt+F2 → `lg`) — not scriptable, not persistable via `gsettings`. This ruled out a quick D-Bus one-liner; a real extension was the only scriptable path with full Meta/Mutter API access.

**Discovery gotcha:** the shell only scans `~/.local/share/gnome-shell/extensions/` for *new* UUIDs at process startup. Neither `gnome-extensions enable` nor manually appending to `org.gnome.shell enabled-extensions` (dconf/gsettings) triggered a live rescan. On X11 this is normally solved with "Restart Shell" (Alt+F2 → `r`); **that restart path does not exist on Wayland** — a full logout/login was required, one time, for the shell to discover the extension. Editing the JS of an *already-registered* extension afterward does not require this — `gnome-extensions disable`/`enable` (or `ReloadExtension` over D-Bus) picks up code changes live.

**Coordinate systems note:** confirmed empirically that `wmctrl`/XWayland-based tools report window position in a coordinate space scaled ~4x relative to Mutter's own logical coordinates on this HiDPI dual-monitor setup — e.g. the extension's own log recorded `moved to 2304,0`, while `wmctrl -l -G` reported `9216,128` for the same window at the same moment (2304×4=9216). Don't use `wmctrl` to sanity-check Mutter-side placement math on this machine; trust the extension's own logged coordinates (`log()` output visible via `journalctl --user -b 0`) or direct visual confirmation instead.

**To switch the target monitor:** edit `TARGET_CONNECTOR` in `extension.js` (`eDP-2` ↔ `DP-1`), then `gnome-extensions disable guake-reposition@skikk-thor.local && gnome-extensions enable guake-reposition@skikk-thor.local` — no logout needed for a code-only change to an already-registered extension. No hotkey exists for this yet (not built — not currently needed).

**Status: Resolved.** User confirmed Guake opens on the laptop screen (`eDP-2`) after logout/login. `~/.config/autostart/guake.desktop` reverted to plain `Exec=guake` (native Wayland, no XWayland override needed anymore). Genuinely Wayland-native, no legacy-protocol fallback. Revert trigger: none currently anticipated — if Guake ever moves to GTK4 with native Wayland positioning support, the extension becomes unnecessary but is harmless to leave in place.

---

### §2.34 — Full journal survey: idle-state hard-freeze pattern, distinct from §2.29's AC-boot-hang (2026-08-06)

**Context:** Following the Aug 6 15:20:26 freeze (already logged under §2.29's timeline as the boot -2 abrupt stop preceding that entry's AC-boot-hang), ran a full journal survey (2026-07-23 – 2026-08-06, retention confirmed back to 2026-07-07) to check for any other unexplained abrupt boot-ends and to characterize the Aug 6 event specifically. This is a separate issue from §2.29 (AC-plugged boot hang, early-userspace, pre-GPU-init) — do not conflate; this entry is about mid-session freezes with no boot-hang signature.

**Survey results — 8 abrupt/unclean boot-ends found (journal stops with no shutdown/reboot/panic/OOM/thermal signature logged):**

| Time | Gap to next boot | Assessment |
|------|-------------------|------------|
| 2026-07-29 21:45:47 | 47s | No error signature. UNEXPLAINED, not previously documented. |
| 2026-07-30 10:06:33 | 75s | Tail shows "snap mount timed out" cascade — likely benign shutdown-teardown artifact, not a freeze. |
| 2026-07-30 22:43:31 | 62s | No error signature. UNEXPLAINED, not previously documented. |
| 2026-07-31 10:23:21 | 108s | Already §2.27 — confirmed hard freeze (user observed screen hang, manual reset). |
| 2026-07-31 12:12:11 | 38s | Already §2.27 — NVRM `osapi.c:1939` assertion firing repeatedly before stop. |
| 2026-08-04/06 10:37–10:43 | rapid failed boots | Already §2.28, RESOLVED — different mechanism (NVRM boot-init assertion loop), not a runtime freeze. |
| 2026-08-06 10:00:23 | 83s | Same benign "snap mount timed out" pattern as 2026-07-30 10:06. |
| 2026-08-06 15:20:26 | **72 minutes** | Today's incident — the only event with a real multi-minute gap consistent with sitting powered-off until manually discovered/power-cycled. |

**Aug 6 15:20:26 event — confirmed idle/AFK at time of freeze.** User has confirmed the laptop was idle and unattended: left running, found dead on return. This is a distinguishing detail — it points to an idle-state transition (autosuspend, GPU runtime PM/D3cold attempt, screen blank/DPMS) as the trigger, not a load-triggered crash. This idle-freeze signature is a closer match to this machine's known PM-freeze history (NVPCF D3cold storm, §2.16; `pm_runtime_work` Blackwell freeze under fine-grained PM, §2.17) than a random crash would be — those were also idle/PM-transition-triggered, not load-triggered.

**Assessment — root cause NOT confirmed, working hypothesis only:**
- The short-gap events (2026-07-29 21:45, 2026-07-30 22:43) remain unexplained: too fast (<2min) to be "sat dead until discovered," more consistent with a fast auto-reboot or transient kernel-level event. Not enough evidence yet to link them to the idle-PM-freeze hypothesis below.
- §2.27's 2026-07-31 12:12 event (NVRM `osapi.c:1939` assertion firing before stop) is the closest prior analog — at least a partial signature — but not proven identical: today's event left **no error signature at all**, not even an NVRM assertion, before the journal stopped. Either whatever hung, hung hard enough that even the NVRM assertion path (if that's the mechanism) never got a chance to log, or this is a different mechanism entirely.
- Working hypothesis: idle-state PM freeze, possibly GPU runtime PM/D3cold related, family-matches prior known PM bugs on this machine — not a diagnosis.

**Recommended next steps (not yet actioned):**
- If willing to test: monitor `powertop` or `cat /sys/bus/pci/devices/*/power/runtime_status` for the GPU during an idle stretch.
- Run `journalctl -f` live during an idle/AFK period to check whether *any* log line appears at the moment of freeze — today's event logged literally nothing, worth confirming that's consistent rather than a one-off.
- If a reliable repro pattern emerges (e.g. "freezes after ~N hours idle"), poll `nvidia-smi`/GPU state just before the expected window.

**Update 2026-08-06 (later same day) — second freeze today, not idle-triggered; podman ruled out as trigger.**

A second freeze occurred at **17:04:26 IST**, this time during active use, not idle — the machine was in active session, contradicting the "idle-state hard-freeze" framing this entry opened with. An AC-boot-hang immediately followed: failed AC-plugged retry at 17:05:13, successful AC-unplugged retry at 17:05:54. This is the same tight freeze→AC-boot-hang coupling seen with the first Aug 6 occurrence (15:20:26 freeze → 16:32:45 failed/16:33:29 successful AC-boot-hang, logged under §2.29). See cross-reference note added to §2.29 below.

**Podman/container activity investigated as a possible trigger — RULED OUT.** The `poc_planning_tool` compose stack runs a DB healthcheck (`kompreno-db`) roughly every 5s continuously whenever the stack is up, which produces dense, regularly-spaced journal lines. Checked all 6 freeze events identified across this investigation (Jul 29 21:45, Jul 30 22:43, Jul 31 10:23, Jul 31 12:12, Aug 6 15:20, Aug 6 17:04) against podman stack state at time of freeze: **two of the six (Jul 30 22:43 and Jul 31 10:23) occurred with the podman stack not running at all**, and the machine still froze. This rules out podman/container workload as the cause outright — a freeze that happens with the workload absent cannot be caused by that workload. The apparent correlation visible in the other four events is a logging-density artifact: at a 5s healthcheck cadence, podman lines appear near *any* freeze timestamp by construction (there's always one within a few seconds of any given moment the stack is up), not because the healthchecks triggered anything.

**NVRM assertion remains the only recurring anomaly, still not conclusively causal.** The `NVRM: nvAssertFailedNoLog` assertion recurs near freeze events (`osapi.c:1939` in one, `osapi.c:2075` in another — see §2.29's 2026-08-04 note), but it also fires harmlessly during normal healthy operation elsewhere in the journal survey, so its presence near a freeze doesn't distinguish causal from coincidental. Flagging as the closest lead, not a diagnosis.

**Freeze count now 6 in the Jul 23–Aug 6 window (~2 weeks).** This elevates the pattern from "occasional, monitor" to "recurring enough to warrant escalation." With no software-workload trigger identified (podman ruled out this update; NVRM assertion unconfirmed as causal), a BIOS/EC firmware update should be prioritized as the next step — see §2.29's root-cause research notes on EC/PM fault class matching and recommended escalation path, which now applies to this entry's freeze pattern as well given the strengthened AC-boot-hang coupling below.

**Working hypothesis strengthened, still not proven: freezes and §2.29's AC-boot-hang may be the same underlying EC/PM fault manifesting two ways.** The AC-boot-hang has now co-occurred with a freeze twice — Aug 6 15:20 freeze → 16:32 hang, and Aug 6 17:04 freeze → 17:05 hang — both within roughly an hour of the freeze and both resolved by the same AC-unplug workaround. Two-for-two co-occurrence is suggestive but n=2 does not establish causation any more than §2.29's own AC-plugged/unplugged correlation does at the same sample size. Treat as the working hypothesis pending a shared root cause (or disconfirming evidence on a future occurrence where one happens without the other).

**Status: MONITORING → ESCALATE.** No longer purely idle-triggered (17:04 occurrence was during active use) — the "idle-state hard-freeze" framing in this entry's title/opening no longer holds as the full explanation; idle-PM remains one plausible trigger among freezes with no confirmed common cause. Podman/container workload is ruled out as a cause. 6 occurrences in ~2 weeks with two now tightly coupled to §2.29's AC-boot-hang is enough to prioritize a BIOS/EC firmware check over further passive log monitoring. Not merged with §2.29 as a single entry — root cause still unconfirmed, and the freeze/hang relationship, while increasingly suggestive, isn't proven identical.

---

### §2.35 — AC-adapter flapping (ACPI `ac_adapter`) caught live, likely shared root cause for §2.29 + §2.34 + the "double chime" (2026-08-06)

**Context:** During a chime-reporting cluster this session (user heard a repeated "double chime" resembling a USB-connect sound, unsure of actual source), started a live background watcher — `journalctl -kf` + `sudo acpi_listen`, both piped with timestamps into `.scratch/chime_watch.log` — covering ~17:39:44 to 18:06 IST (~22 minutes actively logged, with a denser capture window ~17:50–18:06 during active chime reports).

**Finding — ACPI `ac_adapter` event (device `ACPI0003:00`) is flapping in tight bursts, not polling evenly:**

| Time | Event | Gap from prior |
|------|-------|-----------------|
| 17:50:02.253 | `ac_adapter` → `00000000` (offline) | — |
| 17:50:06.264 | `ac_adapter` → `00000001` (online) | 4s |
| 18:01:22.226 | `ac_adapter` → `00000001` (online) | (gap, ~11 min quiet) |
| 18:01:30.251 | `ac_adapter` → `00000000` (offline) | 8s |
| 18:01:34.272 | `ac_adapter` → `00000001` (online) | 4s |

Only 11 `ac_adapter` events total across the ~22-minute window — not constant/evenly-spaced polling, but tight bursts (multiple flaps within seconds) separated by long quiet gaps. This shape is consistent with an intermittent physical fault (loose charging connector, flaky USB-C PD contact, failing charging IC), not a software polling artifact.

Each flap was accompanied within ~0.1–0.4s by a `battery` re-poll ACPI event and a `wmi` (device `PNP0C14:00`) ACPI event, and the flap clusters coincided closely with bursts of the known `NVRM: nvAssertFailedNoLog: Assertion failed: 0 @ osapi.c:2075` assertion (dozens of hits within ~150ms windows, same assertion family already tracked as benign/unconfirmed-causal under §2.20/§2.29/§2.34) firing right alongside.

**Assessed as the single most likely unifying root cause for three previously-separate-looking symptoms:**
- **The "double chime"** — plausibly the OS's power-source-changed audio/notification cue firing on every online/offline flap. Explains why it sounded USB-like but the user wasn't sure.
- **§2.29 (AC-plugged boot hang)** — plausibly the same flaky AC-sense/charging-IC signal disrupting early boot specifically when AC is connected; unplugging AC removes the disruptive signal, which matches the confirmed 2/2 (now 3/3 as of today) AC-unplug-fixes-it pattern.
- **§2.34 (recurring hard freezes)** — plausibly the same AC power-source flapping wedging a PM/EC subsystem at runtime, consistent with §2.34's own working hypothesis of an idle/PM-transition-class fault and its NVRM-assertion correlation.

If confirmed, this reframes §2.29 and §2.34 from two-or-three separate "unconfirmed PM/EC fault" entries into one shared hardware fault with three manifestations (boot hang, runtime freeze, audible chime), rather than independent bugs needing independent software fixes.

**Honesty check — this is NOT yet a confirmed root cause:**
- Single ~25-minute observation window (n=1 watch session). No controlled wiggle-test performed yet.
- Does not explain the July freeze occurrences (Jul 29, Jul 30 x2, Jul 31 x2) that predate this watcher's existence — no way to retroactively check ACPI flapping for those; the only artifact available for them (journal/kernel logs) shows no signature either way for this specific mechanism, so they're neither confirmed nor ruled out against this hypothesis.
- Correlation between ac_adapter flaps and NVRM assertion bursts is temporal, not yet causally demonstrated.

**Recommended next steps:**
1. **Wiggle test (immediate, cheap):** physically wiggle the charger cable at the connector while plugged in and watch for the chime / re-run the ACPI watcher — reproducing the flap on demand vs. not distinguishes a loose connector/cable from an internal IC/firmware fault. Not yet performed by the user as of this entry.
2. **If reproducible via wiggle:** points to connector/cable — try a different cable/charger first (cheapest elimination step) before assuming the port itself is at fault.
3. **If not reproducible via wiggle (intermittent regardless of physical manipulation):** points to the charging IC or EC-level AC-sense circuitry — this is a hardware repair/RMA matter, not something a kernel parameter or driver update can fix. Given this is a fairly new SKIKK Thor 16, check warranty status and pursue RMA/hardware inspection rather than continuing to chase a software-side fix for §2.29/§2.34.
4. Keep the background watcher pattern (`journalctl -kf` + `acpi_listen`, timestamped) available for capturing the next chime/freeze/hang occurrence with more data — 25 minutes was enough to catch the pattern but a longer/repeated capture would strengthen (or break) the correlation.

**Status: HYPOTHESIS, ELEVATED PRIORITY.** Recommend treating as the leading root-cause theory for §2.29 and §2.34 pending the wiggle-test result, and flagging in `doc/machines/skikk-thor.md` prominently given it points to a hardware fault rather than a software one.

---

### §2.36 — Guake top edge hidden under GNOME top bar — reposition extension used raw monitor geometry instead of work area (2026-08-06)

**Symptom:** Guake's top edge was rendered underneath the GNOME top bar (~1-2 lines of terminal content obscured), distinct from the §2.31–2.33 wrong-monitor bug — this time the monitor was correct, only the vertical position was wrong.

**Root cause:** The `guake-reposition@skikk-thor.local` extension (from §2.33) places Guake with `win.move_frame(true, x, geom.y)`, where `geom` comes from `global.display.get_monitor_geometry(monitorIndex)`. Monitor geometry is the *full physical* monitor rectangle, including the strip the GNOME top bar occupies — the panel is an overlay, not a geometry-reducing region. Placing the window at `geom.y` (0) puts its top-left corner at the physical top of the screen, directly behind the bar.

**Fix applied:** Changed the Y calculation to use the workspace's work area instead of raw monitor geometry: `global.display.get_workspace_manager().get_active_workspace().get_work_area_for_monitor(monitorIndex).y`, which Mutter already computes as monitor geometry minus panel/dock reservations. X centering is unchanged (still computed off full monitor geometry, since only the top bar reduces work area on this machine). Edited `~/.local/share/gnome-shell/extensions/guake-reposition@skikk-thor.local/extension.js`.

**Reload caveat confirmed (matches §2.30's Edge-icon precedent):** `gnome-extensions disable`/`enable` and the `org.gnome.Shell.Extensions` D-Bus interface's `ReloadExtension` (present in introspection but returns `UnknownMethod` on this shell version) do **not** force a genuine reload of the extension's ES module under GNOME Shell on Wayland — `journalctl` showed the *old* `y=0` placement logged even after disable/enable and a fresh Guake relaunch. GNOME Shell caches the ESM import; only a full logout/login (Wayland has no `Alt+F2 r` soft-restart) actually reloads extension code. **Status: Resolved.** User confirmed post-logout/login that Guake's top edge no longer sits under the GNOME top bar.

---

### §2.37 — Kernel panic captured by kdump: stack overflow / double fault in `smp_text_poke_int3_handler`, distinct signature from the AC-adapter cluster (2026-08-08)

**Context:** Boot `51c2e05e...` started Aug 06 22:54:31 IST, journal normal throughout (podman healthcheck logging at 10s cadence), then ends abruptly Aug 08 18:29:24 IST with no shutdown/panic message in the journal itself. 23 seconds later a kdump crash-kernel boot (`24e1f71b...`, 31s) ran and captured `/proc/vmcore` — the first time this freeze cluster has left a crash artifact; prior freezes (e.g. §2.34) left no trace at all.

**Pre-crash anomaly, ~3.4h before the panic:** at kernel uptime ~144385s–144877s (5 occurrences at ~123s intervals, roughly Aug 08 15:03–15:11 IST), task `T216` logged an identical hung/stuck trace each time — `RIP: 0033:0x7fa02d134c8d`, same userspace IP every occurrence, consistent with a process spinning or stuck for several minutes. Coincides with the user's report of heavy fan spin-up during this window.

**The panic itself, kernel uptime ~156908.89s (matches the 18:29:24 journal cutoff), cascading within <0.1s wall-clock:**
`BUG: IRQ stack guard page was hit` → repeated `BUG: #DF stack guard page was hit` (double fault) → `BUG: TASK stack guard page was hit` → `Oops: stack guard page: 0000 [#1] SMP NOPTI` → `RIP: 0010:error_entry+0x17/0x140` → self-recursive double-fault cascade inside `smp_text_poke_int3_handler+0x1c/0x2a0` / `__entry_text_end` (kernel's int3-breakpoint / live-patching machinery used by ftrace/kprobes/static-key patching) → `WARNING: stack recursion on stack type 5`. This is a stack-overflow-triggered double-fault death spiral.

**Ruled out:** no thermal/throttle/MCE/Machine-Check lines anywhere in the dump. No `ac_adapter`/`ACPI0003` activity near the crash — this does **not** match the §2.29/§2.34/§2.35 AC-adapter-flapping pattern. Two unrelated correctable NVIDIA PCIe "BadTLP" bus errors ~17h earlier (Aug 08 ~01:01/01:04) are noise, not causal.

**Taint/modules at crash time:** `(OE)` — out-of-tree modules loaded: `nvidia`, `nvidia_drm`, `nvidia_modeset`, `nvidia_uvm`, `ite_8291`/`ite_8291_lb` (TUXEDO per-key RGB keyboard driver), `tuxedo_compatibility_check`. `amdgpu` also loaded (hybrid graphics).

**Assessment: this is a DISTINCT, NEW failure signature, not the AC-adapter fault.** A genuine kernel stack-overflow → double-fault panic in the int3/text-patching path, likely triggered while a process was already stuck/spinning under heavy CPU load (matches the reported fan spin-up). Root cause of the underlying stack overflow is **not yet identified** — candidates for future investigation: the out-of-tree `ite_8291`/`tuxedo_compatibility_check`/`nvidia` modules (common source of this class of bug), or a kernel/ftrace bug in `smp_text_poke_int3_handler`. This confirms not every freeze in the cluster necessarily shares one root cause.

**Artifacts preserved:** `/var/crash/202608081829/` (`dmesg.202608081829`, `dump-incomplete`, root-only) for further analysis if it recurs.

**UPDATE (2026-08-08, same-day follow-up): AMD-Vi IOMMU fault + ucsi_acpi PPM failure at the exact panic second — link to the AC-adapter/USB-C investigation reopened.** A `just health-save` journal snapshot shows, at 18:29:55–18:29:56 IST (i.e. inside the same one-second window as the 18:29:24–18:29:55 crash/kdump sequence above), this exact burst:
```
Aug 08 18:29:55 skikk-thor kernel: nvidia 0000:01:00.0: AMD-Vi: Event logged [IO_PAGE_FAULT domain=0x002b address=0xfff01020 flags=0x0000]
```
(repeated 10x identically), immediately followed by:
```
Aug 08 18:29:55 skikk-thor kernel: ucsi_acpi USBC000:00: con2: failed to get status
Aug 08 18:29:56 skikk-thor kernel: ucsi_acpi USBC000:00: error -ETIMEDOUT: PPM init failed
```
`ucsi_acpi` is the USB-C PD/UCSI ACPI driver — the same subsystem area as the §2.29/§2.34 suspected AC-adapter/USB-C power-sense fault. This directly weakens the "Ruled out... does not match the AC-adapter-flapping pattern" claim above: the original ruling-out only checked for `ac_adapter`/`ACPI0003` strings, which this burst doesn't use, so it was not actually excluded by that check.

**Checked against the crash dump's own captured dmesg** (`.scratch/crash_dmesg_extract.txt`, raw tail of the last 150 lines of `/var/crash/202608081829/dmesg.202608081829`, plus the ACPI/AC-adapter and GPU sections of the same extract): **no AMD-Vi / IO_PAGE_FAULT / ucsi_acpi event lines appear anywhere in the crash dump's own dmesg.** `ucsi_acpi` appears only once, in the static "Modules linked in:" list (expected — it's always loaded, not evidence of an event firing). So this AMD-Vi/ucsi_acpi burst is known only from the systemd journal (which persisted past the crash and into the next boot), not from the panicking kernel's own captured log — the kdump capture window (`smp_text_poke_int3_handler` cascade, uptime ~156908.89s) evidently ended, or the journal simply didn't flush this burst into vmcore's dmesg ring before the dump was taken.

**Two competing interpretations, neither confirmed:**
1. **IOMMU/USB-C fault as trigger:** the AC-adapter/USB-C PD controller fault (already suspected in §2.29/§2.34) glitches, and something in that glitch path (GPU DMA remapping under `nvidia`, or a shared IOMMU/ACPI interrupt) cascades into corrupting kernel stack state, triggering the double fault. This would mean §2.29/§2.34/§2.35 and §2.37 are **not distinct root causes** as concluded above, but the same underlying hardware fault manifesting two ways.
2. **IOMMU fault as downstream symptom:** the GPU driver (`nvidia`), already mid-crash from the stack-overflow/double-fault cascade, issues a bad/stale DMA transaction that AMD-Vi flags as an IO_PAGE_FAULT — a normal side effect of a dying driver, not a cause. The ucsi_acpi PPM failure could similarly be an artifact of interrupts/DMA going haywire system-wide during the crash, not evidence of a real PD-controller fault at that moment.

Cannot currently distinguish these — both are plausible given available evidence. **Status downgraded from "NEW SIGNATURE, confirmed distinct" to NEW SIGNATURE, ROOT CAUSE UNCONFIRMED, POSSIBLE LINK TO AC-ADAPTER/USB-C FAULT NOT RULED OUT.** Next step if this recurs: capture `ucsi_acpi`/AMD-Vi state and `/sys/class/power_supply/ACAD/online` flapping at the moment of any future freeze/panic, not just `ac_adapter`/`ACPI0003` string matches.

**Status: NEW SIGNATURE, ROOT CAUSE OF STACK OVERFLOW UNCONFIRMED — POSSIBLE OVERLAP WITH §2.29/§2.34 AC-ADAPTER FAULT, NOT RULED OUT.**

---

### §2.38 — Kernel upgrade 6.17.0-23-generic → 7.0.0-29-generic, motivated by §2.37 (2026-08-08)

**Context:** The kernel was found `apt-mark hold`-pinned at 6.17.0-23-generic with no documented reason for the hold anywhere in this history or in `doc/machines/skikk-thor.md`. Given §2.37's OE-tainted-driver-vs-kernel-bug ambiguity, upgrading off the held kernel was the cheapest available diagnostic lever.

**Action:** `apt-mark unhold` on the kernel packages → `apt install linux-generic` → DKMS rebuild for all out-of-tree modules → reboot.

**Post-reboot verification, all passed:**
- Running 7.0.0-29-generic
- NVIDIA driver 595.84 loaded, RTX 5070 Ti detected, GPU active, idle P8/49°C
- DKMS: `nvidia`, `tuxedo-drivers`, `tuxedo-yt6801`, `r8125`, `acpi-call` all built/installed cleanly against 7.0.0-29-generic
- GPU PM: `runtime_status active`, `control auto` — healthy
- Only pre-existing cosmetic boot errors present (usbhid interrupt endpoint, gnome-keyring) — nothing new introduced by the upgrade
- Old kernel 6.17.0-23-generic retained as a GRUB fallback entry

**Status: MONITORING, NOT CLOSED.** This upgrade does not by itself confirm or rule out §2.37's root cause — it was undertaken because §2.37's kernel taint (OE) made both an unidentified 6.17-specific kernel bug and the out-of-tree `nvidia`/`tuxedo-drivers` modules plausible candidates. **If the same stack-overflow/double-fault signature (`smp_text_poke_int3_handler` / stack guard page hits) recurs on 7.0.0-29-generic, that rules out a 6.17-specific kernel bug and points root cause squarely at the OE-tainted out-of-tree drivers** (same modules loaded on both kernels). Absence of recurrence over a reasonable monitoring window would be weak evidence for a 6.17-specific bug but not proof, given §2.37 was a single occurrence. No action needed unless it recurs.

---

### §2.39 — NVRM assert-burst frequency is not a valid proxy for AC-adapter-fault activity — corrects §2.35's evidentiary basis (2026-08-10)

**Context:** Current boot (started 13:10:07, still up, no crash) — ran `sudo dmesg -T` via `.scratch/health_sudo.sh` and searched the current-boot kernel ring buffer for both the NVRM assertion and the AC-adapter/battery/EC event family.

**Finding:** `NVRM: nvAssertFailedNoLog: Assertion failed: 0 @ osapi.c:2075` fires continuously — roughly every 15–40s, non-stop — across the entire observed window, 19:03:13 through at least 21:01:42 (nearly 2 hours straight, still ongoing at capture time). Over that same ~2-hour window, a grep for `ac_adapter|ACPI0003|battery|wmi|thermal|shutdown|reboot|panic|watchdog|EC ` across the full dmesg output returned **zero** matches — no AC-adapter events, no battery/wmi re-polls, nothing, despite the NVRM asserts firing continuously throughout.

**Conclusion:** NVRM-assert-burst frequency is **not** a reliable marker for the AC-adapter fault being active — it fires constantly during ordinary operation regardless of AC state. This means §2.35's observation that assert bursts coincided with the `ac_adapter` flap timing on 2026-08-06 was very likely coincidental co-occurrence (the asserts are *always* present in the background) rather than a causal or even a meaningfully correlated signal. **This does not disprove the AC-adapter fault itself** — the `ac_adapter` device flap events §2.35 recorded directly (the ACPI0003:00 online/offline transitions, the accompanying battery/wmi re-polls) are unaffected by this finding and remain real and unexplained. It only removes the NVRM-assert timing as corroborating evidence for "the fault is currently active" in any future log review.

**Root cause of the AC-adapter fault: still OPEN, unconfirmed.** The wiggle test (§2.35 recommendation 1 — physically flex the charger cable at the connector while watching `ac_adapter`/`acpi_listen` directly) remains the actual next diagnostic step and is still unperformed. This entry narrows the evidence chain, it does not close or advance resolution of the underlying issue.

---

### §2.40 — Another §2.34-pattern freeze, manually recovered via forced power-button reboot (2026-08-15)

**Context:** User reported screen freeze + hard fan spin-up around 2026-08-15 11:27-11:36 IST, investigated live within minutes via journal/dmesg/sensors.

**Finding: standard §2.34-pattern freeze — no error signature, journal just stops.** Journal goes silent 11:27:53 → 11:35:57 (~8 min gap), matching prior occurrences exactly. The 11:35:57 entries are a fresh boot sequence, confirmed by `who -b`/`/proc/uptime` (boot at 11:35:55) — **user confirmed this was a manual forced reboot (held the power button)**, i.e. their own recovery action, not a spontaneous hard reset. The AMD firmware line `x86/amd: Previous system reset reason [0x00200800]: ACPI power state transition occurred` is therefore the expected signature of a held-power-button forced reboot, not new evidence about the underlying fault's behavior — **retracts this entry's earlier "severity escalation" framing**, which incorrectly assumed the reboot was spontaneous. No thermal shutdown, OOM, kernel panic/Oops, coredumps, or GPU Xid/reset errors — only the known-benign `NVRM: nvAssertFailedNoLog` cosmetic assertion at boot. No live ACPI watcher was running, so the `ac_adapter` flap mechanism could not be directly checked for this event. Post-recovery thermal state was normal (CPU 64°C, GPU idle 55°C, NVMe 36-41°C, load ~0); one DIMM sensor briefly flagged ALARM at 53.2°C against its 55°C threshold (crit=85°C) — not concerning, matches the known DIMM-temp quirk.

**Assessment:** this is simply another §2.34 occurrence (7th logged), adding no new evidence either way. Status remains MONITORING, root cause still open — the §2.35 wiggle-test remains the actual next diagnostic step. Raw evidence: `.scratch/freeze-investigation-2026-08-15.md`, `.scratch/freeze-raw-2026-08-15.txt`.

---

### §2.41 — gnome-shell crash (SIGABRT), PowerToggle disposed-object bug; user reports adapter-specific correlation, unconfirmed (2026-08-17)

**Context:** gnome-shell crashed (SIGABRT, coredump PID 51722) at 11:19:09 IST. GDM auto-restarted a new shell session within the same second window — no reboot, user session survived.

**Crash signature:** preceded at 11:18:16 by repeated GJS errors — `Object Gjs_status_system_PowerToggle ... has been already disposed` — with stack traces in `resource:///org/gnome/shell/ui/status/system.js:72/73/102`. This is the quick-settings power/battery toggle being accessed after being destroyed mid-teardown — a known upstream gnome-shell crash class, typically triggered by a power-source-change event racing UI teardown (fits the "power toggle" object specifically, not a generic shell bug).

**Co-occurrence, same second (11:18:16):** NVIDIA driver logged a burst of `NVRM: nvAssertFailedNoLog: Assertion failed: 0 @ osapi.c:2075`. Per §2.39, this assertion fires continuously in the background regardless of AC state and is **not** a reliable corroborating signal — timing correlation only, not causal evidence.

**Ruled out:** thermal fault — CPU ~86°C boost, GPU 56°C, no throttling; GPU PM runtime states normal (0x01 fix per §2.17/§2.20 holding). **Not captured:** no literal `ac_adapter`/`ACPI0003` event line in the journal at default verbosity around the crash — consistent with either a power-source-change event that didn't get logged at that verbosity, or no power-source-change at all.

**NEW: user-reported adapter-specific correlation (2026-08-17, unconfirmed).** User reports this crash pattern happens noticeably more often with one of their two AC adapters than the other. **Adapter identity, wattage, and cable type not yet specified — do not guess or assume which adapter, this needs to be confirmed with the user as a follow-up.** If real, this is a meaningfully different shape of evidence than everything in §2.29/§2.34/§2.35/§2.39: a laptop-side charging-circuit or AC-power-sense fault (loose connector, failing charging IC) should misbehave with *any* adapter roughly equally, since the fault lives on the laptop side of the connection. An adapter-specific skew instead points at the adapter/cable side specifically — a marginal USB-C PD negotiation on that one brick, a worn plug, or a degraded cable — which is a different (and more actionable) repair target than the "laptop hardware fault" hypothesis carried since §2.29.

**Assessment:** this crash's own signature (GJS PowerToggle disposed-object bug) is a known upstream gnome-shell bug class triggered by power-source-change races — it does not by itself prove an AC-adapter hardware fault, but it is consistent with one triggering the race. Combined with the new adapter-specific correlation, this narrows (not confirms) the existing flaky-AC-adapter hypothesis toward the adapter/cable, away from the laptop's own charging circuitry. **Status: OPEN.** Next steps: (1) get adapter identity/wattage/cable-type/serial from the user for both adapters, to distinguish which is "the bad one"; (2) once identified, track future gnome-shell crashes and §2.34-pattern freezes against which adapter was in use at the time; (3) the §2.35 wiggle-test (unperformed) remains relevant and should now be run specifically on the suspected adapter's cable/connector, not just the laptop-side port. Raw evidence: `.scratch/crash_diag_part1.txt`, `.scratch/crash_diag_journalerr.txt`, `.scratch/crash_diag_recent.txt`, `.scratch/crash_diag_dmesg.txt` (dmesg capture failed without sudo; journalctl/coredumpctl/sensors used instead).

---

### §2.42 — TCC charging profile set to `stationary` at config level; hardware enforcement unconfirmed, possible overlap with §2.26 driver bug (2026-08-17)

**Context:** user wants a battery-longevity charge cap (analogous to Windows OEM ~85% caps) since the laptop stays plugged in most of the time. Standard kernel sysfs `charge_control_end_threshold` does not exist on this hardware.

**Investigation:** TUXEDO Control Center v3.0.9 has a "Charging Profile" feature (`chargingProfile` key in `/etc/tcc/settings`, values `balanced`/`high_capacity`/`stationary`) but it does not appear anywhere in the installed TCC GUI (confirmed by user screenshot — no charging section under Dashboard, Profiles, Tools, or Global profile settings; only Temperature Display, CPU Frequency Control, Fan Control, Keyboard Backlight Control). Extracted `app.asar` source confirms the feature exists in code (`charging-settings.component.ts`) but isn't rendering in this install.

**Action:** wrote and had the user run `.scratch/set_tcc_stationary_profile.sh` — stop `tccd` → back up existing settings → copy in a corrected settings file with only `chargingProfile` changed (`high_capacity` → `stationary`) → restart `tccd` → verify. Ran clean: `chargingProfile` confirmed `"stationary"` in `/etc/tcc/settings`, `tccd` active. Backup at `.scratch/tcc_settings_backup_20260817.json`.

**Unresolved — hardware enforcement not confirmed.** On restart, `tccd`'s journal logged `FanControlWorker: onStart: Fan API not available` — the exact same failure signature as the already-open §2.26 bug (`tuxedo_keyboard`/`tuxedo_io` fail to load on this CPU family/chassis combo, driver v4.22.3, no fix released, upstream `tuxedo-drivers#376`). Immediately after, the journal showed `ODMProfileWorker: Using tuxedo-io` — meaning charging-profile control very likely routes through the same broken `tuxedo-io` interface as fan control. So: the config-file/daemon-level change succeeded and is accepted by `tccd`, but there is no confirmation it reaches the EC/hardware to actually cap charging — plausibly a second silent symptom of the same driver-compatibility gap that already breaks fan control. No sysfs feedback exists to verify charge-cap enforcement directly.

**Status: OPEN, config applied, hardware effect unverified.** Only real test available is behavioral: watch battery capacity while plugged in over the coming days/weeks — does it plateau below 100% (cap working) or keep climbing to 100% (cap not reaching hardware, same as the fan-control gap). If it recurs/confirms as ineffective, this strengthens the case that `tuxedo-io` is broken across the board on this chassis, not just for fan control.

---

### §2.43 — tuxedo-drivers#376 closed WON'T-FIX, not fixed — permanent exclusion for this non-TUXEDO-branded chassis (2026-08-17)

**Context:** §2.26 documented the open upstream issue tracking `tuxedo_keyboard`/`tuxedo_io` failing to load on this Tongfang GM6HG7Y (SKIKK) chassis due to `tuxedo_compatibility_check.c` rejecting CPU family 26 (Zen5) / non-TUXEDO DMI vendor string. User directly viewed the GitLab issue and confirmed its current status.

**Finding: GitLab issue `tuxedo-drivers#376` was closed 2026-07-29 as WON'T-FIX, not fixed.** Maintainer Werner Sembach (`@tuxedo_wse`) commented: "we can't test non tuxedo devices so they are not supported by tuxedo-drivers". This is a policy exclusion, not a pending compatibility patch — TUXEDO has no intent to support non-TUXEDO-branded Tongfang/Uniwill chassis on this driver, ever.

**Practical implication:** fan control via `tuxedo-io`/`tuxedo_keyboard` will **never** be fixed via tuxedo-drivers on this hardware — reclassify from "unresolved bug, awaiting fix" to "permanent, by-design exclusion." §2.42's charging-profile hardware-enforcement gap (same `tuxedo-io` failure signature) is almost certainly the same permanent exclusion, not a separate bug that might get fixed alongside it.

**Path forward:** the maintainer pointed to a community alternative driver project, [uniwill-laptop](https://github.com/Wer-Wolf/uniwill-laptop), as the intended route for non-TUXEDO-branded Uniwill/Tongfang hardware. Viability of this driver for this chassis is **under separate evaluation this session — not yet confirmed**; do not treat it as a working fix until that evaluation lands.

**Status: §2.26 driver gap reclassified CLOSED/WON'T-FIX UPSTREAM — permanent on tuxedo-drivers. Community `uniwill-laptop` driver is the only forward path, viability unconfirmed.**

---

_End of draft._
