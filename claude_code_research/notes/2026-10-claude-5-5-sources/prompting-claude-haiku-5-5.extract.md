# Extract of prompting-claude-haiku-5-5.md

Title: Prompting Claude Haiku 5.5
Source URL: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-haiku-5-5
Fetch time: 2026-10-13T09:10:15Z
Full snapshot: 15006 bytes, sha256 e871a37701e88998c5bed2e15c586048c86d3d8ab5c333a67c60ad717e0131fd
Extract size: 3586 of 15006 bytes (23.9%)

Full text not committed (licence/size); re-fetch from the URL and verify the sha256.
Entries below are the quotes cited by the checklist, each with the line number and section heading in the full snapshot at the hash above. Quote presence in the full snapshot was verified when the checklist was built (see .scratch only); this folder lets a reader re-fetch the source and confirm each quote and location.
Line numbers refer to the full snapshot (as converted text).

-----
L9 | (no heading) | "Existing Claude Haiku 4.5 prompts should perform well without changes."
L24 | (no heading) | "Add it to new conversations only. A request that sends thinking blocks back after `system` changed can return a 400 error"
L29 | Use effort to control thinking | "It replaces the thinking budget (`budget_tokens`) that Claude Haiku 4.5 used, so there's no old setting to carry over."
L31 | Use effort to control thinking | "In long agent prompts, the model is more likely to skip a search, stop early, or skip a check at this level."
L32 | Use effort to control thinking | "`medium` is the default. Start here for most work, including agentic coding."
L33 | Use effort to control thinking | "`high` suits knowledge work, longer agent tasks, and strict instruction following."
L34 | Use effort to control thinking | "also run your evals on Claude Sonnet 5.5 and compare performance, cost, and speed"
L39 | Use effort to control thinking | "In Anthropic's testing, telling the model in the prompt to answer directly didn't stop it from thinking."
L39 | Use effort to control thinking | "This works at `low`, `medium`, and `high` only."
L40 | Use effort to control thinking | "At `xhigh` effort in multi-turn chats, the model sometimes writes its whole answer in its thinking and ends the turn with no visible text."
L45 | Accurate search results | "When you give Claude Haiku 5.5 a search tool, also give it today's date."
L56 | Accurate search results | "Records, office holders, prices, versions, rules and anything "latest" may have changed since then, so search for those before you answer, even when you feel sure."
L63 | Accurate search results | "In Anthropic's testing, that instruction made the model search on half of the prompts that needed no search."
L83 | Prevent early stopping in long agent prompts | "With a long coding-agent system prompt at `low` effort, it sometimes stops early and hands the task back to the user."
L90 | Prevent early stopping in long agent prompts | "moving from `low` to `medium` effort roughly halved early stopping. It also more than doubled the output tokens for each attempt."
L94 | Tell coding agents to verify their changes | "At `low` and `medium` effort, Claude Haiku 5.5 sometimes reports a code change as done without running a check."
L104 | Mid-turn user messages | "The model can then treat it as untrusted text and ignore it."
L120 | Keep chatbots to their system prompt | "When instruction following matters most, also use `high` effort."
L124 | Keep reasoning out of user-facing text | "If you see this behavior, switch to adaptive thinking and `medium` effort."
L137 | Safeguard refusals | "Sending the same request to Claude Haiku 5.5 again usually returns another refusal."
