# Waydroid Crash Diagnosis — 2026-06-14

## Executive Summary

**Root cause: `vendor.hwcomposer-2-1` crashes with SIGSEGV (signal 11) on every start. SurfaceFlinger detects the hwcomposer death and aborts with SIGABRT (signal 6). Android init restarts both in an infinite loop every ~5 seconds.**

This is a hardware-compositor crash loop, not a networking or binder configuration problem. The iptables/nftables issue and NO-CARRIER on waydroid0 are real but separate — the display stack is what's killing the UI repeatedly.

---

## Crash Chain (confirmed from kernel journal)

```
13:33:32  vendor.hwcomposer-2-1 (pid 109) starts
13:33:48  vendor.hwcomposer-2-1 (pid 109) received signal 11  [SIGSEGV]
13:33:48  SurfaceFlinger (pid 145) sent signal 9 by init  [hwcomposer died → SF aborts]
13:33:48  surfaceflinger (pid 145) received signal 6  [SIGABRT]
13:33:48  vendor.hwcomposer-2-1 restarts (pid 1708)
13:33:48  surfaceflinger restarts (pid 1732)
13:33:50  vendor.hwcomposer-2-1 (pid 1708) received signal 11  [SIGSEGV again]
13:33:50  surfaceflinger (pid 1732) received signal 6
... repeats every ~2-5 seconds for 29 minutes
```

The `vendor.hwcomposer-2-1` binary is the HWC2 composer service for waydroid. It crashes with SIGSEGV on every single invocation — it never stays alive more than ~2-20 seconds.

---

## binder "cannot find target node" storm

PID 29189 is the host-side waydroid session manager (the `waydroid show-full-ui` / session process, PID confirmed from first attempt that stopped at 13:33:29 and was immediately STOPPED). All 34 kernel binder errors pointing to `0:0 failed .../29189/-22` are container processes trying to reach a binder endpoint that died when the container crashed or when that session was stopped prematurely. This is a **symptom** of the hwcomposer crash loop, not its cause.

---

## Why the first attempt failed at 13:33:29 (3 seconds)

