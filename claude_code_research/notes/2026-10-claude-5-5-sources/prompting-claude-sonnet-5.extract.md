# Extract of prompting-claude-sonnet-5.md

Title: Prompting Claude Sonnet 5
Source URL: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5
Fetch time: 2026-10-13T09:10:16Z
Full snapshot: 15963 bytes, sha256 560089d4c75943749b7a81afdf628290c518713e8e82aff88b389c5cc5544c8e
Extract size: 3448 of 15963 bytes (21.6%)

Full text not committed (licence/size); re-fetch from the URL and verify the sha256.
Entries below are the quotes cited by the checklist, each with the line number and section heading in the full snapshot at the hash above. Quote presence in the full snapshot was verified when the checklist was built (see .scratch only); this folder lets a reader re-fetch the source and confirm each quote and location.
Line numbers refer to the full snapshot (as converted text).

-----
L21 | Response length and verbosity | "Positive examples showing how Claude can communicate with the appropriate level of concision tend to be more effective than negative examples"
L25 | Calibrating effort and thinking depth | "For the hardest coding and agentic tasks, raise effort to `xhigh`."
L31 | Calibrating effort and thinking depth | "Reserve for short, scoped tasks and latency-sensitive workloads that are not intelligence-sensitive."
L33 | Calibrating effort and thinking depth | "When benchmarking, match by observed thinking length rather than effort name."
L35 | Calibrating effort and thinking depth | "At `low` and `medium`, the model scopes its work to what was asked rather than going above and beyond."
L37 | Calibrating effort and thinking depth | "If you observe shallow reasoning on complex problems, raise effort to `high` or `xhigh` rather than prompting around it."
L45 | Calibrating effort and thinking depth | "The triggering behavior for adaptive thinking is steerable."
L53 | Calibrating effort and thinking depth | "Manual extended thinking (`thinking: {type: "enabled", budget_tokens: N}`) is not supported on Claude Sonnet 5 and returns a 400 error."
L61 | Tool use triggering | "With thinking disabled, the model is less likely to reach for tools or consider searching"
L61 | Tool use triggering | "Claude Sonnet 5 is more agentic than Claude Sonnet 4.6 by default and will reach for tools and run self-verification loops more readily."
L65 | User-facing progress updates | "If you've added scaffolding to force interim status messages ("After every 3 tool calls, summarize progress"), try removing it."
L69 | More literal instruction following | "Claude Sonnet 5 interprets prompts literally and explicitly, particularly at lower effort levels."
L69 | More literal instruction following | "It does not silently generalize an instruction from one item to another, and it does not infer requests you didn't make."
L87 | Design and frontend defaults | "Generic instructions ("don't use that color," "make it clean and minimal") tend to shift the model to a different fixed palette rather than producing variety."
L132 | Interactive coding products | "it's important to specify the task, intent, and relevant constraints upfront in the first human turn"
L136 | Code review harnesses | "When a review prompt says things like "only report high-severity issues," "be conservative," or "don't nitpick," Claude Sonnet 5 may follow that instruction more faithfully"
L146 | Code review harnesses | "be concrete about where the bar is rather than using qualitative terms like "important"
