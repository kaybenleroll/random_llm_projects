#!/usr/bin/env python3
"""
SessionStart hook: inject this machine's context from doc/machines/<slug>.md.

Resolves the current hostname to a slug via doc/machines/registry.json (an
explicit alias registry, not auto-detection — see doc/machines/README.md for
why). Unknown hostnames, registry errors, or missing files emit a loud warning
in additionalContext instead of silently loading nothing. Always exits 0 —
SessionStart's exit code 2 sends stderr to the user only and never reaches the
model, which would turn this into a silent failure.
"""

import json
import os
import socket
import sys
from pathlib import Path

MACHINES_DIR = Path(__file__).resolve().parent.parent.parent / "doc" / "machines"
REGISTRY_PATH = MACHINES_DIR / "registry.json"


def detected_hostname():
    override = os.environ.get("MACHINE_SLUG_OVERRIDE")
    if override:
        return override
    return socket.gethostname()


def normalise(name):
    return name.split(".")[0].lower()


def resolve_slug(hostname):
    """Returns (slug_or_None, error_message_or_None)."""
    if not REGISTRY_PATH.exists():
        return None, f"registry file not found at {REGISTRY_PATH}"

    try:
        registry = json.loads(REGISTRY_PATH.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return None, f"registry file unreadable/malformed: {e}"

    if not registry:
        return None, "registry file is empty"

    seen = {}
    for slug, aliases in registry.items():
        if not aliases:
            return None, f"slug '{slug}' has an empty alias list"
        for alias in aliases:
            alias_norm = alias.lower()
            if alias_norm in seen and seen[alias_norm] != slug:
                return None, (
                    f"alias '{alias}' is registered under both "
                    f"'{seen[alias_norm]}' and '{slug}' — fix registry.json"
                )
            seen[alias_norm] = slug

    target = normalise(hostname)
    for slug, aliases in registry.items():
        if target in (a.lower() for a in aliases):
            return slug, None

    known = ", ".join(sorted(registry.keys()))
    return None, f"hostname '{hostname}' (normalised '{target}') has no registry entry. Known slugs: {known}"


def unknown_machine_warning(hostname, reason):
    known_files = sorted(p.stem for p in MACHINES_DIR.glob("*.md")) if MACHINES_DIR.exists() else []
    return (
        "## UNKNOWN MACHINE — machine context could not be loaded\n\n"
        f"Detected hostname: `{hostname}`\n"
        f"Reason: {reason}\n\n"
        f"Known machine files: {', '.join(known_files) or '(none found)'}\n\n"
        "Do NOT apply, assert, or assume any fix, quirk, or hardware claim from "
        "any of those files on this session — none of them are confirmed to "
        "match this machine. Fix doc/machines/registry.json (or add a new "
        "machine file) before making machine-specific claims."
    )


def main():
    try:
        sys.stdin.read()
    except Exception:
        pass

    hostname = detected_hostname()
    slug, error = resolve_slug(hostname)

    if slug is None:
        context = unknown_machine_warning(hostname, error)
    else:
        machine_file = MACHINES_DIR / f"{slug}.md"
        try:
            context = machine_file.read_text()
        except OSError as e:
            context = unknown_machine_warning(hostname, f"resolved to slug '{slug}' but {machine_file} unreadable: {e}")

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
