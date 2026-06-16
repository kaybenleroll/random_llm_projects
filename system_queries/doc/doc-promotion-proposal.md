# .scratch/ → Project Promotion Proposal

_Generated: 2026-06-16 | Revised: 2026-06-16 (destination folders updated)_

---

## Summary Table

| Filename | Size | Recommendation | Destination | One-line reason |
|----------|------|----------------|-------------|-----------------|
| `handover-20260611-nvidia-dynamic-boost-storm.md` | 3.1 KB | **Promote** | `doc/` | Decision record + root-cause analysis; needed for 610.x driver revert evaluation |
| `handover-20260614-system-health-waydroid.md` | 3.0 KB | **Promote** | `doc/` | Current config state + disk baseline; reference for Jul 2026 driver check |
| `handover-20260615-post-reboot-clean.md` | 2.2 KB | **Promote** | `doc/` | Most current system health snapshot with actionable watch items |
| `waydroid_crash_diagnosis_20260614.md` | 7.6 KB | **Promote** | `doc/` | Full crash-chain diagnosis; starting point when waydroid is retried on 610+ |
| `chezmoi-migration-report.md` | 17 KB | **Promote** | `doc/` | Design rationale for the dotfiles setup (the why) |
| `chezmoi-explainer-report.md` | 20 KB | **Promote** | `doc/` | What was built: layout, templates, bootstrapping instructions for uhet |
| `chezmoi-setup-log.md` | 4.0 KB | **Promote** | `doc/` | Canonical record of what was done: versions, commits, exact file set |
| `tcc_profiles_new.json` | 6.4 KB | **Promote** | `config/` | Live TCC fan profiles; source of truth if tccd config is reset |
| `tcc_settings_new.json` | 9.1 KB | **Promote** | `config/` | Live TCC settings; pairs with tcc_profiles_new.json |
| `switch_profile.sh` | 2.1 KB | **Promote** | `scripts/` | Reusable TCC profile switcher; solves the daemon overwrite race |
| `nvpcf_fix.asl` | 393 KB | **Promote** | `acpi/` | Only copy of the NVPCF DSDT patch source; keep until BIOS update confirmed |
| `dsdt_bios_20251212.dat` | 50 KB | **Promote** | `acpi/` | Versioned DSDT binary for Dec 2025 BIOS; reference for any future ACPI work |
| `dsdt_bios_20251212.dsl` | 391 KB | **Promote** | `acpi/` | Decompiled Dec 2025 DSDT source; needed for ACPI work on this firmware rev |
| `remediation_plan.md` | 3.3 KB | **Delete** | — | Superseded; conclusions in promoted handover + CLAUDE.md |
| `clean_slate_plan.md` | 3.8 KB | **Delete** | — | Executed; findings in CLAUDE.md |
| `handover-20260614-foliate-pending-reboot.md` | 1.2 KB | **Delete** | — | Superseded by post-reboot handover; nothing unique |
| `freeze_investigation_20260613_164630.txt` | 14 KB | **Delete** | — | Forensic log; root cause fixed and documented |
| `post_reboot_diag_20260613_173702.txt` | 3.2 KB | **Delete** | — | One-off verification; outcome captured in promoted docs |
| `audit_data.txt` | 141 KB | **Delete** | — | Raw diagnostic dump from investigation phase; superseded |
| `test_compile.dsl` | 391 KB | **Delete** | — | Intermediate ACPI build artifact; not source |
| `test_compile.aml` | 50 KB | **Delete** | — | Binary build artifact; derived from source |
| `nvpcf_fix.aml` | 50 KB | **Delete** | — | Binary; regenerable from nvpcf_fix.asl |
| `nvpcf_fix.aml.bak` | 50 KB | **Delete** | — | Backup of above binary; doubly redundant |
| `nvpcf_fix.hex` | 465 KB | **Delete** | — | Hex dump of deleted binary; no independent value |
| `nvpcf_override.cpio` | 51 KB | **Delete** | — | Kernel rejects it (OEM revision equal, not greater); superseded per CLAUDE.md |
| `kernel/firmware/acpi/nvpcf_fix.aml` | 50 KB | **Delete** | — | Staged into CPIO layout; same binary as above |
| `grub_cleanup.sh` | 1.1 KB | **Delete** | — | Applied and done; CLAUDE.md status=Done |
| `apply_aspm_fix.sh` | 2.2 KB | **Delete** | — | Applied Jun 14; ASPM constraint in CLAUDE.md |
| `apply_max_fan.sh` | 1.0 KB | **Delete** | — | Applied; config/ JSON is the durable artifact |
| `fix_nvidia_dynpm.sh` | 3.9 KB | **Delete** | — | Applied Jun 13; one-shot, no re-use value |
| `install_nvpcf_fix.sh` | 1.4 KB | **Delete** | — | Installed superseded CPIO override |
| `apply_rsyslog_filter.sh` | 677 B | **Delete** | — | Applied; live file is canonical |
| `10-drop-acpi-ec.conf` | 196 B | **Delete** | — | Deployed to /etc/rsyslog.d/; live file is canonical |
| `apply_waydroid_fix.sh` | 885 B | **Delete** | — | Applied; diagnosis doc is the reference |
| `apply_waydroid_cfg.sh` | 422 B | **Delete** | — | Applied |
| `apply_egl_fix.sh` | 239 B | **Delete** | — | Applied |
| `waydroid.prop.new` | 807 B | **Delete** | — | Staging file; applied; waydroid.prop is regenerated each session anyway |
| `waydroid.cfg.new` | 634 B | **Delete** | — | Staging; applied |
| `waydroid.cfg.fixed` | 593 B | **Delete** | — | Staging variant; applied |
| `purge_openclaw.sh` | 1.2 KB | **Delete** | — | Applied; confirmed removed |
| `delete_android_sdk.sh` | 353 B | **Delete** | — | Applied; nothing to reference |
| `brave_investigation.sh` | 1.9 KB | **Delete** | — | One-off diagnostic; migration complete |
| `migrate_brave_to_apt.sh` | 1.3 KB | **Delete** | — | Applied; Brave is now APT-managed |
| `migrate_brave_to_apt.log` | 556 B | **Delete** | — | Execution receipt; migration done |
| `collect_audit.sh` | 4.3 KB | **Delete** | — | Diagnostic collector; no ongoing need |
| `tcc_settings_staged.json` | 9.1 KB | **Delete** | — | Duplicate of tcc_settings_new.json (being promoted) |
| `grub.tmp` | 475 B | **Delete** | — | Temporary GRUB config; applied |
| `options_cfg_backup_20260612.cfg` | 4.1 KB | **Delete** | — | PySol pre-session backup; not a system config |
| `screenshot.jpeg` | 62 KB | **Delete** | — | Unlabelled; information already acted on |
| `patch_settings.sh` | 368 B | **Delete** | — | Manual patch superseded by chezmoi |
| `patch_settings.py` | 1.1 KB | **Delete** | — | Same |
| `uhet_settings_restored.json` | 5.6 KB | **Delete** | — | Staging file; chezmoi now manages settings.json.tmpl |
| `uhet_claude_md_new.md` | 1.6 KB | **Delete** | — | Draft; chezmoi manages ~/.claude/CLAUDE.md |
| `modprobe_nvidia_backup/` (4 files) | 41–313 B | **Delete** | — | Pre-fix backups; no revert value (0x02 caused freezes) |
| `memory/` (4 files) | 401 B–1 KB | **Delete** | — | Stale mirror; canonical files in ~/.claude/projects/.../memory/ |
| `skill-diffs/` (21 files) | 1–28 KB | **Delete** | — | Working files from completed /reflect run; PR #3 merged |
| `skill-diff-report.md` | 20 KB | **Delete** | — | /reflect run complete; chezmoi is now the sync mechanism |
| `learnings-merge-plan.md` | 15 KB | **Delete** | — | Merge completed; chezmoi manages skill files |
| `claude-skill-dir-check.md` | 3.4 KB | **Delete** | — | One-time research; finding acted on |
| `research-dotfiles-tools.md` | 18 KB | **Delete** | — | Raw research input; synthesis in chezmoi-migration-report.md |
| `research-claude-dir-anatomy.md` | 13 KB | **Delete** | — | Same |
| `research-cc-community-sync.md` | 15 KB | **Delete** | — | Same |
| `research-sysadmin-repo.md` | 4.5 KB | **Delete** | — | Same |
| `research-home-dotfiles.md` | 12 KB | **Delete** | — | Same |
| `research-chezmoi-migration.md` | 17 KB | **Delete** | — | Same |
| `cc-config-sync-options.md` | 11 KB | **Delete** | — | Draft absorbed into migration report |
| `chezmoi-discovery.md` | 7.6 KB | **Delete** | — | Pre-setup point-in-time snapshot; now false ("no dotfiles repo") |
| `chezmoi.diff` | 38 KB | **Delete** | — | Setup-time diff snapshot; chezmoi diff can be re-run |
| `settings-rendered-test.json` | 4.8 KB | **Delete** | — | Verification artifact; stale as soon as template changes |

