# Codex transcript retention

The Codex installation keeps native session records under
`~/.codex/sessions/` as JSONL rollout files. The CLI can recover them with
`codex resume --all` or `codex resume <session-id>`.

To protect against future native cleanup, this machine mirrors those files to:

```text
~/.local/share/codex/session-archive/
```

The `codex-session-archive.timer` user timer runs every 15 minutes and after
boot. It deliberately does not use `rsync --delete` and has no age-based
pruning. The archive is mode `0700`, is not managed by chezmoi, and is not
cloud-synchronised or committed to Git because transcripts may contain
commands, file contents, and other sensitive material.

The mirror protects against deletion from the live Codex directory. It is not a
versioned backup of a file that is modified in place while a session is active;
the next timer run updates that copy. For recovery after native files disappear,
restore the archive before using `codex resume`:

```sh
rsync -a ~/.local/share/codex/session-archive/sessions/ ~/.codex/sessions/
rsync -a ~/.local/share/codex/session-archive/session_index.jsonl ~/.codex/ 2>/dev/null || true
rsync -a ~/.local/share/codex/session-archive/history.jsonl ~/.codex/ 2>/dev/null || true
codex resume --all
```

The service and timer definitions are chezmoi-managed; the transcript archive
itself is intentionally local state.
