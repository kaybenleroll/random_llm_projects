# Extract of anthropics-skills-claude-api-model-migration.md

Title: model-migration.md
Source URL: https://raw.githubusercontent.com/anthropics/skills/main/skills/claude-api/shared/model-migration.md
Fetch time: 2026-10-13T10:10:04Z
Full snapshot: 346255 bytes, sha256 b4fe96362b865a28726ab877c966624d5bfc2f86ff9b34940a34e3f8b6fc034e
Extract size: 9395 of 346255 bytes (2.7%)

Full text not committed (licence/size); re-fetch from the URL and verify the sha256.
Entries below are the quotes cited by the checklist, each with the line number and section heading in the full snapshot at the hash above. Quote presence in the full snapshot was verified when the checklist was built (see .scratch only); this folder lets a reader re-fetch the source and confirm each quote and location.
Line numbers refer to the full snapshot (as converted text).

-----
L753 | Behavioral shifts (prompt-tunable) | "raise effort to `high` or `xhigh` rather than prompting around it"
L783 | Behavioral shifts (prompt-tunable) | "NEVER use generic AI-generated aesthetics like overused font families (Inter, Roboto, Arial, system fonts)"
L1085 | Behavioral shifts (prompt-tunable) | "ask Claude to self-check" is generally sound advice and is wrong here"
L1087 | Behavioral shifts (prompt-tunable) | "**Removing them reduces over-verification with no capability regression** - this is a delete, not a rewrite."
L1095 | Behavioral shifts (prompt-tunable) | "any "delegate more" guidance you added for Opus 4.8 should come out"
L1095 | Behavioral shifts (prompt-tunable) | "A deterministic ceiling on spawn count is the reliable lever"
L1106 | Behavioral shifts (prompt-tunable) | "Review, verification, or to double check your work. Verification belongs in your main agent loop."
L1138 | Behavioral shifts (prompt-tunable) | "if a review harness says "only report high-severity issues" or "be conservative", Claude Opus 5 follows it literally."
L1155 | Claude Opus 5 Migration Checklist | "**Delete** verification instructions from prompts and verification steps from the harness"
L1268 | Behavioral shifts (prompt-tunable) | "Positive examples showing the desired concision tend to be more effective than telling the model what not to do."
L1272 | Behavioral shifts (prompt-tunable) | "If the harness has scaffolding to force interim status messages ("After every 3 tool calls, summarize progress"), **try removing it**."
L1274 | Behavioral shifts (prompt-tunable) | "The same literalism means style/tone directives carried over from Sonnet 4.6 may now over-apply - re-baseline holdover lines like "be concise" before keeping them."
L1286 | Behavioral shifts (prompt-tunable) | "be concrete about where the bar is rather than using qualitative terms like "important"
L1288 | Behavioral shifts (prompt-tunable) | "Generic instructions ("don't use that color," "make it clean and minimal") tend to shift it to a different fixed palette rather than producing variety."
L1476 | Behavioral shifts (prompt-tunable) | "At higher effort on routine work, Claude Fable 5.1 can gather context and deliberate beyond what the task needs"
L1476 | Behavioral shifts (prompt-tunable) | "Lower effort settings - including `low` - still perform very well on Claude Fable 5.1, often exceeding the `xhigh` or even `max` performance of previous models."
L1480 | Behavioral shifts (prompt-tunable) | "Claude Fable 5.1 is very responsive to explicit communication-style sections in system prompts; invest in them rather than fighting output style downstream."
L1480 | Behavioral shifts (prompt-tunable) | "You don't need to enumerate these behaviors by name; a brief instruction is just as effective:"
L1486 | Behavioral shifts (prompt-tunable) | "Before reporting progress, audit each claim against a tool result from this session."
L1492 | Behavioral shifts (prompt-tunable) | "instead of suppressing delegation (a common prior-model guardrail), use sub-agents frequently"
L1492 | Behavioral shifts (prompt-tunable) | "Sub-agents that communicate **asynchronously** with the orchestrator outperform spawn-and-block"
L1508 | Behavioral shifts (prompt-tunable) | "Claude Fable 5.1 performs better when it understands the intent behind a request"
L1519 | Long-running agent recommendations | "After migrating, A/B the workload with older step-by-step scaffolding removed - prefer stating the goal and constraints over enumerating the steps."
L1553 | Claude Fable 5.1 Migration Checklist | "over-prescriptive prompts/skills reduce Claude Fable 5.1 output quality"
L1768 | Behavioral shifts (prompt-tunable) | "level names don't correspond to the same amount of thinking across models."
L1775 | Behavioral shifts (prompt-tunable) | "Keep the word "privately" - without it the model sometimes answers the reminder ("nothing further is needed") instead of the user in its final reply"
L1775 | Behavioral shifts (prompt-tunable) | "Placement matters more than wording - one sentence near the end of the current request moves the number far more than the same text in the system prompt"
L1787 | Behavioral shifts (prompt-tunable) | "style instructions placed in the first user turn of a session hold better than the same text in the system prompt"
L1793 | Behavioral shifts (prompt-tunable) | "**If the prompt contains anti-formatting language, remove it** or replace it with a rule that says when formatting is appropriate:"
L1811 | Behavioral shifts (prompt-tunable) | "the Claude Opus 5 guidance to delete verification instructions doesn't apply here (tentative: rests on a small number of reports)"
L1811 | Behavioral shifts (prompt-tunable) | "The opening sentence of the first ("The user is not watching") is load-bearing - keep it as written"
L1811 | Behavioral shifts (prompt-tunable) | "This prompt can make the model less likely to clarify ambiguous requests."
L1846 | Behavioral shifts (prompt-tunable) | "try to surgically edit a file rather than rewrite the entire thing."
L2017 | Choosing an effort level - the default is `medium`, and the levels don't map 1:1 from Claude Opus 5 | "**Set `effort` explicitly** and re-run the sweep rather than carrying the Claude Opus 5 setting over."
L2018 | Choosing an effort level - the default is `medium`, and the levels don't map 1:1 from Claude Opus 5 | "lower the effort level before adding "think less" instructions"
L2051 | Behavioral shifts (prompt-tunable) | "may no longer be needed - keep them as the starting point, then re-test each on your own evals rather than carrying them over untouched."
L2053 | Behavioral shifts (prompt-tunable) | "It responds well to instructions that name specific patterns to avoid."
L2057 | Behavioral shifts (prompt-tunable) | "harness scaffolding built for visual inputs on earlier models may no longer be needed - re-test it."
L2058 | Behavioral shifts (prompt-tunable) | "turns run longer than on Claude Opus 5 - plan timeouts, streaming, and progress UX accordingly, and lower effort before prompting for brevity."
L2071 | Claude Opus 5.5 Migration Checklist | "re-test the thinking-disabled mitigation instruction, delete any "don't think" rule."
L2072 | Claude Opus 5.5 Migration Checklist | "re-evaluate Claude Opus 5-specific verbosity / verification / scope instructions."
L2183 | Choosing an effort level - recalibrated levels, default still `high` | "`medium` for agentic coding and multistep tool use; `low` for chat, content generation, classification, extraction, and search."
L2185 | Choosing an effort level - recalibrated levels, default still `high` | "**To get less thinking, lower the effort level.**"
L2204 | Behavioral shifts (prompt-tunable) | "If the Claude Sonnet 5 prompts carry workarounds for these - refusal steering, tool-call retry shims, instructions like "do not be lazy" - remove them"
L2205 | Behavioral shifts (prompt-tunable) | "Remove language that discourages tool use ("only use tools when strictly necessary", "minimize tool calls" - it follows these literally)."
L2206 | Behavioral shifts (prompt-tunable) | "Never put user text inside a `tool_result` block"
L2207 | Behavioral shifts (prompt-tunable) | "Mostly at `low` effort, the model sometimes reports a code change as done without a check that exercises it"
L2210 | Behavioral shifts (prompt-tunable) | "Leave it out where earlier work should keep being re-examined - long analyses, or agentic tasks where a later step can reveal a mistake in an earlier one."
L2225 | Claude Sonnet 5.5 Migration Checklist | "Prompts: remove workarounds (refusal steering, tool-call retry shims, "do not be lazy") and tool-discouraging language"
L2341 | Choosing an effort level - new on the Haiku line, default `medium` | "in Anthropic's testing the model still thought when the prompt told it to answer directly."
L2364 | Behavioral shifts (prompt-tunable) | "also give it today's date, in the system prompt or in the search tool's description"
L2365 | Behavioral shifts (prompt-tunable) | "Avoid blanket instructions such as "search for any present-day factual question, regardless of how confident you are"
L2368 | Behavioral shifts (prompt-tunable) | "With a long coding-agent system prompt at `low` effort, it sometimes stops early and hands the task back to the user."
L2371 | Behavioral shifts (prompt-tunable) | "Keep to them when a user argues, gives a sympathetic reason, asks for just a small part, says that someone approved an exception, or keeps asking."
