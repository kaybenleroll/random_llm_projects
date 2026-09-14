# s3rbase — Sysadmin History

_Last updated: 2026-09-14._

---

## 1. Chronological Decision Log

### 1.1 — Codex CLI sandbox broken by AppArmor unprivileged-userns restriction; fixed with Ubuntu's bwrap-userns-restrict profile (2026-09-14)

**Symptom.** Codex CLI (`~/.codex`, installed via chezmoi-tracked mise config as `npm:@openai/codex`) printed on startup: "Codex's Linux sandbox uses bubblewrap and needs access to create user namespaces." `codex doctor` still reported the sandbox as functioning (approval OnRequest, restricted fs/network), but the underlying bwrap call was failing.

**Root cause.** Ubuntu 24.04 ("noble", confirmed via `codex doctor`'s OS field) sets `kernel.apparmor_restrict_unprivileged_userns=1` by default. This blocks any unconfined process — including `bwrap` (bubblewrap, which Codex uses for its Linux sandbox) — from creating unprivileged user namespaces unless an AppArmor profile explicitly grants it. No such profile existed on s3rbase (`/etc/apparmor.d/*bwrap*` was empty). Reproduced directly: `bwrap --unshare-user --die-with-parent /bin/true` → `bwrap: setting up uid map: Permission denied`.

**First fix attempt (superseded, see below).** Hand-wrote a minimal profile granting `bwrap` the `userns` capability with `flags=(unconfined)`:
```
abi <abi/4.0>,
include <tunables/global>

profile bwrap /usr/bin/bwrap flags=(unconfined) {
  userns,
}
```
This worked (verified `bwrap --unshare-user --ro-bind / / /bin/true` succeeded) but was flagged as too broad on review: `flags=(unconfined)` grants unprivileged-userns creation to *any* invocation of `/usr/bin/bwrap` on the box, with no restriction on what a sandboxed child process can then do. s3rbase has multiple accounts including a `github-runner` account (CI) — the blanket grant reopens the exact kernel attack surface the sysctl hardening exists to close, for every account on a shared machine, not just for Codex.

**Fix applied (current).** Installed Ubuntu's own vetted profile instead of the hand-written one:
```
sudo apt-get install -y apparmor-profiles
sudo rm -f /etc/apparmor.d/bwrap                                              # remove the superseded hand-written profile
sudo install -m 0644 /usr/share/apparmor/extra-profiles/bwrap-userns-restrict /etc/apparmor.d/bwrap-userns-restrict
sudo apparmor_parser -R /etc/apparmor.d/bwrap 2>/dev/null || true
sudo apparmor_parser -r /etc/apparmor.d/bwrap-userns-restrict
```
`bwrap-userns-restrict` ships in the `apparmor-profiles` package (`/usr/share/apparmor/extra-profiles/`, disabled by default) and uses a two-profile design: it grants `bwrap` itself the `userns` capability for setup, then stacks any process it executes into a capability-stripped child profile — so the sandbox escape surface is not reopened for arbitrary code, only for bwrap's own namespace-setup step. Same shape as the `unprivileged_userns` profile already present on the box. Verified: `bwrap --unshare-user --ro-bind / / /bin/true` succeeds; `codex doctor`'s sandbox warning is gone; `kernel.apparmor_restrict_unprivileged_userns` sysctl left untouched at `1` for every other unconfined process.

**Known gap.** This profile (`/etc/apparmor.d/bwrap-userns-restrict`) is a manual, un-tracked root-owned `/etc` file — not managed by chezmoi (deliberately: chezmoi's contract here is user-owned dotfiles applied without privilege; pulling in `/etc` files would mean privileged `run_` scripts executing on every chezmoi-managed machine, including ones where they're irrelevant, to protect against a reprovision of one host that — per direct check — has no reprovisioning pipeline anyway, since s3rbase is bare metal with no Ansible/Puppet/Chef/Salt). If s3rbase is ever reinstalled, this fix needs to be reapplied manually from this entry.

**Not yet done.** s3rbase is not solely the user's machine (multiple accounts present, including `github-runner`). The change lowers a system hardening default (in a scoped way) for every account on the box — whoever owns/administers s3rbase should be told this was done. See draft note below.

---

### Draft note to s3rbase's owner/admin

> Heads up — I installed Ubuntu's `apparmor-profiles` package on s3rbase and enabled the `bwrap-userns-restrict` profile (`/etc/apparmor.d/bwrap-userns-restrict`, loaded via `apparmor_parser -r`). This was needed to get Codex CLI's bubblewrap-based sandbox working — Ubuntu 24.04's `kernel.apparmor_restrict_unprivileged_userns=1` default was blocking it entirely.
>
> This is Ubuntu's own vetted profile (ships disabled by default in `apparmor-profiles`), not a custom one — it grants `bwrap` the ability to create unprivileged user namespaces for its own sandbox setup, then confines anything it executes to a capability-stripped child profile. The system-wide sysctl restriction is untouched for every other process on the box.
>
> Flagging it because it does relax a hardening default (scoped to `bwrap` specifically) on a shared machine — let me know if you'd rather this be reverted or handled differently.
