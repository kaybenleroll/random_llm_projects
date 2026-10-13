# Extract of cc-skills.md

Title: Extend Claude with skills
Source URL: https://code.claude.com/docs/en/skills
Fetch time: 2026-10-13T09:10:34Z
Full snapshot: 107130 bytes, sha256 35fd2c11f870fbe1497a53796de31b2a6b760645e724bda58894525356d4602a
Extract size: 4080 of 107130 bytes (3.8%)

Full text not committed (licence/size); re-fetch from the URL and verify the sha256.
Entries below are the quotes cited by the checklist, each with the line number and section heading in the full snapshot at the hash above. Quote presence in the full snapshot was verified when the checklist was built (see .scratch only); this folder lets a reader re-fetch the source and confirm each quote and location.
Line numbers refer to the full snapshot (as converted text).

-----
L375 | Types of skill content | "State what to do rather than narrating how or why, and apply the same conciseness test you would for"
L379 | Frontmatter reference | "in `.claude/commands/` accepts the same fields except `name` and `paths`."
L392 | Frontmatter reference | "Claude Code ignores a field it doesn't recognize without reporting an error."
L392 | Frontmatter reference | "All fields are optional. Only `description` is recommended so Claude knows when to use the skill."
L394 | Frontmatter reference | "Claude Code reads the frontmatter only when the opening `---` is the file's first line."
L401 | Frontmatter reference | "the combined `description` and `when_to_use` text is truncated at 1,536 characters in the skill listing to reduce context usage."
L403 | Frontmatter reference | "Hint shown during autocomplete to indicate expected arguments."
L405 | Frontmatter reference | "Use for workflows you want to trigger manually with `/name`."
L405 | Frontmatter reference | "Also prevents the skill from being"
L407 | Frontmatter reference | "The grant clears when you send your next message."
L409 | Frontmatter reference | "The override applies for the rest of the current turn and isn't saved to settings."
L409 | Frontmatter reference | "a model that auto mode doesn't support also isn't used, and the session keeps its current model."
L410 | Frontmatter reference | "Overrides the session effort level."
L414 | Frontmatter reference | "Hooks that Claude Code registers when the skill is invoked and keeps running for the rest of the session."
L415 | Frontmatter reference | "When set, Claude loads the skill automatically only when working with files matching the patterns."
L418 | Frontmatter reference | "Claude Code accepts the field but doesn't act on it."
L432 | Using skill frontmatter outside Claude Code | "If you include any field the spec doesn't allow, packaging or upload fails with a hard error instead of ignoring the field:"
L590 | Skill content lifecycle | "Claude Code does not re-read the skill file on later turns, so write guidance that should apply throughout a task as standing instructions rather than one-time steps."
L594 | Skill content lifecycle | "keeping the first 5,000 tokens of each. Re-attached skills share a combined budget of 25,000 tokens."
L1162 | Skill not triggering | "Check the description includes keywords users would naturally say"
L1167 | Skill not triggering | "If the frontmatter YAML is malformed, Claude Code loads the skill body with empty metadata"
L1177 | Skill triggers too often | "Make the description more specific"
L1184 | Claude stops following a skill | "Claude Code runs a hook every time its event occurs, such as before each file edit, whether or not Claude is following the skill."
L1185 | Claude stops following a skill | "word the guidance so it applies to the whole task, for example "Run the tests after every edit" rather than "Run the tests"."
L1190 | Skill descriptions are cut short | "The budget scales at 1% of the model's context window."
L1190 | Skill descriptions are cut short | "When the listing overflows, Claude Code drops descriptions starting with the skills you invoke least, so the skills you use most keep their full text."
L1196 | Skill descriptions are cut short | "set low-priority entries to `"name-only"` in"
