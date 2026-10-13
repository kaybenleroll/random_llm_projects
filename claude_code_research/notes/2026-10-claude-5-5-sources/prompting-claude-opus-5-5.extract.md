# Extract of prompting-claude-opus-5-5.md

Title: Prompting Claude Opus 5.5
Source URL: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5
Fetch time: 2026-10-13T09:10:14Z
Full snapshot: 28753 bytes, sha256 3432e66ac97f77b45e1ecba014c9d6d0001be7ab47b55ebe8c70f5aa55883a14
Extract size: 5899 of 28753 bytes (20.5%)

Full text not committed (licence/size); re-fetch from the URL and verify the sha256.
Entries below are the quotes cited by the checklist, each with the line number and section heading in the full snapshot at the hash above. Quote presence in the full snapshot was verified when the checklist was built (see .scratch only); this folder lets a reader re-fetch the source and confirm each quote and location.
Line numbers refer to the full snapshot (as converted text).

-----
L9 | (no heading) | "Existing Claude Opus 5 prompts should perform well without changes"
L33 | Capabilities relevant to prompting | "say plainly what it did, what it found, and what it needs from you"
L38 | Calibrate effort | "Start at `medium`, the default on Claude Opus 5.5 (Claude Opus 5 defaults to `high`), set it explicitly"
L38 | Calibrate effort | "Effort level names don't correspond to the same amount of thinking across models"
L38 | Calibrate effort | "Claude Opus 5.5 at `medium` matches or exceeds Claude Opus 5 at `high` on coding and knowledge-work evaluations"
L38 | Calibrate effort | "because thinking is always on, it's the first setting to adjust when trading off intelligence, latency, and cost"
L40 | Calibrate effort | "Claude Opus 5.5 tends to think more per turn than Claude Opus 5, especially at `xhigh` and `max`"
L43 | Calibrate effort | "Reserve `xhigh` and `max` for work where you've measured a quality gain."
L44 | Calibrate effort | "Lowering effort reduces thinking, and with it cost and latency, more reliably than prompt instructions do."
L46 | Calibrate effort | "Changing the top-level `effort` value between requests invalidates the prompt cache."
L50 | Prompts written for thinking disabled | "Claude Opus 5 accepts `thinking: {"type": "disabled"}` at `high` effort or below; Claude Opus 5.5 doesn't"
L52 | Prompts written for thinking disabled | "Start at `low` effort and measure."
L52 | Prompts written for thinking disabled | "a system prompt line such as "Answer directly without deliberating." can reduce thinking further"
L53 | Prompts written for thinking disabled | "If your prompt asked the model to write out its reasoning in the response as a substitute for thinking, remove that instruction"
L53 | Prompts written for thinking disabled | "a prompt that pushes the model to reproduce its reasoning in the response text may be declined with the `reasoning_extraction`"
L54 | Prompts written for thinking disabled | "remove the no-thinking rule either way"
L61 | Unattended agentic runs | "Treat a text-only end of turn as a report rather than as proof the task is done."
L61 | Unattended agentic runs | "Keep the task's parts in a checklist the model updates, such as a to-do tool or a file."
L61 | Unattended agentic runs | "have a separate, smaller model check the conversation against it at each end of turn"
L61 | Unattended agentic runs | "stop after two or three automatic continuations on the same task rather than repeating them indefinitely"
L67 | Unattended agentic runs | "If something the model started is still running, such as a background command or a subagent, don't treat the task as done yet"
L69 | Unattended agentic runs | "Claude Opus 5.5 is responsive to instructions that name the specific kinds of early stop you want it to avoid"
L71 | Unattended agentic runs | "adding it partway through changes the `system` prompt and invalidates the conversation's earlier thinking blocks"
L71 | Unattended agentic runs | "keep your own confirmation step for risky or irreversible actions, and leave the addition out of human-in-the-loop applications"
L71 | Unattended agentic runs | "Expect somewhat more tool calls and output tokens per task."
L81 | Safeguard refusals | "The biology safeguards are the same as Claude Fable 5.1's and are new if you're coming from Claude Opus 5."
L95 | User-facing progress updates | "a one-line statement of intent before the first tool call and a short recap at the end, say so in the system prompt"
L100 | User-facing progress updates | "The user hasn't heard from you in a while — say in a few words what you're doing, then continue."
L105 | Explore context in multi-app workflows | "Claude Opus 5.5 tends to get to work quickly, and on loosely specified tasks it helps to tell the model to look through the relevant sources before acting"
L111 | Explore context in multi-app workflows | "keep untrusted content out of the records it searches"
L118 | Time signals for multiagent harnesses | "Time matters here: do not spend time that can be avoided, and the earlier a correct result is obtained, the better."
L121 | Time signals for multiagent harnesses | "The budget is advisory and nothing stops the model at the limit, so if you need a hard stop, keep your own timeout."
L125 | Thinking instructions in chat system prompts | "if your system prompt contains instructions that tell Claude to think carefully before answering, consider removing them for Claude Opus 5.5"
L133 | Thinking instructions in chat system prompts | "Leave it out where you want the model to keep re-examining its earlier work"
L137 | Mark pasted text in user messages | "resists indirect prompt injection, meaning instructions that arrive through tool results, web pages, and on-screen or browser content, better than any earlier Opus model"
L157 | Tools for complex visual inputs | "re-test whether you still need scaffolding you built for visual inputs on earlier models"
L161 | Frontend design defaults | "It responds well to instructions that name specific patterns to avoid"
