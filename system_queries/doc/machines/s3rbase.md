<!-- machine-context: s3rbase -->

# s3rbase — remote server admin context

**Ownership: client-owned, not the user's own infrastructure.** SSH access and
technical control do not make it appropriate to run the user's personal
projects/infrastructure here (2026-08-06 correction, after recommending SSH on
s3rbase for centralised transcript search without checking ownership first) —
verify scope with the user before proposing anything beyond the admin/diagnostic
work this repo already does here.

Otherwise a stub. Nothing surveyed yet — hostname is a best-guess alias in
`registry.json` (unverified; see the plan's Prerequisite 1). Populate this file,
and update `registry.json`'s alias list if the real hostname differs, the first
time this machine is administered from this repo.

## Active fixes

| Date | Fix | Detail |
|------|-----|--------|
| 2026-09-14 | `bwrap-userns-restrict` AppArmor profile installed (Ubuntu's own, from `apparmor-profiles` package) — unblocks Codex CLI's bubblewrap sandbox under 24.04's `kernel.apparmor_restrict_unprivileged_userns=1` default, without a blanket `unconfined` grant | `doc/s3rbase-history.md` §1.1 |

## Known quirks

- Multiple accounts present on this box (`mcooney`, `docd`, `roy`, `github-runner` at least) — treat any system-wide config change (sandboxing, hardening defaults, etc.) as affecting other users/CI, not just personal tooling.
- Bare metal, no reprovisioning pipeline (no Ansible/Puppet/Chef/Salt detected) — manual root-owned `/etc` changes are not chezmoi-tracked and won't survive a reinstall; see each fix's own doc entry for reapply steps.
