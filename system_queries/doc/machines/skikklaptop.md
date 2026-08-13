<!-- machine-context: skikklaptop -->

# skikklaptop — Windows laptop + WSL2 admin context

**Ownership: the user's own machine** (personal Windows laptop). Available for
personal infrastructure/experimentation without the client-ownership caveat that
applies to `s3rbase`.

Hardware/OS/driver identity (chassis, CPU, GPU, kernel, driver versions) lives in
`~/.claude/MACHINE.md`, not here — see `doc/machines/README.md`'s
division-of-labour rule. This file owns what has been done to the machine: active
fixes, hard constraints, quirks, revert steps.

## Hard constraints
- **WSL networking is mirrored, not NAT** — `.wslconfig` sets `networkingMode=mirrored`, so WSL binds the Windows host's LAN IP directly (no port-forwarding rules needed). Requires `wsl --shutdown` + relaunch to pick up `.wslconfig` changes.
- **`wsl.conf` runs systemd (`systemd=true`)** — see the Podman quirk below for what this does and doesn't unblock.

## Active fixes
| Fix | File | Status |
|-----|------|--------|
| SSH server enabled (mirrored networking, port 22) | `openssh-server` + Windows firewall rule on port 22 | Live |
| Migrated from Docker Desktop WSL integration to native Docker Engine | `dockerd` systemd service | Live |

**SSH access (confirmed 2026-08-06):** `openssh-server` active and enabled (`systemctl is-active`/`is-enabled` both confirm). Mirrored networking means SSH reaches WSL directly on the host's LAN IP, port 22 — no Windows-side port-forward rule needed, only the firewall rule.

**Docker Desktop → native Docker Engine migration (confirmed 2026-08-12):** this machine ran Docker Desktop + WSL integration through at least 2026-07-26. Since then it moved to native `dockerd` running directly in WSL as a systemd service (current runtime identity lives in `~/.claude/MACHINE.md`, not here — this entry is about the *migration itself* as a thing that was done). `docker context ls` still lists a `desktop-linux` context but it's not current. **Docker Desktop and native Engine have separate storage backends and cannot share volumes** — a volume created under one is invisible to the other; treat container-based data (e.g. downloaded model files) as cheap to re-fetch into a fresh volume on the target daemon rather than attempting manual volume migration. GPU passthrough re-verified working post-migration.

## Known platform quirks
- `$WSL_DISTRO_NAME` env var stays empty regardless of container-runtime setup — don't use it as a health signal for Docker; check `docker info`/`docker run` directly instead.
- 6GB VRAM (RTX 3060 Laptop) is a real ceiling for local LLM work: ~7B models comfortably at Q4 GGUF, ~13B possible at aggressive quantization with partial CPU offload, nothing 30B+ without heavy offload.
- Chezmoi manages dotfiles from `kaybenleroll/dotfiles`; `.claude/CLAUDE.md`/`MACHINE.md` render this machine's section conditionally via `.chezmoi.kernel.osrelease | lower | contains "microsoft"` (CLAUDE.md) or the `skikklaptop` hostname branch (MACHINE.md).
- Rootless Podman is installed but degraded, not fully non-functional: `podman info` warns the cgroupv2 manager is set to `systemd` but no systemd user session is available, and falls back to `--cgroup-manager=cgroupfs`. Confirmed 2026-08-12: this is *not* a missing-linger or missing-package problem — `loginctl show-user 1000 -p Linger` → `Linger=yes`, `systemctl --user is-system-running` → `running`, and `systemctl --user status dbus.socket` shows it `active (listening)` on `/run/user/1000/bus` — but that path doesn't actually exist on disk (`stat` fails). The socket unit is listening on a path that's been removed underneath it. Next probe, untried: `systemctl --user restart dbus.socket`. Root cause of the disappearing socket file itself is undiagnosed.
- WSL mirrored networking not needing port-forward rules does **not** mean stale Windows-side `netsh interface portproxy` rules are gone — those persist in the Windows registry via IP Helper independent of WSL's networking mode. If WSL reports a port conflict but internal `ss`/`lsof` show no listener, check the Windows side first (`netsh interface portproxy show all`, IP Helper service) and clean up stale rules when reconfiguring forwarding.
- Scripts calling `wsl --shutdown` kill the invoking WSL session immediately — such scripts must run from native Windows CLI (PowerShell/cmd) **and** be stored on the native Windows filesystem (see `system_queries/CLAUDE.md`'s `.scratch/` exception), not over a `\\wsl.localhost\` mount or from within WSL itself; `wsl --shutdown` unmounts those shares as part of the same shutdown.
- `wsl.exe -u root <cmd>` run from PowerShell writes guest root-owned files (e.g. `/etc/wsl.conf`) without any sudo password prompt in a WSL shell — WSL's host-trust model lets the Windows host act as root over the guest unauthenticated. The corollary: guest-side root-only file permissions are not a security boundary against anything running as the Windows user.
- PowerShell 5.1 (Windows' default) reads BOM-less script files as the legacy ANSI codepage, not UTF-8 — a non-ASCII byte (e.g. an em dash) can either mangle into garbled output or, depending on which character lands where, cause an outright parse error (a smart dash/quote landing where PowerShell expects a real hyphen/quote token). Don't assume "it ran without a parse error" rules out the encoding issue if the output looks garbled. Fix: keep PowerShell scripts ASCII-only, or save the file as UTF-8 with a BOM.

No `doc/skikklaptop-history.md` yet — add one if narrative detail accumulates beyond what fits here.
