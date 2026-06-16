> DRAFT — for review before committing to doc/

# SKIKK Thor 16 — Health Check Runbook

**Machine:** SKIKK Thor 16 (Tongfang GM6HG7Y) · AMD Ryzen 9 9955HX3D · RTX 5070 Ti (Blackwell GB203M)
**OS:** Ubuntu 26.04 LTS · kernel 6.17.0-23-generic · nvidia-open 580.126.09 · tuxedo-drivers 4.22.2

---

## 1. Purpose and Cadence

This runbook defines repeatable health checks so any CC session can establish a known baseline without re-inventing diagnostics.

| Trigger | Check level |
|---------|-------------|
| Start of any admin session | Quick (section 2) |
| After reboot | Full (section 3) |
| After driver/kernel/BIOS update | Full + firmware section |
| Investigating freeze, hang, or thermal complaint | Full |
| Weekly (unattended) | Quick |

The quick check takes under 2 minutes. The full check takes 5–10 minutes depending on SMART scan time.

---

## Quick Reference — When to Run What

Use this table to pick the right command without reading the full runbook.

| Situation | Command | Takes |
|-----------|---------|-------|
| Starting any admin session | `just health-quick` | ~2 min |
| After a reboot | `just health-full` | ~5 min |
| After a kernel/driver update | `just health-full` then `just gpu-pm-status` | ~7 min |
| Machine feels hot / fan loud | `just temps` | instant |
| Want to reduce fan noise | `just fan-balanced` | instant |
| Doing heavy GPU/CPU work | `just fan-performance` | instant |
| Done with intensive work | `just fan-auto` | instant |
| Investigating storage growth | `just disk-usage` | ~30 sec |
| Checking drive health | `just smart-check` | ~10 sec (needs `sudo smartctl**` in CC allowlist) |
| Syncing CC config from this machine to others | `just dotfiles-diff` then `just dotfiles-apply` | instant |
| Pulling CC config updates from another machine | `just dotfiles-update` | instant |
| Suspecting GPU power management issue | `just gpu-pm-status` then check dmesg | instant |
| Suspecting ethernet freeze / NIC stranded | `just aspm-status` | instant |
| Want a full audit trail for later comparison | `just health-log` | ~5 min |
| Checking whether metrics are drifting over time | `just health-snapshot` then `cat logs/health-metrics.tsv` | instant |

---

## 2. Quick Health Check (~2 min)

Run these five checks in order. Any FAIL stops the session until resolved.

### Q1 — Failed systemd units

```bash
systemctl --failed
```

**Pass:** `0 loaded units listed`
**Fail:** Any unit in `failed` state — investigate with `journalctl -xe -u <unit>`

---

### Q2 — GPU runtime PM fix in place

```bash
grep NVreg_DynamicPowerManagement /etc/modprobe.d/nvidia-power.conf /etc/modprobe.d/nvidia.conf 2>/dev/null
```

**Pass:** All lines show `=0x01`
**Fail:** Any line shows `=0x02` — machine will freeze under GPU idle. See section 5 (Escalation: GPU).

---

### Q3 — PCIe ASPM policy in live kernel

```bash
grep -o 'pcie_aspm[^ ]*' /proc/cmdline
```

**Pass:** Output includes `pcie_aspm=force` and `pcie_aspm.policy=default`
**Fail:** `policy=powersave` — ethernet will strand in L1 ASPM. See section 5 (Escalation: Networking).
**Note:** If GRUB was recently edited, a reboot may be pending — check `/etc/default/grub` to compare.

---

### Q4 — GPU D3cold storm absent

```bash
sudo dmesg --since "10 minutes ago" | grep -c 'nvidia.*pm_runtime_work\|nvidia.*D3cold\|nvidia.*NVPCF'
```

**Pass:** Count is 0
**Warn:** Count 1–5 — transient, watch
**Fail:** Count > 5 — storm active. Check GPE07 rate: `sudo cat /sys/kernel/debug/acpi/gpe_info 2>/dev/null | grep GPE07` — normal is ~320/sec; >1000/sec with nvidia errors = storm. See section 5 (Escalation: GPU).

---

### Q5 — Root filesystem headroom

```bash
df -h / /data 2>/dev/null
```

**Pass:** Root < 85% used
**Warn:** Root 85–90% — schedule cleanup
**Fail:** Root > 90% — run `du -sh /home/* /var/* /snap` to find candidates. Known large items: snap revisions (`snap list --all`; retain=2 set), `~/.android`, LM Studio models.

---

## 3. Full Health Check

### 3A — Kernel / Firmware

#### ACPI DSDT revision (run after BIOS update only)

