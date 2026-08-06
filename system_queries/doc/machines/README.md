# Machine context files

One file per machine this repo is administered from. A `SessionStart` hook
(`.claude/hooks/load-machine-context.py`) detects the current hostname, resolves it
to a slug via `registry.json`, and injects the matching file's contents into every
session started in `system_queries/`. Unknown hostnames get a loud warning instead
of silently answering from the wrong machine's file — never assume any of these
files applies to the current session without checking the injected sentinel.

## Index

| Slug | Machine | Status |
|---|---|---|
| `skikk-thor` | Native Ubuntu 26.04, SKIKK Thor 16 (Tongfang GM6HG7Y) | Populated |
| `skikklaptop` | Windows laptop + WSL2 (this machine's project context) | Near-empty, backfill as issues are found |
| `s3rbase` | Remote server | Stub |

Hostnames are **not** auto-derived — `registry.json` is an explicit alias registry,
because this repo already documented hostname auto-detection as unreliable (see
`.claude/rules/skill-hygiene.md`'s `.chezmoi.hostname` corruption bullet). Adding a
machine, or absorbing a rename, is a `registry.json` edit plus a new file here.

## Division of labour with `~/.claude/MACHINE.md`

**Intended end state** (Scope C, not yet landed): `~/.claude/MACHINE.md` (global,
loaded in every project on every machine) owns **what the box is** — chassis, CPU,
GPU, RAM, OS, kernel, driver versions, shell, container runtime. Files in this
directory own **what has been done to it** — active fixes, quirks, hard
constraints, revert steps, specific to `system_queries/` sysadmin work.

Today, `~/.claude/MACHINE.md` does not exist, is not chezmoi-managed, and is
imported nowhere — so it is not actually loaded anywhere yet. As a bridge until
Scope C lands, `skikk-thor.md` temporarily carries Thor's hardware identity lines
itself, marked explicitly as temporary. **Do not restate hardware/OS/driver facts
in a machine file here otherwise** — once Scope C lands, reference
`~/.claude/MACHINE.md` instead. Both files are hand-curated, so this boundary is a
convention to check against, not something enforced structurally.

`doc/skikk-thor-history.md` is Thor-specific narrative decision-log detail, referenced
by `§2.N` pointers from `skikk-thor.md`. It stays where it is — read on demand, never
auto-loaded. Future machines get their own `doc/<slug>-history.md` if warranted.
