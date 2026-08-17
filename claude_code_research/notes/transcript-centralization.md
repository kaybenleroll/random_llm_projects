# Claude Code Transcript Centralization

Research into giving cross-machine access/search over Claude Code session transcripts, which are currently machine-local and subject to auto-deletion.

## Problem Statement

Claude Code session transcripts live at `~/.claude/projects/<slug>/*.jsonl`, per machine. Multi-machine development works fine under plain git (checkout + run), but under Claude Code it's uncomfortable: switching machines loses the ability to look back at prior session history ("what was I doing two weeks ago"). Compounding this, Claude Code deletes local transcripts after a retention window (`cleanupPeriodDays`, 30-day default), so history is lost even on a single machine over time. Chezmoi/git-as-dotfile-sync was ruled out early — append-only JSONL logs would bloat repo history permanently.

## Timeline

- **2026-08-06** — Initial brain dump (`braindump-20260806-claude-code-workflow.md`) raised cross-machine transcript access as one of four Claude Code workflow pain points (alongside stress-test token burn, skill bloat, and Opus/Fable model choice).
- **2026-08-06** — Status update (`status-20260806-claude-code-workflow.md`) worked through four sync/hosting options in sequence, each superseded by a new constraint:
  1. Syncthing (peer-to-peer) — superseded when the ask shifted to a centralized hub model.
  2. Self-hosted hub on `s3rbase` — ruled out: s3rbase is a client's machine, not personal infrastructure.
  3. Dedicated GCP e2-micro VM — considered to recover SSH+ripgrep search without using a client machine; pricing verified as ~$1.50/month (disk only, compute free-tier) vs AWS's ~$6-8/month.
  4. **Google Drive + rclone sync** — landed as the "final recommendation, at least to start with," since the user already has paid storage on Google Drive and OneDrive and it adds zero marginal cost. **Not implemented** — parked as next-session work.
- **2026-08-14** — Full research report (`transcript-centralization-report-20260814.md`) superseded the Google Drive plan after a same-day false start (an oversized dedicated-VM redesign that failed a sniff-test). Five parallel research angles were run, converging on a lighter-weight recommendation than any prior pass.

This is documented in the 2026-08-14 report as the third time this need surfaced without resolution.

## Corpus Findings

- **SkikkLaptop**: 57MB, corpus growing slowly (28MB/185 files measured 2026-08-06; 57MB by 2026-08-14).
- **skikk-thor**: 1.5GB.
- Combined corpus (both machines, retained indefinitely): estimated 150–300MB/year going forward — not large enough to justify dedicated infrastructure. The rejected VM+disk proposal had assumed a storage premise wrong by 2+ orders of magnitude versus this measured figure.
- **Retention window verification**: `cleanupPeriodDays` was unset (30-day default) on SkikkLaptop, consistent with its oldest surviving transcript (~30 days old). skikk-thor's oldest surviving transcript was ~47 days old, initially inconsistent with a 30-day default — resolved when two independent unpushed commits were found on skikk-thor's chezmoi source that had already changed `cleanupPeriodDays` to 365. Both machines are now confirmed at `cleanupPeriodDays: 365`.
- **Noise ratio** (measured on a real 2.5MB transcript, by content-block byte share): `text` (actual conversation) 11.5%, `tool_use` (tool call args) 27%, `tool_result` (file/command output) 61.5%. Real conversational content is roughly ~3% of raw file bytes once JSONL metadata is included — plain `grep`/`ripgrep` over raw transcripts is a genuinely poor search experience, and this worsens as the corpus grows since tool-output volume scales with work done, not decisions made.

## Approaches Surveyed

The 2026-08-14 report ran five parallel research angles:

