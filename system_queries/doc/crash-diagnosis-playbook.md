# Crash Diagnosis Playbook

General, machine-agnostic techniques for diagnosing a kernel panic or crash
using kdump + journalctl. Not narrative — see the origin investigation for
the full story: `doc/skikk-thor-history.md` §2.37 (kernel panic diagnosis on
SKIKK Thor 16, 2026-08-08).

## 1. Correlate kdump dumps by timestamp, not by content

- kdump crash dump directories are named by timestamp:
  `/var/crash/YYYYMMDDHHMM/` — e.g. `/var/crash/202608081829/` =
  2026-08-08 18:29.
- Use that timestamp directly to cross-reference OTHER log sources for the
  same moment (`journalctl -b -1`, health-save snapshots, etc.) — don't
  grep timestamps out of the dmesg content first.

## 2. Never trust a keyword-filtered grep alone

- A keyword scan of a crash dump (e.g. `panic|Oops|BUG|thermal|GPU|ACPI-AC`)
  can silently miss the actual root cause if you don't already know which
  subsystem is involved.
- Example: an IOMMU fault (`AMD-Vi: Event logged`) and a USB-C PD interface
  failure (`ucsi_acpi`) at the exact crash timestamp were only found via a
  live journal snapshot — neither matched the original keyword patterns,
  and neither appeared in the crash dump's own raw dmesg tail.
- **Always follow a keyword scan with an unfiltered pull of raw dmesg lines
  around the identified timestamp** (+/- a few seconds), not just the
  matched categories.

## 3. Cross-check journalctl separately — it can diverge from kdump dmesg

- The persistent journal survives across a crash/reboot and can be
  correlated by wall-clock timestamp against a kdump directory name.
- kdump captures only what made it into the *crashing* kernel's own ring
  buffer before it died. journalctl on the *next* boot may hold entries
  for the same wall-clock second logged via a different path (e.g.
  hardware/ACPI/USB-C events) that never reached the ring buffer at all.
- Treat kdump dmesg and journalctl as two independent sources for the same
  event window — check both, don't assume one subsumes the other.
