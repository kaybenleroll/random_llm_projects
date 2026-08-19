# Moved

This tool has moved to its own standalone repository, with git history
preserved:

https://github.com/kaybenleroll/claude-transcript-sanitizer

The files in this directory are left in place for now (not yet deleted) —
that's a separate decision pending confirmation that the new repo is
working out.

Note: at the time of extraction, this directory had uncommitted local
changes (`.gitleaks.toml`, `bin/recognizer-gate.sh`, and modifications to
`bin/gitleaks-baseline.sh`, `sanitize/classify.py`,
`sanitize/recognizers.py`, `tests/test_classify.py`,
`tests/test_recognizers.py`) that were not part of this repo's git history
and so could not be carried over by `git filter-repo`. That working-tree
state was copied into the new repo's first scaffolding commit instead. If
you intend to keep working in *this* directory rather than the new repo,
be aware the new repo is currently ahead by that uncommitted work.
