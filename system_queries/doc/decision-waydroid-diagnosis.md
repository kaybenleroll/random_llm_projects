# Handover — 2026-06-14 — System health audit + Waydroid investigation

Branch: main | Latest commit: 772b0dc

## What was done this session

- /reflect: 8 learnings processed, 3 promoted to skill-hygiene.md
- PySol sluggishness: diagnosed as Chrome/XWayland competition; Marvellous Suspender installed
- OneDrive rclone: token expired, reconnected interactively, service restarted
- Portable monitor: BIOS set to discrete GPU mode; mini-DP→HDMI (video) + USB-C (power) both required
- System health audit: ~18 GB cleaned (Android Studio snap, old snap revisions, ~/.android 8.3 GB, LM Studio models 3.2 GB, Android SDK 11 GB)
- snap retain=2 set — 8 disabled revisions are normal/expected going forward
- rsyslog filter: /etc/rsyslog.d/10-drop-acpi-ec.conf drops ACPI EC spam (was 785 MB/day, now ~1 MB/day)
- ASPM grub fix applied (pcie_aspm.policy=default, was powersave) — GRUB UPDATED, REBOOT STILL NEEDED
- Waydroid: investigated and parked (see below)
- 18 skill learnings queued for /reflect

## CRITICAL PENDING: REBOOT REQUIRED

`/etc/default/grub` has been updated with `pcie_aspm.policy=default` and `update-grub` ran successfully. Ethernet (enp5s0) is currently DOWN and has been dropping overnight due to r8125 stranding in L1 ASPM. The fix only activates after reboot.

After reboot: `ip link show enp5s0` should show `state UP`.

## Waydroid status (parked)

**Root cause:** `hwcomposer.waydroid.so` crashes with SIGSEGV ~1s after start. The vendor image (MAINLINE) targets AMD iGPU renderD129 for GBM buffer allocation. In discrete GPU BIOS mode, the AMD iGPU's render node is present but half-powered — GBM initialisation fails. The Wayland compositor (GNOME) runs on NVIDIA, creating a cross-device dma-buf sharing problem even when the AMD node was available. This regression appeared around Dec 2025–Jan 2026, coinciding with nvidia-open 580.95.05 → 580.126.09.

**Current waydroid state:**
- Session: STOPPED (clean)
- waydroid.cfg: `waydroid.background_start=false` (won't spam Guake), `ro.hardware.egl=mesa`
- waydroid.prop: regenerated on each session start — edits to waydroid.prop are overwritten
- No fix found without switching BIOS to hybrid mode (user won't do this — external monitor requires discrete)

**When to retry:** nvidia-open 610+ with improved Blackwell GBM support. Cloud routine `trig_01JUnBV6BGNv5pJsbQeGNSvw` checks on 2026-07-07.

**Kindle workaround:** User has Calibre library with most EPUBs. Foliate (native Linux EPUB reader) is the recommended reader. Not yet installed.

## Disk state (after cleanup)

- Root: 76%, 222 GB free (was 78%)
- /data: 25%, 701 GB free
- Logs: syslog ~1 MB/day (rsyslog filter working)
- Snap: 15 GB steady state with retain=2

## Key config files changed

- /etc/default/grub — pcie_aspm.policy=default (needs reboot)
- /etc/rsyslog.d/10-drop-acpi-ec.conf — ACPI EC log filter
- /var/lib/waydroid/waydroid.cfg — background_start=false, egl=mesa
- /etc/modprobe.d/nvidia-power.conf — NVreg_DynamicPowerManagement=0x01 (pre-existing, leave alone)