1. **Sync/replication transport** (Syncthing, rsync, git, Resilio, Unison, rclone bisync, restic/borg) — Syncthing is the best fit if hand-rolling transport (atomic writes, no dedicated host, good mid-write safety); rsync lacks atomicity; rclone bisync flagged as less battle-tested by rclone's own maintainers.
2. **Cloud object storage** (Cloudflare R2, Backblaze B2, AWS S3, GCS, Google Drive+rclone) — Cloudflare R2 wins on cost (free indefinitely at this scale, zero egress fees), but no provider offers server-side search, so this choice is fully decoupled from the search-quality problem.
3. **Git repository as archive** — sound at this scale with two required fixes: a quiescence rule (only commit files with mtime >10 min old, never `git add -A`) and host namespacing (CC's project-directory names derive from absolute working-directory path, so identical paths on two machines collide). GitHub's ~1GB soft-warning line is not yet hit by the combined corpus. Do not use Git LFS.
4. **Existing ready-made tools** (strongest finding) — `claude-code-sync` (git-based sync CLI) and `claude-history` (local search CLI) purpose-built for exactly this problem; see Recommendation below.
5. **Search quality** — independent of transport/storage choice; raw JSONL search is poor (per noise ratio above) regardless of where files live. `jq`-based extraction of `text`/`tool_use` cuts ~97% of noise; SQLite FTS5 on top of that is the recommended real solution if built custom.

### Earlier options considered (2026-08-06)

Before the 2026-08-14 report, an earlier pass had landed on Google Drive +
rclone as a stopgap, evaluating options later superseded above but not
otherwise recorded here:

- **GCP e2-micro VM** (rejected as oversized once corpus size was measured):
  Always-Free-tier eligible indefinitely (vs. AWS's 12-month-only trial), with
  IAP TCP forwarding giving SSH access with no public IP needed. Priced at
  ~$1.50/month (disk only, compute free). Caveat: the pricing was sourced
  partly from a low-quality SEO site (`agentdeals.dev`) and needs
  re-verification against `cloud.google.com/free` before acting on it.
- **`rclone mount` vs `rclone sync`**: live-mounting and grepping over the
  mount was considered and rejected — each file open is a network round-trip,
  too slow for full-corpus search. `rclone sync` (pull changes locally, then
  grep locally) was the workaround used instead.
- **Google Drive preferred over OneDrive**: OneDrive's rclone integration,
  especially for personal (non-business) accounts, has more known quirks
  around sync tokens/API changes than Google Drive's.

## Final Recommendation

1. **Try `claude-code-sync` + `claude-history` first**, pointed at a private git remote:
   - [`perfectra1n/claude-code-sync`](https://github.com/perfectra1n/claude-code-sync) — Rust CLI, git-based sync of exactly `~/.claude/projects/**/*.jsonl` across machines, 85 stars, actively maintained, conflict resolution, credential-file security denylist.
   - [`raine/claude-history`](https://github.com/raine/claude-history) — Rust CLI, most mature/starred tool found in the research pass (446 stars), fuzzy full-text search with a TUI plus experimental semantic search, zero infrastructure.
   - Check whether `claude-history`'s search already filters `tool_result` noise adequately before building anything custom.
2. **Fallback for transport**: if `claude-code-sync` mishandles mid-write files or namespacing, use Syncthing (best mid-write safety) or a hand-rolled git script with the quiescence + namespacing rules above.
3. **Fallback for search**: if `claude-history`'s search quality disappoints, build a SQLite FTS5 index (BM25 ranking, structured columns, incremental re-indexing) on top of the `jq`-based text/tool_use extraction — estimated roughly half a day of work.
4. **Exclude s3rbase** from any centralization scheme — it's client-owned hardware; query it live over SSH as needed, never copy its transcripts into personal storage.

## Supporting Scripts

Both live in `.scratch/` as throwaway research tools, not meant to be reused as-is:

- **`extract_transcript.py`** — scans a single transcript JSONL file, extracts `text`, `tool_use`, and `tool_result` content blocks, and prints matching lines for a fixed keyword list (`s3rbase`, `transcript`, `central`, `archiv`, `rsync`, `sync`). Used to pull out transcript-centralization-relevant excerpts from a raw session log.
- **`extract2.py`** — same pattern, narrower keyword list (`centralis`, `centraliz`, `cross-machine`, `retention`, `aggregat`, `search across`, `index`) and only extracts `text` blocks (no `tool_use`/`tool_result`). A second, more targeted pass over transcripts for this research.

## Related Investigation: Stress-Test Sweep on s3rbase

`stress-test-sweep-s3rbase.md` is a separate transcript-mining pass (using remote SSH access to s3rbase, not centralized storage) that reviewed stress-test loop activity across s3rbase's projects — this was the parallel brain-dump topic (stress-test token burn) that also depended on cross-machine transcript access. Findings: all genuine stress-test activity on s3rbase is confined to one repo (`sea3r_automation/portal`); 76 session plan-mode files carry a Stress-Test Log, spanning 2026-07-14 to 2026-08-13, totaling ~185 stress-test passes; 8 files show 5+ pass outlier chains (max 10, on `cheeky-popping-origami`), most resolving via a "COUNTER RESET" (baseline restart after repeated RERUN_NEEDED) rather than indefinite re-litigation. This confirms transcript access has direct value beyond the original "what was I doing" use case — it was used here to retroactively audit workflow behavior across sessions. It does not bear on the storage/sync/search recommendation itself.

## Current Status

**Research complete. Not implemented.** No cron job, hook, sync process, or centralization infrastructure of any kind currently exists on any machine. The Google Drive + rclone plan from 2026-08-06 was superseded by the 2026-08-14 report and was never built either. The only concrete change actually applied from this research is the `cleanupPeriodDays: 365` setting now confirmed consistent on SkikkLaptop and skikk-thor.

## Next Steps / Open Decision

Concrete first step, should someone act on this: install `claude-code-sync` and `claude-history` and try them against a private git remote for about a week before building anything custom (custom SQLite FTS5 indexing or hand-rolled Syncthing/git transport). Open decisions not yet settled:

- Whether the third machine (`wsl-skikk`) is in scope for centralization.
- Git remote choice if a hand-rolled git-repo route is needed: GitHub private repo, self-hosted bare repo, or both (dual-remote).
- Sync cadence (daily was the stated default interval; quiescence is the real gate, not frequency).
