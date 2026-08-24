# claude_code_research — Claude Code capability research

## Purpose

Research and experiments focused on Claude Code (the CLI and agentic coding tool):
- Capabilities, limits, and behaviour patterns
- Skill/hook/workflow authoring and testing
- Prompt engineering for coding agents
- Multi-agent orchestration patterns

## Working approach

- Notes and findings go in `notes/`; reusable artifacts go in `artifacts/`
- Artifacts in `artifacts/` must be standalone runbooks portable to a fresh session on another machine — concrete commands, pass/fail thresholds, no references to this repo or session, not a report of session-specific findings

## File layout

```
notes/         — research notes, findings, session write-ups
artifacts/     — reusable prompts, skill stubs, workflow scripts worth keeping
.scratch/      — all working files and experiment outputs
```
