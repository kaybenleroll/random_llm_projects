# Extract of prompting-claude-sonnet-5-5.md

Title: Prompting Claude Sonnet 5.5
Source URL: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5
Fetch time: 2026-10-13T09:10:14Z
Full snapshot: 27949 bytes, sha256 6886cdd2625b73be5bd74420e31c3a050c1c52b8073b9bebe15f4dcf33e44f91
Extract size: 5086 of 27949 bytes (18.2%)

Full text not committed (licence/size); re-fetch from the URL and verify the sha256.
Entries below are the quotes cited by the checklist, each with the line number and section heading in the full snapshot at the hash above. Quote presence in the full snapshot was verified when the checklist was built (see .scratch only); this folder lets a reader re-fetch the source and confirm each quote and location.
Line numbers refer to the full snapshot (as converted text).

-----
L9 | (no heading) | "For the hardest long-horizon work, an Opus model is the better choice."
L9 | (no heading) | "Existing Claude Sonnet 5 prompts should perform well without changes"
L29 | Calibrate effort | "Its levels are recalibrated: a level doesn't produce the same amount of thinking as the same level on Claude Sonnet 5."
L29 | Calibrate effort | "For agentic coding and multistep tool use, start at `medium` for well-specified tasks and move to `high` for harder or longer ones."
L31 | Calibrate effort | "At `low` and `medium`, on long agentic tasks, it's more likely to stop and check in with the user before it finishes."
L31 | Calibrate effort | "At `low`, it keeps its thinking short and can skip verifying a change."
L36 | Calibrate effort | "Reserve `xhigh` and `max` for work where you've measured a quality gain, because thinking and replies get much longer there."
L37 | Calibrate effort | "Asking it in the system prompt to think less doesn't reliably reduce its thinking."
L37 | Calibrate effort | "From `medium` up, the model thinks briefly before almost every reply, even a greeting"
L39 | Calibrate effort | "Per-message effort changes need adaptive thinking."
L48 | Steer initiative and scope | "Keep working until everything the user asked for is done, and only stop to ask when you can't go on without the user or before a risky step."
L50 | Steer initiative and scope | "Don't add features, tests, files, docs or refactors that weren't asked for."
L53 | Steer initiative and scope | "The prompt doesn't replace your own rules about risky or irreversible actions."
L57 | Steer initiative and scope | "After it finishes a task, it can start its own rounds of review and verification, sometimes with subagents if your harness provides them."
L60 | Steer initiative and scope | "don't launch reviewer sub-agents unless the user asked for a review"
L68 | Steer initiative and scope | "When the user asks for ideas, options or a plan, give them that and stop."
L73 | Running without up-front thinking | "It's the lowest thinking setting on this model, and it's accepted at `high` effort or below."
L75 | Running without up-front thinking | "With `between_tools`, remove any instruction that tells the model not to think."
L82 | Reasoning tasks with JSON output | "On tasks like these, the model often answers without thinking first, particularly at `low` and `medium` effort."
L92 | Reasoning tasks with JSON output | "At `high` effort, the line brings accuracy close to what the model reaches at `xhigh`, for a modest increase in output tokens."
L111 | User-facing progress updates | "Next, remove older instructions such as "hold all findings for the final response"."
L111 | User-facing progress updates | "The model follows instructions like this."
L119 | User-facing progress updates | "Frequent harness text after tool results can make the model suspect a prompt injection"
L125 | Tool use in chat and knowledge work | "check your prompt for language that discourages tool use, such as "only use tools when strictly necessary" or "minimize tool calls", and remove it"
L128 | Tool use in chat and knowledge work | "Use the search tool to check specifics that may have changed since your training, such as what is allowed, required or charged, even when you feel confident."
L135 | Mid-turn user messages | "Sometimes it treats a genuine user message as a possible injection."
L141 | Mid-turn user messages | "Never put a notice and the user's words in the same block."
L142 | Mid-turn user messages | "don't add your own token or budget countdown after tool results"
L151 | Verification on coding tasks | "When you change code that can be run, built, or type-checked, run a real check that exercises the change before reporting it done"
L156 | Tolerant tool-call handling | "Claude Sonnet 5.5 occasionally calls a declared tool by a name that differs only in letter case, such as `bash` for `Bash`."
L169 | Safeguard refusals | "Finding vulnerabilities in source code is allowed. High-risk dual-use cybersecurity work isn't allowed."
L179 | Safeguard refusals | "If your prompts ask the model to include its reasoning in the response, remove those instructions, because they invite `reasoning_extraction` declines."