---

## Per-File Sections

---

### handover-20260611-nvidia-dynamic-boost-storm.md
- **Size:** 3.1 KB | **Modified:** 2026-06-11
- **Purpose:** Session handover documenting the confirmed GPE07/NVPCF Dynamic Boost storm root cause, three ranked fix options, the NVIDIA PR #1181 reference, and constraints to observe.
- **Recommendation: Promote to `doc/`**
- **Justification:** The pm_runtime_work freeze fix is live but the upstream bug is unmerged. The next session handling the 610.x driver upgrade will need to re-evaluate whether PR #1181 landed and whether to revert `/etc/modprobe.d/nvidia-power.conf`. This handover explains why the current workaround exists and what to check. CLAUDE.md summarises the status but this document has the depth needed for re-evaluation.
- **Proposed filename:** `doc/nvidia-dynamic-boost-storm-root-cause.md`

---

### handover-20260614-system-health-waydroid.md
- **Size:** 3.0 KB | **Modified:** 2026-06-14
- **Purpose:** Session handover recording: what was done (cleanup, rsyslog filter, ASPM fix, waydroid investigation), waydroid root cause, current config state, cloud routine trig_01JUnBV6BGNv5pJsbQeGNSvw, disk baseline.
- **Recommendation: Promote to `doc/`**
- **Justification:** The waydroid section is reference material for the Jul 2026 driver check. The disk baseline (root 76%, /data 25%) establishes a baseline to track against. The config change log (grub, rsyslog, waydroid.cfg, nvidia-power.conf) is a useful audit trail not duplicated in CLAUDE.md at this level of detail.
- **Proposed filename:** `doc/session-handover-20260614-health-waydroid.md`

