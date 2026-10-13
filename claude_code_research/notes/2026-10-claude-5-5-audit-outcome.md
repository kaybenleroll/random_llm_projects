# Claude 5.5 audit outcome (dotfiles#352)

> Outcome record of the audit of the Claude Code setup against Anthropic's 5.5-series guidance. Findings were reviewed adversarially; items that did not survive review are listed so they are not re-raised. Issue numbers are in `kaybenleroll/dotfiles`.

Date: 2026-10-13. Companion notes: `notes/2026-10-claude-5-5-guidance-checklist.md` (the 459-row sourced checklist, row IDs A-/B-/C-/D-), `notes/2026-10-claude-5-5-community-claims.md` (secondary evidence, not used as a source of findings).

## 1. Scope and method

Audit of the global `CLAUDE.md`, `SOUL.md` and `MACHINE.md`, the rules files, all skills, agents, commands and hooks, and the model/effort keys in `settings.json`, against Anthropic's guidance for the 5.5 series (Opus, Sonnet, Haiku) and Fable 5.1. The reference was the 459-row checklist in the sibling note, built from primary sources only. Eight read-only auditors covered always-loaded text, model/effort, hooks and commands, agents and skills. Their per-class reports were returned as text only, so the saved record is a consolidated draft. On 2026-10-13 the draft got one spot-check round against docs and live behaviour, then two stress-test rounds of three reviewers each. A final re-verification pass re-checked every cited path, line, count and quote case-insensitively.

## 2. Outcome in brief