```bash
sudo python3 -c "
import struct
hdr = open('/sys/firmware/acpi/tables/DSDT','rb').read(36)
rev = struct.unpack('<I', hdr[24:28])[0]
print(hex(rev))
"
```

**Known good:** `0x0107200A` (Dec 2025 BIOS)
**If changed:** BIOS was updated. The nvpcf_override.cpio in /boot may need rebuilding — but check CLAUDE.md; as of Jun 2026 the BIOS itself ships the empty `PWUP` method that the patch applied, so the override may still be harmless/redundant. Kernel rejection (`OEM revision equal, not greater`) is normal.

#### GRUB cmdline integrity

```bash
cat /proc/cmdline
```

**Required flags present:**
- `pcie_aspm=force` — must be present
- `pcie_aspm.policy=default` — must be `default`, not `powersave`

**Harmless/legacy flags that may still be present:**
- `GRUB_EARLY_INITRD_LINUX_CUSTOM="acpi_override.cpio"` — removed in Jun 2026 cleanup (verify absent in `/etc/default/grub`)
- `processor.max_cstate=5` — removed in cleanup (counterproductive)
- `acpi_osi='!Windows 2020'` — removed in cleanup (inert)

#### Kernel messages — noise baseline

```bash
sudo dmesg | grep -E 'error|fail|warn' | grep -v -E 'ite_8291|Bluetooth: hci|acpi-cpufreq|ACPI: \_SB' | tail -30
```

Known-acceptable noise (do not alarm):
- `ite_8291: Failed to rename LED` (×125) — cosmetic, RGB driver
- GPE07 at ~320/sec in `/sys/kernel/debug/acpi/gpe_info` — EC Dynamic Boost polling, hardware characteristic

---

### 3B — GPU

#### Dynamic PM setting

```bash
grep NVreg_DynamicPowerManagement /etc/modprobe.d/nvidia-power.conf /etc/modprobe.d/nvidia.conf 2>/dev/null
```

**Pass:** All occurrences = `0x01`
**Note:** There are currently three occurrences across two files — all must be `0x01`. If you ever need to change this value, update all three.

#### GPU firmware mode

```bash
nvidia-smi --query-gpu=name,driver_version,persistence_mode --format=csv,noheader
```

**Pass:** Returns RTX 5070 Ti entry without error.
**Note:** `NVreg_EnableGpuFirmware=0` in modprobe is silently ignored on Blackwell — GSP is mandatory. This is expected.

#### D3cold storm check (extended window)

```bash
sudo journalctl -k --since "1 hour ago" | grep -c 'pm_runtime_work\|NVPCF\|D3cold'
```

**Pass:** 0
**Fail:** > 0 — see Escalation: GPU

#### GPE07 rate (EC polling — should be low/stable)

```bash
sudo cat /sys/kernel/debug/acpi/gpe_info 2>/dev/null | grep -i 'gpe07\|GPE07'
```

**Pass/normal:** ~320 counts/sec accumulation rate (EC Dynamic Boost polling — hardware characteristic)
**Alarm:** Rate >1000/sec accompanied by nvidia dmesg errors = D3cold storm active

---

### 3C — Storage

#### NVMe SMART — both drives

```bash
sudo smartctl -a /dev/nvme0n1 | grep -E 'Model|Serial|Temperature|Available_Spare|Unsafe_Shutdowns|Media_Errors|Power_On_Hours'
sudo smartctl -a /dev/nvme1n1 | grep -E 'Model|Serial|Temperature|Available_Spare|Unsafe_Shutdowns|Media_Errors|Power_On_Hours'
```

**Pass criteria:**
- `Available_Spare` > 10%
- `Media_Errors` = 0 (or unchanged from last check)
- `Temperature` < 70°C

**Note:** Requires `sudo smartctl**` in CC bash allowlist. If blocked, add the allowlist entry first.

#### Filesystem usage

```bash
df -h / /data
```

**Baselines (Jun 2026):**
- Root (`/`): ~75–76% used, ~222 GB free
- `/data`: ~25% used, ~701 GB free

---

### 3D — Networking

#### Ethernet carrier state

```bash
ip link show enp5s0
cat /sys/class/net/enp5s0/carrier 2>/dev/null && echo "carrier: UP" || echo "carrier: DOWN (check cable)"
```

**Pass (cable plugged):** `state UP`, carrier = `1`
**Pass (no cable):** `state DOWN`, `NO-CARRIER` — driver is healthy, physical link absent
**Fail:** `state DOWN` with cable plugged in — r8125 stranded in L1 ASPM. Verify `pcie_aspm.policy=default` in `/proc/cmdline`; if missing, update GRUB and reboot.

#### r8125 driver loaded

