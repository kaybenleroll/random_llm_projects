# Extract of cc-model-config.md

Title: Model configuration
Source URL: https://code.claude.com/docs/en/model-config
Fetch time: 2026-10-13T09:10:35Z
Full snapshot: 116499 bytes, sha256 8f65d1b1463bc7e24fa0eeeadd290278162b1f26c56be6190a1db510de8d7ca0
Extract size: 3226 of 116499 bytes (2.8%)

Full text not committed (licence/size); re-fetch from the URL and verify the sha256.
Entries below are the quotes cited by the checklist, each with the line number and section heading in the full snapshot at the hash above. Quote presence in the full snapshot was verified when the checklist was built (see .scratch only); this folder lets a reader re-fetch the source and confirm each quote and location.
Line numbers refer to the full snapshot (as converted text).

-----
L40 | Model aliases | "Special mode that uses `opus` during plan mode, then switches to `sonnet` for execution"
L53 | Model aliases | "the `fable` alias resolves to Fable 5.1"
L61 | Model aliases | "To pin to a specific version, use the full model name, for example `claude-opus-5-5`"
L64 | Model aliases | "Sonnet 5.5 requires Claude Code v2.1.284 or later, and Opus 5.5 requires v2.1.280 or later."
L82 | Work with Fable | "hand it the result you want and let it plan the path."
L84 | Work with Fable | "it verifies its own work with less prompting, so reminders to test or check are usually unnecessary."
L603 | Adjust effort level | "Claude Code falls back to the highest supported level at or below the one you set."
L605 | Adjust effort level | "Claude Code resolves the session's effort level in this order, taking the first that applies:"
L609 | Adjust effort level | "`high` on every model that supports effort, except that Opus 5.5, Sonnet 5.5, and Haiku 5.5 default to `medium`"
L613 | Adjust effort level | "a top-level `effortLevel` in your user settings file doesn't count for Opus 5.5."
L664 | Choose an effort level | "On Opus 5.5 and Sonnet 5.5, it fits day-to-day engineering work with a clear scope, such as implementing a new feature."
L667 | Choose an effort level | "`max` may show diminishing returns and is prone to overthinking, so test before adopting it broadly"
L672 | Choose an effort level | "The effort scale is calibrated per model, so the same level name does not represent the same underlying value across models."
L674 | Choose an effort level | "start at `medium` rather than carrying over the level you used on Opus 5."
L678 | Use ultrathink for one-off deep reasoning | "Claude Code passes other phrases such as "think", "think hard", and "think more" through as ordinary prompt text and doesn't recognize them as keywords."
L692 | Set the effort level | "Frontmatter effort applies when that skill or subagent is active, overriding the session level but not the environment variable."
L700 | Adaptive reasoning and fixed thinking budgets | "you can say so directly in your prompt or in `CLAUDE.md`; the model responds to that guidance within its effort setting."
L702 | Adaptive reasoning and fixed thinking budgets | "Fable models, Sonnet 5 and later, Haiku 5.5, and Opus 4.7 and later always use adaptive reasoning."
L1007 | Prompt caching configuration | "Set to `1` to disable prompt caching for Fable models only"