---

### handover-20260615-post-reboot-clean.md
- **Size:** 2.2 KB | **Modified:** 2026-06-15
- **Purpose:** Most current system state record: all fixes confirmed live post-reboot, 0 failed systemd units, watch items identified (DIMM 1 temps, root filesystem %, SMART data, triple-set NVreg).
- **Recommendation: Promote to `doc/`**
- **Justification:** This is the current baseline. The watch items (DIMM 1 at 53-54°C, root at 75%, SMART not yet checked, nvidia.conf has NVreg set three times) are actionable on the next session. These are not in CLAUDE.md.
- **Proposed filename:** `doc/system-state-20260615-post-reboot.md`

---

### waydroid_crash_diagnosis_20260614.md
- **Size:** 7.6 KB | **Modified:** 2026-06-14
- **Purpose:** Full crash-chain analysis: hwcomposer-2-1 SIGSEGV root cause, binder storm explanation, EGL/Vulkan config audit, iptables/nftables mismatch, fix strategy ranked by option.
- **Recommendation: Promote to `doc/`**
- **Justification:** Waydroid is parked but the intent is to retry when nvidia-open 610+ improves Blackwell GBM support. This document is the starting point — it documents exactly why the current vendor image fails on this hardware configuration, which options were tried, and what the recommended retry path is. Without it, a future session re-diagnoses from scratch.
- **Proposed filename:** `doc/waydroid-hwcomposer-crash-diagnosis.md`

