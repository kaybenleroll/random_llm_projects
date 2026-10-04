---
paths:
  - "**/Justfile"
  - "**/justfile"
---

# Justfile rules

- In Justfiles, backtick expressions (e.g. `` `cd .. && pwd` ``) spawn subshells that CC's security sandbox blocks — use `$(dirname $(realpath .))` or hardcoded paths instead.
- In Justfiles, recipe lines run under `sh -cu` (dash on Ubuntu) regardless of invocation context — dash's `echo` doesn't support `-e` (it prints a literal `-e ` prefix instead of interpreting escapes); use `printf` instead.
