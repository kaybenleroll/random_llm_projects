# Codex project instructions

## Orchestration

- For substantial authorised work, the main session coordinates scope,
  partitioning, dispatch, integration, and verification. Delegate research,
  implementation, and routine testing by default.
- Keep work local when it is tightly coupled, immediately blocking, or solvable
  in one or two tool calls. Do not fan out work that needs one coherent model.
- Give each subagent bounded scope and disjoint write ownership. Do not duplicate
  exploration or permit nested delegation without explicit user instruction.
- Default cap: three concurrent and six total subagents per task.
- Inspect live available/deferred subagent tools before concluding delegation is
  unavailable.

## Model economy

- Use the cheapest capable available model. The current local mapping is Luna for
  mechanical work, Terra for ordinary implementation/debugging, Sol for difficult
  ambiguity or architecture, and Astra for exceptional end-to-end work. Sol/Astra
  require an explicit reason and must not be inherited by broad fan-out.
- Delegated prompts state model/effort, scope, stop condition, and output format.
  Prefer short summaries with paths and line references; put long findings in
  `.scratch/`.

## Completion

- The main session integrates and verifies delegated work. Escalate only for a
  demonstrated reasoning or reliability problem, not for repository size,
  missing context, vague requirements, or weak verification.
- Handoff evidence is the working tree, diff, tests, build artefacts, and written
  checkpoints—not private transcripts.
- Preserve unrelated changes. Keep durable workflow policy here; keep
  machine/account-specific settings and subscription observations user-level.

See [docs/codex-orchestration.md](docs/codex-orchestration.md) for rationale and
the fuller policy record.
