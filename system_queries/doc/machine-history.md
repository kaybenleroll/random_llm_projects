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

**Fix:** set all three GNOME actions to `'nothing'` (live, no reboot); staged a `HandleSuspendKey=ignore`/`HandleHibernateKey=ignore` logind drop-in for defense-in-depth (needs sudo+reboot — see CLAUDE.md Active fixes table for current status).

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

_End of draft._