```bash
lsmod | grep r8125
```

**Pass:** `r8125` listed (not `r8169`)
**Fail:** `r8169` loaded — wrong driver. Check `/etc/modprobe.d/blacklist-r8169.conf` exists.

---

### 3E — Thermal

#### DIMM temperatures

```bash
sensors | grep -A5 'spd\|dimm\|DIMM\|ddr'
```

**Baselines:**
- DIMM 0: typically 40–48°C at idle
- DIMM 1: typically 45–54°C under load — **high alarm threshold is 55°C**

**Warn:** DIMM 1 > 52°C at idle — indicates memory-intensive background work
**Fail:** Any DIMM > 55°C — stop memory-intensive work, check for runaway processes

#### CPU package temperature

```bash
sensors | grep -E 'Tctl|Tdie|Package'
```

**Idle pass:** < 55°C
**Load pass:** < 95°C (Ryzen 9955HX3D TjMax = 100°C)

#### GPU temperature

```bash
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader
```

**Idle pass:** < 45°C
**Alarm:** > 80°C at idle — check pm_runtime_work fix (section 3B); pre-fix idle was 84°C during D3cold storm

---

### 3F — Processes

#### Zombie count

```bash
ps aux | awk '$8=="Z"' | wc -l
```

**Normal:** 0–10 (background noise; post-reboot baseline was 6)
**Warn:** > 20 — identify parents: `ps aux | awk '$8=="Z" {print $3}' | sort -u | xargs ps -p`
**Note:** Before the Jun 2026 reboot there were 131 zombies (kompreno-app container leaking); reboot cleared them. Kompreno-app is now `Exited` and not retrying.

#### Podman containers

```bash
podman ps -a
```

**Expected state:**
- `kompreno-app`: `Exited` — this is correct; it is not set to auto-restart
- No containers in `Restarting` loop

**Fail:** Any container in `Restarting` loop with rapid restart count — investigate `podman logs <container>`

---

### 3G — Mounts

#### rclone cloud mounts

```bash
mount | grep rclone
systemctl status rclone-googledrive.service rclone-onedrive.service --no-pager -l
```

**Pass:** Both services `active (running)`, both mountpoints appear in `mount` output
**Expected mountpoints:** `~/GoogleDrive` and `~/OneDrive` (verify exact paths with `mount | grep rclone`)

**Fail — GoogleDrive:** Service failed — check `journalctl -xe -u rclone-googledrive.service`
**Fail — OneDrive:** Token may have expired (happened Jun 2026) — reconnect interactively with `rclone config reconnect onedrive:` then restart the service

---

## 4. Known-Good Baselines

| Item | Normal value | Alarm threshold | Notes |
|------|-------------|-----------------|-------|
| GPE07 rate | ~320/sec | >1000/sec + nvidia dmesg errors | EC Dynamic Boost polling — hardware characteristic |
| DIMM 0 temp | 40–48°C idle | >55°C | — |
| DIMM 1 temp | 45–54°C under load | >55°C | Runs hot by design; monitor during memory-intensive work |
| Root filesystem | ~75% used | >90% | 222 GB free as of Jun 2026 |
| /data filesystem | ~25% used | >85% | 701 GB free as of Jun 2026 |
| Zombie count | 0–10 | >20 | Background noise; kompreno-app was source of 131 pre-reboot |
| `ite_8291` boot warnings | 125 occurrences | — | Cosmetic RGB driver issue, not a bug |
| Battery cycle count | 0 | — | EC doesn't expose wear data; always 0 |
| NVreg_DynamicPowerManagement | `0x01` | `0x02` = freeze risk | 3 occurrences across 2 files — must all be `0x01` |
| pcie_aspm.policy | `default` | `powersave` = NIC freeze | Must be `default`; `force` stays permanently |
| DSDT OEM revision | `0x0107200A` | Change = BIOS updated | Check offset 24–28 (not 32–36 which is Creator Revision) |
| GPU idle temp (fix active) | < 45°C | > 60°C idle | Was 84°C during D3cold storm before fix |

---

## 5. Escalation

### GPU — D3cold storm / pm_runtime_work freeze

**Symptoms:** GPU idle temp > 60°C, GPE07 rate > 1000/sec, dmesg full of `nvidia pm_runtime_work` / `NVPCF` / `D3cold` entries, eventual hard freeze.

**First check:**
```bash
grep NVreg_DynamicPowerManagement /etc/modprobe.d/nvidia-power.conf /etc/modprobe.d/nvidia.conf
```
Must all be `0x01`. If any is `0x02`, run `.scratch/fix_nvidia_dynpm.sh` (or set manually and `sudo update-initramfs -u -k all`).

