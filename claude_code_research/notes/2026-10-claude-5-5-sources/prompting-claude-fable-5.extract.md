# Extract of prompting-claude-fable-5.md

Title: Prompting Claude Fable 5
Source URL: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5
Fetch time: 2026-10-13T09:10:16Z
Full snapshot: 19305 bytes, sha256 f10e377e6a6d53f848db16c58f6bb23d7e1c03e475788e87d0c6bd99d03603b2
Extract size: 4572 of 19305 bytes (23.7%)

Full text not committed (licence/size); re-fetch from the URL and verify the sha256.
Entries below are the quotes cited by the checklist, each with the line number and section heading in the full snapshot at the hash above. Quote presence in the full snapshot was verified when the checklist was built (see .scratch only); this folder lets a reader re-fetch the source and confirm each quote and location.
Line numbers refer to the full snapshot (as converted text).

-----
L4 | (no heading) | "Behavioral differences and prompting patterns for Claude Fable 5 and Claude Mythos 5"
L14 | (no heading) | "adaptive thinking only, summarized-only thinking output, no extended thinking budgets"
L35 | Longer turns by default | "Individual requests on hard tasks can run for many minutes at higher"
L38 | Longer turns by default | "When you have enough information to act, act."
L43 | Consider all effort levels | "Use `high` as the default for most tasks, with `xhigh` for the most capability-sensitive workloads and `medium` or `low` for routine work."
L43 | Consider all effort levels | "Lower effort settings on Claude Fable 5 still perform well and often exceed `xhigh` performance on prior models."
L48 | Consider all effort levels | "Don't add features, refactor, or introduce abstractions beyond what the task requires."
L53 | Strong instruction following | "you can steer most behaviors with a brief instruction rather than enumerating each behavior by name"
L56 | Strong instruction following | "Being readable and being concise are different things, and readability matters more."
L58 | Strong instruction following | "not to compress the writing into fragments, abbreviations, arrow chains like A → B → fails, or jargon"
L64 | Strong instruction following | "Pause for the user only when the work genuinely requires them: a destructive or irreversible action, a real scope change, or input that only they can provide."
L72 | Ground progress claims during long runs | "Before reporting progress, audit each claim against a tool result from this session."
L77 | State the boundaries | "Claude Fable 5 can occasionally take unrequested actions (drafting an email when none was asked for, creating defensive git-branch backups)."
L80 | State the boundaries | "When the user is describing a problem, asking a question, or thinking out loud rather than requesting a change, the deliverable is your assessment."
L85 | Parallel subagents | "prefer asynchronous communication between orchestrator and subagents over blocking until each subagent returns"
L93 | Construct a memory system | "Provide a place to write notes, as simple as a Markdown file"
L110 | Rare cases of early stopping | "You are operating autonomously. The user is not watching in real time and cannot answer questions mid-task"
L115 | Rare cases of context-budget concern | "Avoid surfacing explicit context-budget counts where possible."
L118 | Rare cases of context-budget concern | "You have ample context remaining. Do not stop, summarize, or suggest a new session on account of context limits."
L123 | Give the reason, not only the request | "Claude Fable 5 tends to perform better when it understands the intent behind a request"
L134 | Readability when communicating with the user | "Terse shorthand is fine between tool calls. Your final summary is different: it's for a reader who didn't see any of that."
L138 | Readability when communicating with the user | "Don't use arrow chains, hyphen-stacked compounds, or labels you made up earlier."
L162 | Create a send-to-user tool | "Defining the tool is not sufficient on its own; without an instruction in the system prompt, Claude Fable 5 rarely calls it."
L172 | Recommended scaffolding changes | "Pick a task harder than what you'd assign to prior models"
L173 | Recommended scaffolding changes | "Separate, fresh-context verifier subagents tend to outperform self-critique."
L174 | Recommended scaffolding changes | "Skills developed for prior models are often too prescriptive for Claude Fable 5 and can degrade output quality."
L175 | Recommended scaffolding changes | "Audit existing skills and system prompts for reflection or show-your-thinking instructions when migrating."