- Container started at 13:33:26
- lxc-info showed STOPPED briefly then RUNNING
- waydroid.log: "waiting 10 seconds for container to start..."
- Container stopped at 13:33:29 — only 3 seconds
- Cause: The waydroid session process (pid 29189, the previous session's host process) had a stale binder context. The waydroid python daemon detected the container wasn't responding via binder and bailed. This was a cleanup race from the **previous** boot's session.

---

## EGL/Rendering Configuration (waydroid.prop)

```
ro.hardware.egl=swiftshader       ← software renderer
ro.hardware.gralloc=android       ← generic gralloc (not gbm)
ro.hardware.vulkan=radeon         ← AMD vulkan (renderD128/129 = NVIDIA, not AMD!)
gralloc.gbm.device=/dev/renderD129
```

**Problem: `ro.hardware.vulkan=radeon` is wrong for this machine.** This is a pure NVIDIA system (RTX 5070 Ti). The `radeon` vulkan driver does not exist here. But since `ro.hardware.gralloc=android` + `ro.hardware.egl=swiftshader` means it's using the software path anyway, this specific mismatch may not be the immediate crash trigger — swiftshader doesn't use Vulkan or the GPU.

The HWC2 (`vendor.hwcomposer-2-1`) in the MAINLINE vendor image handles display composition. It is crashing before it can initialize.

---

## lxc.hook.post-stop exit status 126

```
lxc-start: waydroid: ../src/lxc/utils.c: run_buffer: 569 Script exited with status 126
lxc-start: waydroid: ../src/lxc/start.c: lxc_end: 986 Failed to run lxc.hook.post-stop
```

The LXC config has `lxc.hook.post-stop = /dev/null`. Exit status 126 means "found but not executable" — `/dev/null` is not executable as a script. This error appears on **every** clean stop and is harmless (waydroid handles cleanup through its own stop sequence). Not a crash cause.

---

## Network Issues (iptables vs nftables)

On every start:
```
iptables: Bad rule (does a matching rule exist in that chain?).
iptables: No chain/target/match by that name.
```

Ubuntu 26.04 uses nftables as the default backend; `iptables-legacy` is calling nftables translation layer and failing. waydroid-net.sh uses legacy iptables rules. The waydroid0 bridge therefore has no NAT rules → NO-CARRIER and no outbound connectivity from the container. This prevents internet access inside Waydroid but does **not** cause the UI crash loop.

---

## `waydroid.cfg` `background_start = true`

The config has `waydroid.background_start=true`. This means Waydroid auto-starts its container on login and auto-shows the UI when anything triggers it. **This is why the crashing UI kept stealing focus for 30+ minutes** — the session process kept auto-restarting the container, and each crash triggered the UI to flash briefly before the hwcomposer killed SurfaceFlinger again.

---

## Known Issues Inventory

| Issue | Severity | Blocks UI? |
|-------|----------|------------|
| `vendor.hwcomposer-2-1` SIGSEGV crash loop | CRITICAL | YES — this is the root crash |
| `ro.hardware.vulkan=radeon` wrong for NVIDIA system | HIGH | Indirect (not causing immediate crash due to swiftshader) |
| iptables/nftables mismatch on Ubuntu 26.04 | MEDIUM | No — network only |
| lxc.hook.post-stop = /dev/null (exit 126) | LOW | No — cosmetic |
| `background_start=true` causing repeated UI pop-ups | UX | Yes — multiplies crash impact |
| waydroid0 NO-CARRIER / IP UNKNOWN | MEDIUM | No — network only |

---

## Fix Strategy

### Immediate: Disable background_start to stop the focus-stealing

```bash
sudo sed -i 's/^waydroid.background_start=true/waydroid.background_start=false/' /var/lib/waydroid/waydroid.prop
# Also in cfg:
sudo waydroid prop set waydroid.background_start false
```

Or edit `/var/lib/waydroid/waydroid.cfg`:
```
waydroid.background_start = False
```

### Root fix: hwcomposer-2-1 SIGSEGV

The `vendor.hwcomposer-2-1` crash is the core issue. Options in priority order:

**Option 1 (preferred): Force software compositor**

Add to `/var/lib/waydroid/waydroid.prop`:
```
ro.hardware.hwcomposer=ranchu
```
The `ranchu` hwcomposer is a software/drm compositor used in AOSP emulator that doesn't require GPU hardware. This bypasses the crashing HWC2 entirely.

Or force the DRM hwcomposer:
```
ro.hardware.hwcomposer=drm
```

**Option 2: Fix the Vulkan property**

Change `ro.hardware.vulkan=radeon` to either blank or `pastel` (the swiftshader/software vulkan):
```
ro.hardware.vulkan=
```
or remove it entirely. With `ro.hardware.egl=swiftshader`, vulkan shouldn't matter but the mismatch may confuse hwcomposer init.

**Option 3: Switch to GBM gralloc + DRM hwcomposer** (proper NVIDIA path)

```
# In waydroid.prop:
ro.hardware.gralloc=gbm
ro.hardware.hwcomposer=drm
gralloc.gbm.device=/dev/dri/renderD128   # use renderD128 (primary), not renderD129
ro.hardware.egl=mesa                      # if mesa DRI works, otherwise keep swiftshader
```
Note: renderD129 maps to the NVIDIA secondary render node; renderD128 is primary. NVIDIA proprietary + Waydroid GBM is not well-supported — mesa/swiftshader is safer here.

### Fix network (iptables → nftables)

Install `iptables-nft` as default:
```bash
sudo update-alternatives --set iptables /usr/sbin/iptables-nft
sudo update-alternatives --set ip6tables /usr/sbin/ip6tables-nft
```
Then restart the container so waydroid-net.sh re-runs with the working backend.

---

## Recommended sequence

1. `waydroid session stop` (already done)
2. Edit `/var/lib/waydroid/waydroid.prop`, add `ro.hardware.hwcomposer=ranchu`
3. Set `waydroid.background_start=false` in waydroid.cfg
4. Fix iptables: `sudo update-alternatives --set iptables /usr/sbin/iptables-nft`
5. `waydroid session start && waydroid show-full-ui`
6. Monitor: `journalctl -f | grep -E "hwcomposer|surfaceflinger|signal"`

If `ranchu` hwcomposer works, SurfaceFlinger won't crash and the UI will stay up.