---

### chezmoi-migration-report.md
- **Size:** 17 KB | **Modified:** 2026-06-16
- **Purpose:** Decision document comparing Option A (convert sysadmin_files), B (new dotfiles repo), C (chezmoi for ~/.claude/ only). Recommends and documents Option B. Includes the candidate file list with templating notes and step-by-step migration procedure.
- **Recommendation: Promote to `doc/`**
- **Justification:** This is the design rationale for the dotfiles setup. If the setup ever needs to be understood, extended, or reproduced on a new machine, this explains the why. chezmoi-explainer-report.md covers the what; this covers the reasoning.
- **Proposed filename:** `doc/chezmoi-migration-decision.md`

---

### chezmoi-explainer-report.md
- **Size:** 20 KB | **Modified:** 2026-06-16
- **Purpose:** Detailed explainer of what was set up: source repo layout, tracking inclusions and exclusions rationale, template system (homeDir + hostname conditionals), sysadmin_files relationship, current state per machine, and bootstrapping instructions for uhet.
- **Recommendation: Promote to `doc/`**
- **Justification:** uhet has not yet had `chezmoi apply` run. This document has the exact commands needed to bootstrap it. It also explains the template logic for settings.json.tmpl, which future sessions will need when adding new MCP permissions or modifying the config. High ongoing utility.
- **Proposed filename:** `doc/chezmoi-setup-explainer.md`

---

### chezmoi-setup-log.md
- **Size:** 4.0 KB | **Modified:** 2026-06-16
- **Purpose:** Execution log of the chezmoi setup: versions installed, GitHub repo created, exact commits (439b992, b75b024), template substitution counts, directory tree of the source repo.
- **Recommendation: Promote to `doc/`**
- **Justification:** Records what was actually done at the file level — commit SHAs, counts, exact directory structure. Complements the explainer. Useful for auditing whether a file was tracked or not, and for verifying the source repo state on any future machine.
- **Proposed filename:** `doc/chezmoi-setup-log.md`

---

### tcc_profiles_new.json
- **Size:** 6.4 KB | **Modified:** 2026-06-11
- **Purpose:** TCC fan control profiles: TUXEDO Defaults, Thor Balanced, Thor Deep Freeze, Thor Max Fan, Thor Gaming. Custom fan curves with CPU/GPU temperature tables.
- **Recommendation: Promote to `config/`**
- **Justification:** This is a live configuration file, not a written explanation. `config/` is the right home — these are the reference configs for the TCC service, equivalent to what you'd track in a sysadmin config repo. If /etc/tcc/profiles is ever reset (tuxedo-drivers update, TCC reinstall), this is the source of truth. The Gaming profile in particular has a deliberate fan curve not regenerable from memory.
- **Proposed filename:** `config/tcc-profiles.json`

---

### tcc_settings_new.json
- **Size:** 9.1 KB | **Modified:** 2026-06-12
- **Purpose:** Full TCC settings file, including stateMap profile assignments per power state (AC vs battery).
- **Recommendation: Promote to `config/`**
- **Justification:** Same rationale as tcc_profiles_new.json — this is a service config, not a document. Together the two JSON files reconstruct the full TCC configuration. If tccd is reset or the config directory is wiped, both are needed.
- **Proposed filename:** `config/tcc-settings.json`

---

### switch_profile.sh
- **Size:** 2.1 KB | **Modified:** 2026-06-12
- **Purpose:** Utility for switching TCC AC fan profile without a tccd daemon overwrite race. Handles reading/writing settings correctly (stop daemon → write → start). Also includes the DSDT OEM revision check.
- **Recommendation: Promote to `scripts/`**
- **Justification:** Previously marked "Keep in .scratch/" but this is a reusable maintenance utility, not a one-shot application script or a working file. `scripts/` is the correct home — it's a tool you'll reach for whenever switching TCC profiles. The daemon overwrite problem it solves is real and will recur. Promoting it out of `.scratch/` makes it findable and signals it's not disposable.
- **Proposed filename:** `scripts/switch_tcc_profile.sh`

