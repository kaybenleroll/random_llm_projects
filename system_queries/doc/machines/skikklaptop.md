<!-- machine-context: skikklaptop -->

# skikklaptop — Windows laptop + WSL2 admin context

Hardware/OS/driver identity (chassis, CPU, GPU, kernel, driver versions) lives in
`~/.claude/MACHINE.md`, not here — see `doc/machines/README.md`'s
division-of-labour rule. This file owns what has been done to the machine: active
fixes, hard constraints, quirks, revert steps.

## Hard constraints
- **WSL networking is mirrored, not NAT** — `.wslconfig` sets `networkingMode=mirrored`, so WSL binds the Windows host's LAN IP directly (no port-forwarding rules needed). Requires `wsl --shutdown` + relaunch to pick up `.wslconfig` changes.
- **`wsl.conf` runs systemd (`systemd=true`)** — `/run/user/1000` and user lingering are available, but there's no active systemd *user session* by default (`loginctl enable-linger 1000` not yet run), so Podman's cgroupv2/systemd cgroup manager still falls back to `cgroupfs` (see quirk below) even though the raw `systemd=false` blocker from earlier is gone.
- **Container tooling is native Docker Engine, not Docker Desktop** — verified 2026-08-12: `dockerd` runs as a systemd-managed service (`systemctl is-active docker`), `docker context` is `default` → `unix:///var/run/docker.sock`, no `/mnt/wsl/docker-desktop/*` sockets exist. Docker Desktop is still installed on Windows but is no longer the integration path from this distro — this superseded an earlier Docker-Desktop-based setup (see history below). GPU passthrough re-verified working under native Engine (`docker run --gpus all ... nvidia-smi` shows the RTX 3060).

## Active fixes
| Fix | File | Status |
|-----|------|--------|
| SSH server enabled (mirrored networking, port 22) | `openssh-server` + Windows firewall rule on port 22 | Live |
| Migrated from Docker Desktop WSL integration to native Docker Engine | `dockerd` systemd service | Live |
| nvidia-container-toolkit installed for GPU passthrough in containers | WSL distro package install | Live |

**SSH access (confirmed 2026-08-06):** `openssh-server` active and enabled (`systemctl is-active`/`is-enabled` both confirm). Mirrored networking means SSH reaches WSL directly on the host's LAN IP, port 22 — no Windows-side port-forward rule needed, only the firewall rule.

**Docker Desktop → native Docker Engine migration (confirmed 2026-08-12):** this machine ran Docker Desktop + WSL integration through at least 2026-07-26 (GPU passthrough confirmed working that way then). Since then it moved to native `dockerd` running directly in WSL as a systemd service — `docker context ls` still lists a `desktop-linux` context but it's not current, and no Desktop shared-socket mount exists. **Docker Desktop and native Engine have separate storage backends and cannot share volumes** — a volume created under one is invisible to the other; treat container-based data (e.g. downloaded model files) as cheap to re-fetch into a fresh volume on the target daemon rather than attempting manual volume migration. GPU passthrough re-verified working under native Engine (`docker run --gpus all nvidia/cuda:... nvidia-smi` shows the RTX 3060, nvidia-container-toolkit registers a working `nvidia` runtime).

## Known platform quirks
- `$WSL_DISTRO_NAME` env var stays empty regardless of container-runtime setup — don't use it as a health signal for Docker; check `docker info`/`docker run` directly instead.
- 6GB VRAM (RTX 3060 Laptop) is a real ceiling for local LLM work: ~7B models comfortably at Q4 GGUF, ~13B possible at aggressive quantization with partial CPU offload, nothing 30B+ without heavy offload.
- Chezmoi manages dotfiles from `kaybenleroll/dotfiles`; `.claude/CLAUDE.md`/`MACHINE.md` render this machine's section conditionally via `.chezmoi.kernel.osrelease | lower | contains "microsoft"` (CLAUDE.md) or the `skikklaptop` hostname branch (MACHINE.md).
- Rootless Podman is installed but degraded, not fully non-functional: `podman info` warns the cgroupv2 manager is set to `systemd` but no systemd user session is available, and falls back to `--cgroup-manager=cgroupfs`. Untested whether `loginctl enable-linger 1000` resolves this now that `systemd=true` — don't assume Podman is unusable without re-testing after that step.
- WSL mirrored networking not needing port-forward rules does **not** mean stale Windows-side `netsh interface portproxy` rules are gone — those persist in the Windows registry via IP Helper independent of WSL's networking mode. If WSL reports a port conflict but internal `ss`/`lsof` show no listener, check the Windows side first (`netsh interface portproxy show all`, IP Helper service) and clean up stale rules when reconfiguring forwarding.

No `doc/skikklaptop-history.md` yet — add one if narrative detail accumulates beyond what fits here.
