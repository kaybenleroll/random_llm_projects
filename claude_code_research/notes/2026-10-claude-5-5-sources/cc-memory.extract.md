# Extract of cc-memory.md

Title: How Claude remembers your project
Source URL: https://code.claude.com/docs/en/memory
Fetch time: 2026-10-13T09:10:34Z
Full snapshot: 51556 bytes, sha256 52c9ce2203d522ab02f6f5d9e6bede9998a9a71c9b2bf58fd237ca689e013161
Extract size: 3681 of 51556 bytes (7.1%)

Full text not committed (licence/size); re-fetch from the URL and verify the sha256.
Entries below are the quotes cited by the checklist, each with the line number and section heading in the full snapshot at the hash above. Quote presence in the full snapshot was verified when the checklist was built (see .scratch only); this folder lets a reader re-fetch the source and confirm each quote and location.
Line numbers refer to the full snapshot (as converted text).

-----
L24 | CLAUDE.md vs auto memory | "Claude treats them as context, not enforced configuration."
L24 | CLAUDE.md vs auto memory | "The more specific and concise your instructions, the more consistently Claude follows them."
L51 | When to add to CLAUDE.md | "If an entry is a multi-step procedure or only matters for one part of the codebase, move it to a"
L80 | Write effective instructions | "Write instructions that are concrete enough to verify:"
L88 | Write effective instructions | "target under 200 lines per CLAUDE.md file. Longer files consume more context and reduce adherence."
L88 | Write effective instructions | "help you organize a long file but don't reduce its context cost, because imported files also load at launch."
L89 | Write effective instructions | "Organized sections are easier for Claude to follow than dense paragraphs."
L90 | Write effective instructions | "if two instructions contradict each other, Claude may pick one arbitrarily."
L94 | Audit your instruction files | "Claude looks for problems such as instructions written for older models, references to files or commands that don't exist, and files that contradict each other."
L144 | How CLAUDE.md files load | "All discovered files are concatenated into context rather than overriding each other."
L146 | How CLAUDE.md files load | "Instead of loading them at launch, Claude Code loads each one once Claude reads, writes, or edits another file in that subdirectory."
L150 | How CLAUDE.md files load | "Block-level HTML comments (`<!-- maintainer notes -->`) in CLAUDE.md files are stripped before the content is injected into Claude's context."
L171 | Organize rules with `.claude/rules/` | "Rules load into context every session or when matching files are opened."
L188 | Set up rules | "are loaded at launch with the same priority as `.claude/CLAUDE.md`."
L241 | API Development Rules | "`paths` is the only field Claude Code reads from a rule; any other field is ignored without an error."
L247 | API Development Rules | "If the YAML between the markers doesn't parse, Claude Code ignores the frontmatter and loads the rule as if it had no `paths`."
L546 | How it works | "The first 200 lines of `MEMORY.md`, or the first 25KB, whichever comes first, are loaded at the start of every conversation."
L578 | Claude isn't following my CLAUDE.md | "CLAUDE.md content is delivered as a user message after the system prompt, not as part of the system prompt itself."
L587 | Claude isn't following my CLAUDE.md | "Check whether your instruction competes with guidance Claude Code adds on its own."
L589 | Claude isn't following my CLAUDE.md | "Hooks execute as shell commands at fixed lifecycle events and apply regardless of what Claude decides to do."
L625 | Instructions seem lost after `/compact` | "Project-root CLAUDE.md survives compaction: after `/compact`, Claude re-reads it from disk and re-injects it into the session."
