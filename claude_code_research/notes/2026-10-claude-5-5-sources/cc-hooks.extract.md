# Extract of cc-hooks.md

Title: Hooks reference
Source URL: https://code.claude.com/docs/en/hooks
Fetch time: 2026-10-13T09:10:34Z
Full snapshot: 268811 bytes, sha256 31754d5adce5052af35acf85dc2ed207bb082b7dbf87f25218047b10a024a073
Extract size: 3067 of 268811 bytes (1.1%)

Full text not committed (licence/size); re-fetch from the URL and verify the sha256.
Entries below are the quotes cited by the checklist, each with the line number and section heading in the full snapshot at the hash above. Quote presence in the full snapshot was verified when the checklist was built (see .scratch only); this folder lets a reader re-fetch the source and confirm each quote and location.
Line numbers refer to the full snapshot (as converted text).

-----
L810 | Exit code 0 | "where Claude Code adds plain-text stdout as context that Claude can see and act on."
L821 | Exit code 0 | "Claude never sees stderr from a hook that exits 0."
L821 | Exit code 0 | "To surface a warning to Claude from a `PostToolUse` or `PostToolUseFailure` hook, exit 2 instead so"
L825 | Exit code 2 | "a `PreToolUse` hook blocks the tool call, for example, and a `UserPromptSubmit` hook rejects the prompt."
L991 | JSON output | "Choose one approach per hook: either use exit codes alone for signaling, or exit 0 and print JSON for structured control."
L994 | JSON output | "Print nothing but the JSON object to stdout."
L996 | JSON output | "are capped at 10,000 characters:"
L1000 | JSON output | "Claude Code doesn't ask Claude to read the file, so keep anything Claude must always see within the cap."
L1012 | JSON output | "Has no effect: Claude Code accepts the field but doesn't act on it."
L1013 | JSON output | "Warning message shown to the user."
L1059 | Add context for Claude | "inserts it into the conversation at the point where the hook fired."
L1076 | Add context for Claude | "next to the tool result"
L1092 | Add context for Claude | "It loads without running a script and is the standard place for static project conventions."
L1094 | Add context for Claude | "Write the text as factual statements rather than imperative system instructions."
L1094 | Add context for Claude | "Text framed as out-of-band system commands can trigger Claude's prompt-injection defenses, which causes Claude to surface the text to you instead of treating it as context."
L1096 | Add context for Claude | "`SessionStart` hooks run again on resume with `source` set to `"resume"`"
L1123 | Decision control | "can't replace the prompt; it only injects `additionalContext` alongside it"
L1434 | UserPromptSubmit | "The prompt still reaches Claude without that context."
L1464 | UserPromptSubmit decision control | "Plain stdout and the `additionalContext` value are each injected as a system reminder that starts with the hook's name; Claude reads both."
L1909 | PreToolUse decision control | "`"deny"` prevents the tool call."
L2762 | Stop decision control | "Use `additionalContext` when the hook is working as designed and giving Claude guidance, such as "run the test suite before finishing"."