---

### nvpcf_fix.asl
- **Size:** 393 KB | **Modified:** 2026-06-11
- **Purpose:** Full ASL source of the NVPCF DSDT patch (DSDT with `\_SB.INOU.PWUP` nulled out). The patch is superseded because the Dec 2025 BIOS already has PWUP as an empty method, but this is the only copy of the patched ASL.
- **Recommendation: Promote to `acpi/`**
- **Justification:** Previously marked "Keep in .scratch/" but `.scratch/` is for working files, not archival source. `acpi/` groups the firmware/ACPI artifacts alongside the Dec 2025 DSDT snapshots, making the relationship between them clear. Keep until it is verified no subsequent BIOS update has reintroduced the PWUP body. If a future BIOS update reinstates the bug, this ASL provides the starting point for rebuilding the patch.
- **Proposed filename:** `acpi/nvpcf_fix.asl`

---

### dsdt_bios_20251212.dat
- **Size:** 50 KB | **Modified:** 2026-06-12
- **Purpose:** Raw DSDT binary from the Dec 2025 BIOS (OEM revision 0x0107200A). Reference for ACPI work against this specific firmware revision.
- **Recommendation: Promote to `acpi/`**
- **Justification:** Previously marked "Keep in .scratch/" but this is a versioned reference artifact with long-term value. CLAUDE.md notes that the root-level `dsdt.dat` is the "current" DSDT; this file is explicitly the Dec 2025 snapshot, needed for comparison if a future BIOS update changes the DSDT. `acpi/` groups it with its decompiled counterpart and the patch source.
- **Proposed filename:** `acpi/dsdt_bios_20251212.dat`

---

### dsdt_bios_20251212.dsl
- **Size:** 391 KB | **Modified:** 2026-06-12
- **Purpose:** Decompiled DSDT ASL from the Dec 2025 BIOS. Needed for any future ACPI work on this firmware revision.
- **Recommendation: Promote to `acpi/`**
- **Justification:** Same rationale as the .dat file. CLAUDE.md already tracks root-level `dsdt.dsl` as the current decompiled DSDT. This is the Dec 2025-versioned snapshot — different file, different purpose. `acpi/` is the correct home.
- **Proposed filename:** `acpi/dsdt_bios_20251212.dsl`

---

### remediation_plan.md
- **Size:** 3.3 KB | **Modified:** 2026-06-10
- **Purpose:** Early analysis plan for the GPE07 storm, written before root cause was confirmed. Identified RTAC as a wrong diagnosis, proposed four diagnostic steps.
- **Recommendation: Delete**
- **Justification:** Superseded by clean_slate_plan.md (which has the confirmed root cause) and then by the fix being applied. The first-principles analysis it contains is reproduced and improved in the handover document being promoted. Nothing here is not in the promoted documents.

---

### clean_slate_plan.md
- **Size:** 3.8 KB | **Modified:** 2026-06-10
- **Purpose:** Root-cause confirmed plan: EC query 0x84 / _Q84 NVIDIA Dynamic Boost notification loop, clean-slate remediation steps.
- **Recommendation: Delete**
- **Justification:** The plan was executed. Its findings are captured in the promoted handover document. The CLAUDE.md active-fixes table records the current state. Retaining this as a planning doc after execution adds confusion about whether it's still pending.

---

### handover-20260614-foliate-pending-reboot.md
- **Size:** 1.2 KB | **Modified:** 2026-06-14
- **Purpose:** Bridge handover: Foliate installed, reboot still pending, waydroid still parked, points to the other handover for detail.
- **Recommendation: Delete**
- **Justification:** Entirely superseded by handover-20260615-post-reboot-clean.md which records the reboot completion. Nothing unique here.

---

