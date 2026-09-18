# Codex orchestration policy

Status: active working policy, 17 September 2026.

## Purpose

This repository records the durable workflow decisions from the Codex/Claude
comparison. The root `AGENTS.md` contains only the rules that should enter every
task's context. This document keeps the rationale, boundaries, and review
criteria under Git without loading them automatically.

## Decision

Use the main Codex session as an orchestrator. It should define the task,
partition independent work, dispatch bounded subagents, integrate their results,
and verify the final outcome. Subagents should perform most substantial
research, implementation, and routine testing.

Keep work in the main session when it is tightly coupled, immediately blocking,
or small enough for one or two tool calls. Do not manufacture fan-out for its
own sake.

## Delegation contract

Each delegated task has:

- one concrete responsibility and disjoint write ownership;
- an explicit model and reasoning effort;
- a stop condition and concise output format;
- short final reporting, with detailed findings written to `.scratch/` when
  necessary.

Do not duplicate exploration. Do not permit nested delegation unless the user
explicitly requests it. The main session owns integration, conflict resolution,
acceptance checks, and the final user-facing answer.

Default safety cap: three concurrent and six total subagents per user task.
Exceed it only when the user accepts the added coordination and usage cost.

## Model-routing policy

Start with the cheapest available model that can plausibly complete the bounded
task. The names below are the current local mapping, not a permanent availability
or capability claim:

| Work | Default |
| --- | --- |
| Mechanical edits, extraction, formatting, routine checks | Luna |
| Ordinary implementation, debugging, and structured research | Terra |
| Difficult ambiguity, architecture, contested synthesis, or high-cost review | Sol |
| Exceptional end-to-end work where failure cost justifies it | Astra |

Sol and Astra require a stated reason. They must not be inherited by broad
fan-out. Escalate after a demonstrated reasoning or reliability problem, not
because the repository is large, context is imperfect, or verification is
inconvenient.

## Why this differs from the prior setup

The Claude configuration made fan-out, bounded ownership, model tiering,
response minimisation, isolation, and workflow caps explicit. The prior Codex
setup left those decisions mostly implicit, so the main session tended to absorb
work and stronger models were easier to invoke than they should be.

This policy makes the default explicit while treating subscription limits as a
real design constraint. Strong models remain available for high-leverage
judgement; they are not the default for volume work.

## Scope boundary

Tracked repository files define portable workflow policy. User-level Codex
configuration and memory may record local model availability, account limits,
and personal preferences, but those facts are not repository requirements.

Review this policy when the Codex/Claude workflow, available models, or account
limits materially change.
