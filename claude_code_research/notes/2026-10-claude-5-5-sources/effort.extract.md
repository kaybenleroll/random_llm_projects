# Extract of effort.md

Title: Effort
Source URL: https://platform.claude.com/docs/en/build-with-claude/effort
Fetch time: 2026-10-13T09:10:20Z
Full snapshot: 42983 bytes, sha256 60ab9707701eb92ea0b21059de490d49fd93b81e194d4e442c03133c26dac118
Extract size: 3305 of 42983 bytes (7.7%)

Full text not committed (licence/size); re-fetch from the URL and verify the sha256.
Entries below are the quotes cited by the checklist, each with the line number and section heading in the full snapshot at the hash above. Quote presence in the full snapshot was verified when the checklist was built (see .scratch only); this folder lets a reader re-fetch the source and confirm each quote and location.
Line numbers refer to the full snapshot (as converted text).

-----
L225 | How effort works | "Claude Opus 5.5 and Claude Haiku 5.5 default to medium."
L237 | How effort works | "Lower effort also means fewer and terser tool calls."
L247 | Effort levels | "Simpler tasks that need the best speed and lowest costs, such as subagents"
L252 | Effort levels | "Effort is a behavioral signal, not a strict token budget."
L259 | Recommended effort levels for Claude Fable 5.1 | "step down to `medium` or `low` for routine or latency-sensitive work once your evals show quality holds"
L271 | Recommended effort levels for Claude Opus 5.5 | "so a request that omits `effort` runs one level lower than it did on Claude Opus 5"
L271 | Recommended effort levels for Claude Opus 5.5 | "Run an effort sweep on your own evals rather than carrying settings over from an earlier model"
L277 | Recommended effort levels for Claude Opus 5 | "Effort controls thinking volume, not visible response length: on Claude Opus 5, changing effort does not reliably shorten responses"
L307 | Recommended effort levels for Claude Opus 4.7 | "On most workloads `max` adds significant cost for relatively small quality gains"
L309 | Recommended effort levels for Claude Opus 4.7 | "If you observe shallow reasoning on complex problems with Claude Opus 4.7, raise effort rather than prompting around it."
L309 | Recommended effort levels for Claude Opus 4.7 | "At lower effort levels, the model scopes its work to what was asked rather than doing more than requested."
L315 | Recommended effort levels for Claude Sonnet 5.5 | "Its levels are recalibrated, so a level doesn't produce the same amount of thinking as the same level on Claude Sonnet 5."
L315 | Recommended effort levels for Claude Sonnet 5.5 | "For agentic coding and multistep tool use, start with `medium` for well-specified tasks and move to `high` for harder or longer ones."
L342 | Recommended effort levels for Claude Haiku 5.5 | "In long agent prompts, the model is more likely to skip a search, stop early, or skip a check at `low`."
L342 | Recommended effort levels for Claude Haiku 5.5 | "Use `high` for knowledge work, longer agent tasks, and strict instruction following."
L657 | Per-message effort (beta) | "its earlier replies were written at the previous level, and it tends to stay consistent with them."
L665 | Best practices | "The API defaults to `high` (`medium` on Claude Opus 5.5 and Claude Haiku 5.5), but the right starting point depends on your model and workload."
L669 | Best practices | "Changing the top-level effort value between requests invalidates"
