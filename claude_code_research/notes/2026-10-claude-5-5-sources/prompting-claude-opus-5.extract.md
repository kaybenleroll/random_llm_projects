# Extract of prompting-claude-opus-5.md

Title: Prompting Claude Opus 5
Source URL: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5
Fetch time: 2026-10-13T09:10:16Z
Full snapshot: 12910 bytes, sha256 cb089946ebaa9500565b2326e8411a8a6f6c8d1a11c843155b91cc5743e00e83
Extract size: 3865 of 12910 bytes (29.9%)

Full text not committed (licence/size); re-fetch from the URL and verify the sha256.
Entries below are the quotes cited by the checklist, each with the line number and section heading in the full snapshot at the hash above. Quote presence in the full snapshot was verified when the checklist was built (see .scratch only); this folder lets a reader re-fetch the source and confirm each quote and location.
Line numbers refer to the full snapshot (as converted text).

-----
L15 | Capability improvements | "it performs best when given the complete task specification up front and left to run"
L16 | Capability improvements | "If your review prompt says "only report high-severity issues" or "be conservative," the model may follow that instruction literally and report less"
L17 | Capability improvements | "use `low` and `medium` liberally as your primary control for token cost and response time wherever quality holds, and step up to `xhigh` for demanding coding and agentic work"
L25 | Response length and verbosity | "lowering effort can reduce thinking volume without reliably shortening the visible response"
L33 | Response length and verbosity | "In a long system prompt, pair the instruction with a short reminder near the end of the prompt:"
L49 | User-facing progress updates | "Positive examples of the communication style you want tend to be more effective than instructions about what not to do."
L53 | Written deliverable length | "files that Claude Opus 5 writes to disk (reports, Markdown documents, summaries) are often longer than on prior models"
L61 | Task scope and over-verification | "instructions like these cause over-verification on Claude Opus 5, and removing them reduces wasted tokens with no loss in quality"
L63 | Task scope and over-verification | "Claude Opus 5 can also expand the scope of a task, adding steps that weren't requested or applying its own judgment about what the task should be."
L71 | Controlling subagent spawning | "Claude Opus 5 delegates to subagents more readily than prior models."
L74 | Controlling subagent spawning | "do not use subagents to verify or double-check your own work"
L77 | Controlling subagent spawning | "the deterministic caps are the `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` and `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` environment variables"
L77 | Controlling subagent spawning | "Claude Code adds a delegation instruction of its own on Claude Opus 5 only when you use its `claude_code` system prompt preset"
L81 | Self-correction | "Avoid instructing re-checks it already performs"
L83 | Self-correction | "The model also narrates corrections to its earlier statements more than prior models do"
L91 | Running with thinking disabled | "for most tasks, thinking enabled at `low` effort performs better than thinking disabled at similar cost"
L91 | Running with thinking disabled | "A request that combines `thinking: {"type": "disabled"}` with effort `xhigh` or `max` returns a 400 error."
L95 | Running with thinking disabled | "If your system prompt contains a rule instructing the model not to think or not to reason, remove it; that kind of instruction increases tag leakage."
L103 | Running with thinking disabled | "Instructions that call out thinking tags by name are less effective than the general form, so avoid naming them specifically."
L107 | Reasoning in the response | "Prompts, skills, and tool descriptions that ask Claude Opus 5 to write out its thinking or reasoning, verbatim or in a fixed format, may be declined"