**Root cause reference:** nvidia-open bug in `rm_acpi_nvpcf_notify()` — calls `os_ref_dynamic_power()` unconditionally without D3Cold state check. Community PR #1181 (open-gpu-kernel-modules). Unmerged as of Jun 2026.

**When to revert to `0x02`:** Watch 610.x+ nvidia-open release notes for "NVPCF", "RTD3", or "D3cold" fix. Then: `sudo rm /etc/modprobe.d/nvidia-power.conf`, revert `nvidia.conf` to `0x02`, `sudo update-initramfs -u -k all`.

**Reference files:** `.scratch/handover-20260611-nvidia-dynamic-boost-storm.md`, `.scratch/freeze_investigation_20260613_164630.txt`, CLAUDE.md (Active fixes table)

---

### Networking — Ethernet DOWN with cable plugged

**Symptom:** `ip link show enp5s0` shows `state DOWN` or `NO-CARRIER` with physical cable connected.

**Cause:** r8125 NIC stranded in L1 ASPM low-power state.

**Fix sequence:**
1. Verify `/proc/cmdline` contains `pcie_aspm.policy=default` — if it shows `powersave`, GRUB edit didn't take effect
2. Check `/etc/default/grub` for `pcie_aspm.policy=default`
3. If missing from GRUB: add it, run `sudo update-grub`, reboot
4. Verify `lsmod | grep r8125` (not r8169) and `/etc/modprobe.d/blacklist-r8169.conf` exists

**Hard constraint:** `pcie_aspm=force` must remain. Only `policy=default` is the fix. Do not remove `force`.

**Reference files:** `.scratch/apply_aspm_fix.sh`, CLAUDE.md (Hard constraints)

---

### Storage — NVMe SMART degraded

**Symptom:** `Available_Spare` < 10%, `Media_Errors` increasing, `Unsafe_Shutdowns` spiking.

**Action:**
```bash
sudo smartctl -a /dev/nvme0n1 > .scratch/smart-nvme0-$(date +%Y%m%d).txt
sudo smartctl -a /dev/nvme1n1 > .scratch/smart-nvme1-$(date +%Y%m%d).txt
```
Compare against previous captures in `.scratch/`. `Media_Errors` > 0 or `Available_Spare` < 10% warrants data backup before further work.

---

### Thermal — DIMM 1 approaching 55°C

**Action:** Identify memory-intensive processes:
```bash
ps aux --sort=-%mem | head -20
```
Stop or throttle them. If at idle, check for runaway background jobs. If sustained > 55°C under normal workload, consider TCC (Tuxedo Control Center) fan profile — see `.scratch/apply_max_fan.sh` for max-fan profile.

---

### rclone — OneDrive token expired

**Symptom:** `rclone-onedrive.service` failed, logs show auth/token error.

**Fix:**
```bash
rclone config reconnect onedrive:
sudo systemctl restart rclone-onedrive.service
systemctl status rclone-onedrive.service
```

---

### Zombie accumulation (> 20)

**Identify zombie parents:**
```bash
ps aux | awk '$8=="Z" {print "zombie PID:",$2,"parent:",$3}' | head -20
ps aux | awk '$8=="Z" {print $3}' | sort -u | xargs -I{} ps -p {} -o pid,comm=
```
If parent is `podman` or `conmon`, kompreno-app container restart loop may have resumed — check `podman ps -a`. A clean reboot clears accumulated zombies when the root cause is fixed.

---

## 6. Check History

| Date | Operator | Level | Result | Notes |
|------|----------|-------|--------|-------|
| 2026-06-15 | CC session (post-reboot) | Full | PASS | pcie_aspm.policy=default live; 0 failed units; 6 zombies (normal); GPU fix active; rclone mounts up; DIMM 1 at 53–54°C (watch); root at 75%. Kompreno-app exited cleanly. |

---

## Appendix: Useful One-Liners

```bash
# Full sensors snapshot
sensors

# All active kernel errors in last boot
sudo journalctl -k -p err -b

# Snap disk usage by revision
snap list --all | awk 'NR>1 {print $1, $3}' | sort

# Check which nvidia modprobe files exist
ls /etc/modprobe.d/nvidia*.conf /etc/modprobe.d/blacklist-r8169.conf 2>/dev/null

# Verify rclone mount contents alive (not stale mount)
ls ~/GoogleDrive | head -3
ls ~/OneDrive | head -3

# PCIe ASPM current policy (live, not just cmdline)
cat /sys/module/pcie_aspm/parameters/policy

# ACPI GPE counts snapshot
sudo cat /sys/kernel/debug/acpi/gpe_info

# Check all DKMS module status (relevant after kernel or driver update)
dkms status
```
