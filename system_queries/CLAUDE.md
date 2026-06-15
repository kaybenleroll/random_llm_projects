# system_queries — SKIKK Thor 16 admin workspace

## Machine
SKIKK Thor 16 (Tongfang GM6HG7Y) · AMD Ryzen 9 9955HX3D · RTX 5070 Ti (Blackwell GB203M)
Ubuntu 26.04 LTS · kernel 6.17.0-23-generic · nvidia-open 580.126.09 · tuxedo-drivers 4.22.2

## Hard constraints
- **Keep `pcie_aspm=force` with `pcie_aspm.policy=default`** — r8125 ethernet hard-freezes when `policy=powersave` + `force` push L1 ASPM aggressively, stranding the NIC in a low-power state; `force` must stay but `policy` must remain `default` to allow correct negotiation
- **`/etc/default/grub` edits require `sudo update-grub` + reboot to take effect**
- **BIOS updates invalidate the DSDT override** — rebuild nvpcf_fix.asl against new DSDT after any firmware update

## Active fixes
| Fix | File | Status |
|-----|------|--------|
| NVPCF D3cold storm (nvidia-open bug) | `.scratch/nvpcf_fix.asl` → `/boot/nvpcf_override.cpio` | Superseded |
| pm_runtime_work freeze (Blackwell + fine-grained PM) | `/etc/modprobe.d/nvidia-power.conf` | Live |
| Gemini wrong-fix artifacts | Deleted | Done |
| GRUB cleanup (wrong CPIO, stale flags) | `.scratch/grub_cleanup.sh` | Done |

**NVPCF fix status (Jun 2026):** BIOS Dec 2025 ships `\_SB.INOU.PWUP` as an empty method — the same fix our DSDT patch applied. The initrd override is no longer needed. The kernel rejects our cpio anyway (OEM revision equal, not greater) so it's harmless to leave in place.

**pm_runtime_work fix (Jun 2026):** `NVreg_DynamicPowerManagement=0x01` (coarse-grained) set in `/etc/modprobe.d/nvidia-power.conf` and `/etc/modprobe.d/nvidia.conf`. Fine-grained (`0x02`) causes pm_runtime_work callbacks to block the system workqueue on Blackwell GB203M, eventually hard-freezing the machine. Root cause: nvidia-open 580.126.09 (upgraded May 3 2026) introduced a bug in `rm_acpi_nvpcf_notify()` — calls `os_ref_dynamic_power()` unconditionally without D3Cold state check. Fix is in community PR #1181 (open-gpu-kernel-modules, filed Jun 6 2026, unmerged as of Jun 2026). Available drivers: 580.159.04 and 610.43.02 — neither contains the fix. **Revert when nvidia-open fixes Blackwell runtime PM** — watch 610.x+ release notes for "NVPCF", "RTD3", or "D3cold" fix, then `sudo rm /etc/modprobe.d/nvidia-power.conf`, revert nvidia.conf to `0x02`, and `sudo update-initramfs -u -k all`.

## File layout
```
dsdt.dsl              — decompiled firmware DSDT (source of truth for ACPI work)
dsdt.dat              — raw DSDT binary
SKIKK_Support_Dossier.md  — hardware/platform context
.scratch/             — all working files, scripts, outputs
```

## Working approach
- All temp and output files go in `.scratch/` — never `/tmp/`
- Scripts that need root use `sudo` internally; run them as `bash .scratch/script.sh`, not `sudo bash`
- Subagents do implementation; this session orchestrates
- Check DSDT OEM revision (offset 24-28, not 32-36 which is Creator Revision): `sudo python3 -c "import struct; hdr=open('/sys/firmware/acpi/tables/DSDT','rb').read(36); rev=struct.unpack('<I',hdr[24:28])[0]; print(hex(rev))"` — firmware is `0x0107200A` (Dec 2025 BIOS)

## Known platform quirks
- GPE07 fires ~320/sec (EC Dynamic Boost polling) — hardware characteristic, not a bug
- `ite_8291` logs 125 LED rename warnings at boot — cosmetic, RGB driver issue
- `NVreg_EnableGpuFirmware=0` in modprobe.d is silently ignored (GSP mandatory on Blackwell)
- Battery cycle count always reads 0 — EC doesn't expose wear data