### freeze_investigation_20260613_164630.txt
- **Size:** 14 KB | **Modified:** 2026-06-13
- **Purpose:** Forensic diagnostic report from the Jun 13 hard freeze: boot timeline, journal sections, GRUB/cmdline state at the time.
- **Recommendation: Delete**
- **Justification:** The freeze was caused by fine-grained DynamicPowerManagement on Blackwell. That is fixed and documented. This is a point-in-time forensic artifact — its diagnostic value was realised when the fix was identified. No future session needs to re-read a 14 KB symptom dump.

---

### post_reboot_diag_20260613_173702.txt
- **Size:** 3.2 KB | **Modified:** 2026-06-13
- **Purpose:** Post-fix verification output confirming DynamicPowerManagement=1, no pm_runtime_work events, openclaw user removed.
- **Recommendation: Delete**
- **Justification:** Fix verification complete. State confirmed. The promoted handover documents capture the outcome.

---

### audit_data.txt
- **Size:** 141 KB | **Modified:** 2026-06-11
- **Purpose:** Raw system diagnostic dump from collect_audit.sh — dmesg, nvidia-smi, systemd status, memory, kernel cmdline.
- **Recommendation: Delete**
- **Justification:** Point-in-time forensic dump from early in the session when the problem was being characterised. Entirely superseded. Not a document; just data.

---

### test_compile.dsl / test_compile.aml
- **Sizes:** 391 KB / 50 KB | **Modified:** 2026-06-11
- **Purpose:** ACPI ASL compilation test artifacts; intermediate steps during NVPCF DSDT work.
- **Recommendation: Delete**
- **Justification:** Build artifacts, not source. The source (nvpcf_fix.asl, dsdt_bios_20251212.dsl) is being promoted to `acpi/`. These compilations carry no information not in the source.

---

### nvpcf_fix.aml / nvpcf_fix.aml.bak / nvpcf_fix.hex / nvpcf_override.cpio / kernel/firmware/acpi/nvpcf_fix.aml
- **Sizes:** 50 KB / 50 KB / 465 KB / 51 KB / 50 KB | **Modified:** 2026-06-11
- **Purpose:** Binary artifacts from the NVPCF patch build chain.
- **Recommendation: Delete**
- **Justification:** All are derived from nvpcf_fix.asl (which is being promoted to `acpi/`) or from each other. The kernel rejects the CPIO (OEM revision equal, not greater per CLAUDE.md). Regenerable from source. Deleting saves ~675 KB with no information loss.

---

### grub_cleanup.sh / apply_aspm_fix.sh / apply_max_fan.sh / fix_nvidia_dynpm.sh / install_nvpcf_fix.sh / apply_rsyslog_filter.sh / apply_waydroid_fix.sh / apply_waydroid_cfg.sh / apply_egl_fix.sh / purge_openclaw.sh / delete_android_sdk.sh
- **Sizes:** 239 B – 3.9 KB | **Modified:** 2026-06-11 to 2026-06-14
- **Purpose:** One-shot application scripts, each applied during the sessions that fixed specific issues.
- **Recommendation: Delete**
- **Justification:** Every script in this group was applied and its effect confirmed. None has re-use value — if the same change were needed again, you would write a new script with fresh context. The durable outputs are: the live system state, CLAUDE.md, and the promoted documentation.

---

### apply_rsyslog_filter.sh / 10-drop-acpi-ec.conf
- **Sizes:** 677 B / 196 B | **Modified:** 2026-06-14
- **Purpose:** Deployed rsyslog filter to drop ACPI EC spam.
- **Recommendation: Delete**
- **Justification:** Applied; /etc/rsyslog.d/10-drop-acpi-ec.conf is live. The live file is canonical. The conf content (3 lines) is not worth preserving separately.

---

### waydroid.prop.new / waydroid.cfg.new / waydroid.cfg.fixed
- **Sizes:** 807 B / 634 B / 593 B | **Modified:** 2026-06-14
- **Purpose:** Staging files for waydroid configuration changes applied during the Jun 14 session.
- **Recommendation: Delete**
- **Justification:** All applied. The waydroid crash diagnosis document (being promoted to `doc/`) is the reference for what was changed and why. These are implementation artifacts, not documentation.

---

