# pi_research — pi harness research

## Purpose

Research and experiments on the `pi` coding-agent harness (installed via mise):
- Capabilities, limits, and behaviour patterns
- Extensions, skills, prompt templates, and configuration
- Model/provider comparison under pi
- Comparison against Claude Code (`../claude_code_research/`) and Codex (`../codex_research/`)

## Working approach

- Findings go in `notes/`; durable policy and rationale in `docs/`; reusable, standalone runbooks in `artifacts/`.
- Artifacts must be portable to a fresh session on another machine: concrete commands, pass/fail thresholds, no references to this repo or session.
- All working files and experiment outputs go in `.scratch/`, never `/tmp/`.
- Machine/account-specific settings stay user-level, not in this directory.
- Preserve unrelated changes. Handoff evidence is the working tree, diff, tests, and written checkpoints — not private transcripts.

## File layout

```
AGENTS.md    — project instructions (this file)
docs/        — policy records, rationale, harness reference
notes/       — research notes, findings, session write-ups
artifacts/   — reusable prompts, extensions, runbooks worth keeping
.scratch/    — working files and experiment outputs
```

## Open questions

- (fill in as research starts)
