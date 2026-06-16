# SKIKK Thor 16 — NVIDIA Dynamic Boost storm / nvidia-open driver patch

## Branch / SHA
Branch: main | Latest: 772b0dc

## System
SKIKK Thor 16 (Tongfang GM6HG7Y), AMD Ryzen 9 9955HX3D + NVIDIA RTX 5070 Ti (Blackwell, GB203M),
Ubuntu 25.10, kernel 6.17.0-23-generic, nvidia-open 580.126.09, tuxedo-drivers DKMS 4.22.2.

## Root cause — CONFIRMED via live EC tracing
EC query byte `0x84` → `_Q84` ACPI handler (dsdt.dsl:9468) → `INOU.PWUP` → `Notify(NPCF, 0xC0)` +
`Notify(GPP0.PEGP, 0xC5)`. Driver bug: `rm_acpi_nvpcf_notify()` in nvidia-open calls
`os_ref_dynamic_power()` unconditionally — no D3Cold state check. EC re-asserts before GPU
finishes waking → 321/sec loop → 84°C idle.

**Upstream fix: NVIDIA/open-gpu-kernel-modules PR #1181** — "Don't wake a runtime-suspended dGPU
to service NVPCF/GPS ACPI notifies". Open, unmerged in 580.126.09.

## Three viable fixes (ranked)

1. **Apply PR #1181 as local DKMS patch** — fixes bug at source, Dynamic Boost stays functional
2. **SSDT override: null `Notify(NPCF, 0xC0)` in `_Q84`** — community workaround cited in PR #1181;
   existing `rtac_fix.asl` in repo is wrong target, but approach is right
3. **`acpi_mask_gpe=0x07`** — broadest hammer, fallback only

## Recommended first action
Attempt option 1:
1. Fetch PR #1181 diff from https://github.com/NVIDIA/open-gpu-kernel-modules/pull/1181
2. Locate the affected files in `/usr/src/nvidia-580.126.09/` (DKMS source tree)
3. Apply patch, rebuild DKMS module: `sudo dkms build -m nvidia -v 580.126.09 && sudo dkms install -m nvidia -v 580.126.09`
4. Reboot, measure gpe07 delta

## NOT yet tested (still pending from this session)
- `sudo modprobe -r tuxedo_nb02_nvidia_power_ctrl` + measure gpe07 delta
  (safe: display on amdgpu, refcount 0 — low probability of fixing storm but worth confirming)

## CRITICAL constraint
Do NOT remove `pcie_aspm=force` until storm is resolved — documented hard soft-lockup freeze
(r8125 + ASPM negotiation). See SKIKK_Support_Dossier.md.

## Gemini artifacts (safe to clean up AFTER storm is fixed)
- `GRUB_EARLY_INITRD_LINUX_CUSTOM="acpi_override.cpio"` — wrong fix, remove
- `acpi_osi='!Windows 2020'` — inert, remove
- `processor.max_cstate=5` — counterproductive, remove
- `pcie_aspm=force` — KEEP until storm fixed
- `/etc/modprobe.d/blacklist-r8169.conf` — KEEP (r8125 is correct driver)
- `/etc/modprobe.d/nvidia-gsp.conf` (NVreg_EnableGpuFirmware=0) — silently ignored on Blackwell,
  harmless but pointless
- NVIDIA options in modprobe (NVreg_DynamicPowerManagement=0x02 etc) — KEEP

## Key source files
- `dsdt.dsl` — `_Q84` at lines 9468-9482, `ECMG` OperationRegion at 8542
- `ssdt23.dsl` — AMD PEP SSDT (RTAC here — irrelevant to storm)
- `.scratch/clean_slate_plan.md` — stress-tested plan (DBEN/DBAP clearing approach rejected)
- `HANDOVER_REPORT.md` — Gemini's handover; do NOT trust its "RESOLVED" claim

## User running sudo
User can run sudo commands in a separate terminal and paste output back.
`! sudo <cmd>` fails (no TTY for interactive auth).