### brave_investigation.sh / migrate_brave_to_apt.sh / migrate_brave_to_apt.log
- **Sizes:** 1.9 KB / 1.3 KB / 556 B | **Modified:** 2026-06-12
- **Purpose:** Diagnosed Brave browser state and migrated from Flatpak to APT. Log confirms Brave 149.1.91.171 installed via APT.
- **Recommendation: Delete**
- **Justification:** Migration complete. Brave is now APT-managed. The log is a receipt, not a reference.

---

### collect_audit.sh
- **Size:** 4.3 KB | **Modified:** 2026-06-11
- **Purpose:** System diagnostic collector script; generated audit_data.txt.
- **Recommendation: Delete**
- **Justification:** Diagnostic from the investigation phase. Root cause identified and fixed. The script has no ongoing diagnostic role — future sessions would write their own.

---

### tcc_settings_staged.json
- **Size:** 9.1 KB | **Modified:** 2026-06-12
- **Purpose:** Staging copy of TCC settings used by switch_profile.sh when /etc/tcc/settings is not directly writable.
- **Recommendation: Delete**
- **Justification:** tcc_settings_new.json (being promoted to `config/`) has the same content. Duplicate.

---

### grub.tmp
- **Size:** 475 B | **Modified:** 2026-06-14
- **Purpose:** Temporary GRUB config file staged for apply_aspm_fix.sh.
- **Recommendation: Delete**
- **Justification:** Applied. Nothing here not in /etc/default/grub.

---

### options_cfg_backup_20260612.cfg
- **Size:** 4.1 KB | **Modified:** 2026-06-12
- **Purpose:** Backup of PySol options config taken before the session that changed display settings.
- **Recommendation: Delete**
- **Justification:** PySol manages its own config; this is a pre-session snapshot from a completed task. Not a system config, not high-value.

---

### screenshot.jpeg
- **Size:** 62 KB | **Modified:** 2026-06-13
- **Purpose:** Unidentified screenshot; date suggests it was taken during the Jun 13 freeze/nvidia investigation.
- **Recommendation: Delete**
- **Justification:** No caption, no context, no label. Cannot determine what it shows or why it was taken. If it captured something important, that information was already acted on in the diagnosis.

---

### patch_settings.sh / patch_settings.py / uhet_settings_restored.json / uhet_claude_md_new.md
- **Sizes:** 368 B / 1.1 KB / 5.6 KB / 1.6 KB | **Modified:** 2026-06-15
- **Purpose:** Scripts and staging files for manually patching uhet's settings.json and CLAUDE.md before chezmoi existed.
- **Recommendation: Delete**
- **Justification:** Chezmoi now manages settings.json.tmpl and CLAUDE.md as the canonical source. These manual-patching artifacts are superseded. The content they contain is now in the chezmoi source repo.

---

### modprobe_nvidia_backup/ (4 files)
- **Sizes:** 41–313 B | **Modified:** 2026-06-13
- **Purpose:** Pre-fix backups of /etc/modprobe.d/nvidia*.conf files taken by fix_nvidia_dynpm.sh.
- **Recommendation: Delete**
- **Justification:** Fix applied, confirmed stable, CLAUDE.md documents the current state. Backups from the 0x02 → 0x01 transition have no recovery value — you would not want to revert to the state that caused hard freezes.

---

### memory/ (4 files: MEMORY.md, 3 feedback docs)
- **Sizes:** 401 B / 1.0 KB / 752 B / 844 B | **Modified:** 2026-06-15
- **Purpose:** Local copies of the CC memory system files for this project.
- **Recommendation: Delete**
- **Justification:** These are copies or mirrors generated during a session. The canonical memory files live at `~/.claude/projects/.../memory/` and are tracked by chezmoi. This scratch copy is a snapshot that will diverge from the live version on the next session that updates memory.

---

### skill-diffs/ (21 files) / skill-diff-report.md / learnings-merge-plan.md
- **Sizes:** 97 B – 27 KB / 20 KB / 15 KB | **Modified:** 2026-06-16
- **Purpose:** Working files from the `/reflect` skill-sync workflow on Jun 16.
- **Recommendation: Delete**
- **Justification:** Generated diffs have been reviewed; PR #3 was opened and merged. The chezmoi source repo now holds the canonical skill files. These diffs and reports are spent.

