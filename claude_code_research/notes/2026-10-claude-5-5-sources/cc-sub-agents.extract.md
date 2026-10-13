# Extract of cc-sub-agents.md

Title: Create custom subagents
Source URL: https://code.claude.com/docs/en/sub-agents
Fetch time: 2026-10-13T09:10:34Z
Full snapshot: 108551 bytes, sha256 dd3f22aa021a3525f48227321c34eab28b322d7ab77cb3d5fc01ddd048e8f6ea
Extract size: 2412 of 108551 bytes (2.2%)

Full text not committed (licence/size); re-fetch from the URL and verify the sha256.
Entries below are the quotes cited by the checklist, each with the line number and section heading in the full snapshot at the hash above. Quote presence in the full snapshot was verified when the checklist was built (see .scratch only); this folder lets a reader re-fetch the source and confirm each quote and location.
Line numbers refer to the full snapshot (as converted text).

-----
L307 | Write subagent files | "to use: `sonnet`, `opus`, `haiku`, `fable`, a full model ID such as `claude-opus-5-5`, or `inherit`."
L315 | Write subagent files | "Set to `true` to launch this subagent without the user, project, and local CLAUDE.md files"
L316 | Write subagent files | "Options: `low`, `medium`, `high`, `xhigh`, `max`; available levels depend on the model."
L322 | Write subagent files | "Write `cacheTtl` inside the `experimental` map, not at the top level of the frontmatter."
L340 | Subagent files Claude Code skips | "Claude Code skips the file and writes the reason to the debug log."
L370 | Choose a model | "the subagent runs on the main conversation's exact model, including any `[1m]` suffix"
L377 | Choose a model | "Before v2.1.251, `CLAUDE_CODE_SUBAGENT_MODEL` came first in this order and overrode both the per-invocation parameter and the frontmatter, including `model: inherit`."
L390 | Choose a model | "There is no per-subagent thinking setting."
L826 | Understand automatic delegation | "To encourage proactive delegation, include phrases like "use proactively" in your subagent's description field."
L828 | Understand automatic delegation | "Keep descriptions brief: Claude Code shows a startup warning when your subagents' combined descriptions pass"
L1072 | What loads at startup | "The built-in Explore and Plan agents skip this."
L1079 | What loads at startup | "The main conversation still has your full CLAUDE.md when it reads these subagents' results, so most rules don't need to reach the subagent itself."
L1079 | What loads at startup | "restate it in the prompt you give Claude when delegating."
