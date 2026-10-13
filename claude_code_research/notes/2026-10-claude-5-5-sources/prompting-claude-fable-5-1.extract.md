# Extract of prompting-claude-fable-5-1.md

Title: Prompting Claude Fable 5.1
Source URL: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1
Fetch time: 2026-10-13T09:10:15Z
Full snapshot: 55050 bytes, sha256 4aa7e61031b5d52456433bd9804503717b8e0b5a3c35137f48ea5324c7913db4
Extract size: 5630 of 55050 bytes (10.2%)

Full text not committed (licence/size); re-fetch from the URL and verify the sha256.
Entries below are the quotes cited by the checklist, each with the line number and section heading in the full snapshot at the hash above. Quote presence in the full snapshot was verified when the checklist was built (see .scratch only); this folder lets a reader re-fetch the source and confirm each quote and location.
Line numbers refer to the full snapshot (as converted text).

-----
L4 | (no heading) | "Behavioral differences and prompting patterns for Claude Fable 5.1 and Claude Mythos 5.1"
L9 | (no heading) | "Your existing Claude Fable 5 prompts should perform well on Claude Fable 5.1 without changes"
L31 | (no heading) | "Prompts, skills, and tool descriptions that ask the model to write out its thinking or reasoning may be declined with the `reasoning_extraction` category."
L36 | Consider all effort levels | "Re-run the sweep even if you already ran one on Claude Fable 5: effort level names don't correspond to the same amount of thinking across models."
L38 | Consider all effort levels | "At `medium`, results roughly match Claude Fable 5 at lower cost, so step down to `medium` or `low` where your evals show quality holds."
L38 | Consider all effort levels | "At `low`, Claude Fable 5.1 is often competitive with Claude Opus and Claude Sonnet models on cost per task while scoring higher"
L44 | Ask for user-facing progress updates | "Claude Fable 5.1's default behavior is to write fewer user-facing updates during long tool-calling turns than Claude Fable 5 does."
L48 | Ask for user-facing progress updates | "Second, audit your prompt for instructions that suppress narration."
L56 | Ask for user-facing progress updates | "If your product collapses or hides tool output, tell the model."
L67 | Batch independent tool calls in agent loops | "First privately list what you need next; then request every item that doesn't depend on another's result in this one response."
L760 | Keep the conversation history append-only | "injecting and removing per-turn reminders, summarizing older turns in place, or changing the system prompt mid-session"
L760 | Keep the conversation history append-only | "compacting early to save cost may no longer be the right cost-intelligence tradeoff on Claude Fable 5.1, so experiment with later compaction points"
L766 | Writing density | "Add it to a user message (preferred) or the system prompt"
L775 | Writing density | "Please remove all mannered prose."
L780 | Formatting in chat | "If your prompt contains anti-formatting language, remove it or replace it with a rule that says when specific formatting is appropriate"
L788 | Quoting retrieved sources | "add one complete example of a correct response to the system prompt"
L808 | Finish the whole task | "Two system prompt additions together mitigate this. Apply both."
L820 | Finish the whole task | "The opening sentence, which tells the model the user isn't watching, carries much of the effect. Keep it as written."
L820 | Finish the whole task | "This block can also make the model less likely to ask about ambiguous requests, so check that trade-off on your own tasks."
L826 | Delivering work | "The user's request — or the plan they approved — sets the scope, and the scope is the deliverable: don't quietly narrow, widen, or swap it."
L828 | Delivering work | "A step you have decided on is something to run, not to announce"
L835 | Tell the model what to preserve in compaction summaries | "Claude Fable 5.1 responds well to being told explicitly what its summary must retain when a long conversation is compacted."
L843 | Keep changes and tests to what the task asks for | "It responds well to explicit instructions about what to leave out."
L846 | Keep changes and tests to what the task asks for | "don't fix, optimize or extend it in this change unless the requested behavior cannot work without it; report it as a follow-up in your summary"
L846 | Keep changes and tests to what the task asks for | "Commit tests only where the task asks for them or this repository already keeps tests for this kind of change"
L851 | Search triggering at low effort | "the simplest fix is to raise effort for the affected turns rather than the whole conversation"
L856 | Search triggering at low effort | "familiarity is not a reason to skip the search"
L863 | Reduce safeguard false positives | "Instead of "Does this program compile without errors?", ask "Are there any bugs in this program?"
L865 | Reduce safeguard false positives | "Tools that return base64-encoded data into the model's context can trigger false positives, so removing them is the recommended fix."
L869 | Prefer targeted edits over whole-file rewrites | "Claude Fable 5.1 is more likely than Claude Fable 5 to rewrite an entire text file rather than make a targeted edit."
L877 | Leave room for long outputs at xhigh and max effort | "The simplest approach is to run requests like these at `high`, the recommended starting point, and move to `xhigh` or `max` only where you've measured a quality gain"
L890 | Let the lead agent keep working while subagents run | "letting the lead continue while subagents run lowers average time to completion at similar quality, token usage, and cost"