---

### claude-skill-dir-check.md
- **Size:** 3.4 KB | **Modified:** 2026-06-16
- **Purpose:** Research document establishing that CLAUDE_SKILL_DIR is set at skill execution time, confirming version compatibility.
- **Recommendation: Delete**
- **Justification:** Answered question, one-time research. Finding acted on. Not reference material for future sessions.

---

### research-dotfiles-tools.md / research-claude-dir-anatomy.md / research-cc-community-sync.md / research-sysadmin-repo.md / research-home-dotfiles.md / research-chezmoi-migration.md / cc-config-sync-options.md
- **Sizes:** 4.5 KB – 18 KB | **Modified:** 2026-06-16
- **Purpose:** Background research reports and intermediate options documents generated as inputs to the chezmoi migration decision.
- **Recommendation: Delete**
- **Justification:** Raw research inputs, not outputs. The synthesis lives in chezmoi-migration-report.md (being promoted to `doc/`). Retaining both input and output creates redundancy; the inputs are harder to read. Delete the inputs, promote the synthesis.

---

### chezmoi-discovery.md
- **Size:** 7.6 KB | **Modified:** 2026-06-16
- **Purpose:** Pre-migration discovery pass confirming chezmoi not installed, no dotfiles repo yet, home root dotfile inventory.
- **Recommendation: Delete**
- **Justification:** Point-in-time discovery from before the setup was done. Everything it confirmed ("no dotfiles repo") is now false. Not useful going forward.

---

### chezmoi.diff
- **Size:** 38 KB | **Modified:** 2026-06-16
- **Purpose:** Output of `chezmoi diff` taken during setup to verify what apply would change.
- **Recommendation: Delete**
- **Justification:** A snapshot of the diff at setup time. Not reference material. `chezmoi diff` can be re-run at any time to see current state.

---

### settings-rendered-test.json
- **Size:** 4.8 KB | **Modified:** 2026-06-16
- **Purpose:** Test render of settings.json.tmpl to verify the Go template output.
- **Recommendation: Delete**
- **Justification:** Verification artifact. chezmoi manages the canonical template. This snapshot is stale the moment settings.json.tmpl is next edited.

---

## Proposed Directory Structure

```
system_queries/
├── CLAUDE.md
├── SKIKK_Support_Dossier.md
├── SKIKK_Thor_ASPM_Bug_Report.md
├── dsdt.dat                              (existing — current DSDT binary)
├── dsdt.dsl                              (existing — current DSDT decompiled)
│
├── acpi/                                 (NEW — ACPI/firmware artifacts)
│   ├── nvpcf_fix.asl                     ← .scratch/nvpcf_fix.asl
│   ├── dsdt_bios_20251212.dat            ← .scratch/dsdt_bios_20251212.dat
│   └── dsdt_bios_20251212.dsl            ← .scratch/dsdt_bios_20251212.dsl
│
├── config/                               (NEW — live service configs)
│   ├── tcc-profiles.json                 ← .scratch/tcc_profiles_new.json
│   └── tcc-settings.json                 ← .scratch/tcc_settings_new.json
│
├── doc/                                  (NEW — human-readable records)
│   ├── nvidia-dynamic-boost-storm-root-cause.md
│   ├── session-handover-20260614-health-waydroid.md
│   ├── system-state-20260615-post-reboot.md
│   ├── waydroid-hwcomposer-crash-diagnosis.md
│   ├── chezmoi-migration-decision.md
│   ├── chezmoi-setup-explainer.md
│   └── chezmoi-setup-log.md
│
└── scripts/                              (NEW — reusable maintenance scripts)
    └── switch_tcc_profile.sh             ← .scratch/switch_profile.sh
```

## .scratch/ After Promotion (nothing retained)

All files currently marked "Keep in .scratch/" are being promoted to `acpi/` or `scripts/`. After the moves and deletes, `.scratch/` holds only new working files from future sessions.