- The emphasis hypothesis is NOT supported. No statement tied to a 5.x generation says to dial back emphasis (the dial-back statements name only Opus 4.5/4.6 and "Claude 4.6 models"). The generation-neutral rows (D-02, D-04, D-05, D-07, D-08, D-13) still apply to all tiers, so HARD RULE density was filed as a low-confidence review (#362), not as a defect.
- The substantive themes were: effort and tier calibration (#356, #357, #358, #359, #364), stale claims about effort and thinking (#357, #358), the compaction re-attach limit for large skills (#360), and literal-reading hazards in skills and commands (#361).
- Smaller defects (hook text, dispatch boilerplate, frontmatter, a stale template) were filed as separate issues after review (#363, #365, #366).
- Raw auditor counts (159 findings; 5 HIGH / 67 MED / 87 LOW) are not reproducible from the saved body. Per-item severity tags are authoritative; the header total is not.

## 3. Issue index

Evidence levels: verified live (a command or payload was run), code read, docs, parser, script, auditor-reported (not independently verified).

| Issue | Title | Priority | Evidence level |
|---|---|---|---|
| #356 | enforce-agent-model hook ignores the per-call Agent effort parameter | P1 | Verified live (synthetic payload) plus code read; real payload field name not confirmed |
| #357 | Correct stale subagent effort claims (per-call parameter, Haiku support) | P2 | Docs for both claims; line numbers auditor-reported |
| #358 | update-config skill: correct effortLevel and thinking-budget guidance | P2 | Docs (model-config page); line numbers auditor-reported |
| #359 | Recalibrate effort settings and pins for Opus 5.5 / Sonnet 5.5 | P2 | Docs (item 1), code read (items 2-3); line numbers auditor-reported |
| #360 | Restructure skills over the 5,000-token post-compaction re-attach limit | P2 | Docs for the limit; sizes measured; byte-to-token conversion (bytes/4) unvalidated; what falls past the cut is auditor-reported |
| #361 | Tighten literal-reading hazards in skills and commands | P3 | Wording verified by read; hazard and 5.5 applicability are auditor-reported (supporting rows are Sonnet 5 / Opus 5) |
| #362 | Review HARD RULE emphasis density and always-loaded size in CLAUDE.md | P3 | Counts auditor-reported; guidance mapping from the checklist; hypothesis not supported |
| #363 | Reflect and reflect-maintain dispatch recipes omit the mandatory polling-loop line | P3 | Script count plus a read of each block; consequence unmeasured |
| #364 | deep-research workflow leaves model and effort unset, against the CLAUDE.md model rule | P3 | Code read; which model runs under opusplan is reasoned, not measured |
| #365 | Fix skill frontmatter: two unparseable descriptions and a dead triggers key | P3 | Parser (item 1), docs plus code read (item 2); runtime effect untested |
| #366 | MACHINE.md.tmpl pins stale kernel and NVIDIA driver versions | P3 | Script (live commands on the host) |

## 4. Verified facts worth keeping

Each with its source type. Re-verify before relying on any of them for a different Claude Code version.

| Fact | Source type |
|---|---|
| Haiku 5.5 supports all five effort levels, with medium as the default. The "Haiku does not support effort" premise in the setup is stale. | Docs (effort page; checklist A-90, A-91, A-96, B-66, C-86) |
| A per-invocation `effort` parameter exists on the Agent tool. It overrides the agent file's field, needs Claude Code v2.1.292+, and applies to non-fork subagents only. | Docs (sub-agents page) plus the Agent tool schema in a live session |
| A user-level `effortLevel` is ignored for Opus 5.5. It still applies to Fable 5.1 and Opus 5; the 5.5 Sonnet and Haiku defaults are their own. | Docs (model-config page) |
| `MAX_THINKING_TOKENS=0` and `alwaysThinkingEnabled: false` have no effect on Opus 5.5, Sonnet 5.5, Haiku 5.5 or Fable. Behaviour with a non-zero budget is inferred, not documented. | Docs (model-config page) |
| After compaction, the first 5,000 tokens of each invoked skill are re-attached, within a 25,000-token combined budget; older skills may be dropped. | Docs (skills page, compaction behaviour) |
| The `enforce-agent-model.py` hook derives effort only from agent-file frontmatter or the session-level payload `effort.level`. It ignores `tool_input.effort`: a synthetic PreToolUse payload with a Sonnet call and per-call xhigh was allowed, while the same call with a top-level xhigh was denied. | Code read plus live synthetic payload |
| The existing hook test `test_tool_input_effort_ignored` asserts the ignore as intended, so the per-call case is currently specified as a non-feature. | Code read |
| PreCompact plain stdout reaches the user and the summariser, not the main model (tracked in #350, out of #352 scope). | Live test (earlier session) plus docs |
| Two frontmatter descriptions (`skills/stress-test/SKILL.md`, `agents/general-purpose-xhigh.md`) fail `yaml.safe_load`; no other frontmatter among 40 skills, 7 agents and 5 commands does. Both still load in a live session. | Parser |
| Unrecognised skill frontmatter keys (`version`, `triggers`) are ignored without error. | Docs (skills page) |

## 5. Refuted or corrected during review

Do not re-raise these without new evidence.

- "Work mode lost" for the wayfinder skill after compaction: refuted. The `## Work mode` heading sits at a measured byte offset of about 17 KB (roughly 4.3k tokens by bytes/4), inside the 5,000-token window. Only the tail beyond about 20 KB is cut (low).
- A pinned-effort claim for `new-feature` (a line near 115): no such pin exists in the file.
- `commands/check-acs.md:82` "poll with short sleeps" conflicting with the foreground-sleep block: refuted. In this environment foreground sleeps of 1 s and 5 s ran; only a 30 s sleep was blocked. At most a wording nit (no interval given).
- The "start with Opus 5.5 for most workloads" quote (B-101) as support for changing the Sonnet-default rule: it compares Opus 5.5 with Fable 5.1, not with Sonnet.
- "Per-call effort pins in skills are dead prose, rated HIGH": refuted by the docs, which confirm the parameter exists. Whether such pins take effect from a skill is a separate open question (section 8).
- The "5 HIGH" header total: not reproducible from the body. Only three items carry explicit HIGH tags in the body (stale Haiku claim, update-config text, compaction limit); the refuted dead-pins claim was HIGH only in prose.
- `model-notes` "covers Fable only": wrong. It also covers Haiku limitations, effort control, the model lifecycle and effort evidence. What it omits is per-tier defaults, skill-frontmatter `model`/`effort` and environment-variable precedence.
- Several smaller corrections to auditor claims: the session-cost nudge is edge-triggered (at most three emissions per session), not every turn; the usage reminder prints percentages, not a countdown; always-on injected hook text measures about 180 B per turn, not about 500 B; the four UserPromptSubmit commands are three scripts plus one inline `date`; the `system_queries` Justfile tables are duplicated by design (a `docs-check` target diffs them); the stress-test frontmatter comment is qualified, not wrong; `test-audit.js` defines 22 principles but four of its strings say 21 (the reverse of the first report).
- Process lesson. An automated pre-verification step (Step 1.5) used literal, case-sensitive matching and produced four false refutations (a Haiku mention in stress-test, the repeated queue-file prohibition, the prose-ban lines, and the "stronger word" lines). A re-run with case-insensitive search, paraphrase checks and reading the surrounding text corrected all four. Treat a literal-match "absent" result as unverified.

## 6. Deliberately not filed

- Owned elsewhere: PreCompact reminder delivery (#350); alias-versus-full-ID pins (#359, acceptance criterion 4); keep-going line for long Sonnet pipelines (#361, acceptance criterion 4).
- SOUL.md terse register versus Fable readability guidance, and the "narrate reasoning" wording: a style call for the owner, and the consequence is a checklist mapping, not a test.
- Ask-first gates in always-loaded text versus Sonnet 5.5 and Fable check-in tendencies: consequence is auditor-reported; owner's call.
- `omitClaudeMd` on the triage agents: the Claude Code docs contradict themselves on whether global memory files are still loaded, so any saving needs a live test first.
- Hook matcher case-sensitivity: docs say matchers are exact strings but not whether that is case-sensitive; untested, low.
- Housekeeping with no verified defect and no Anthropic basis: the dead import in the root `CLAUDE.md`, header-only rules files, 80-byte learnings stubs, unpinned container tag, version-stamped observations, long-skill line counts.
- Reddit evidence: access route unresolved; parked.
- Appendix H and Appendix E items (no Anthropic basis; stale internal evidence): only a selection was saved, because the per-auditor text was returned as text and never written out. The unlisted remainder cannot be reconstructed, so this list is not the complete residue of the audit.

## 7. What conforms (selection)

- Rules that matter are enforced by hooks or handlers (labels, Agent model tier, PR closing keywords, destructive git), except the per-call effort case in #356.
- No "think carefully" or "step by step" lines in skills, agents or `CLAUDE.md` (A-30, D-21, D-22).
- Key prohibitions carry reasons (B-04, D-07).
- `CLAUDE.md` is 59 lines (C-04).
- Most SKILL.md files are under the 5,000-token re-attach limit by the bytes/4 estimate; the exceptions are covered in #360.
- No refusal-steering or retry shims (D-40); verifiers run in fresh context (A-150); reviewers have no Agent tool (A-47..A-49).
- The stress-tester agent runs at Opus medium, matching the 5.5 guidance to restart at medium (A-03, C-91).
- Installed Claude Code is above the minimum versions for the 5.5 models (C-101).

## 8. Open items

- Live test: do per-call effort pins set from a skill on a bare Agent call take effect? Five pin sites exist (the reflect references). Docs describe the parameter; the effect has never been tested. A comment was added to #357; the real PreToolUse payload field name (#356) is the related question.
- Completeness caveat: the saved residue is not the full audit (section 6, last item); severity totals are unverified; byte-to-token figures are an unvalidated estimate; Haiku is the thinnest tier in the checklist.
- Consequences (as opposed to wording) in several unfiled items rest on auditor judgement and were not measured.
- Standing decisions respected: the sequential-thinking use in triage is kept as-is (no removal proposed without a concrete quality complaint); plan mode stays on Opus; SOUL.md style and ask-first gates are the owner's call; edits to the stress-test skill are plan-mode-only.
