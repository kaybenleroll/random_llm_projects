# Research Sources Playbook — Claude Code / Dev-Tool Cost & Context Research

Purpose: a reusable, self-contained checklist for researching Claude Code (or similar dev-tool) topics that need real-world/community signal, not just official docs. Built and validated 2026-07-03 while researching token-economy practices. Hand this to a future subagent verbatim — it should be able to execute every entry without re-deriving strategy.

Format per entry: **Source — what it's good for — exact access pattern — notes from actual use.**

---

## HIGH-SIGNAL — use these

### 1. Hacker News via Algolia API (WebFetch)
- **Good for:** Technical practitioner discussion, tool launches with cost/context claims in the title, comment threads with real numbers (token counts, $ saved, before/after benchmarks).
- **Access pattern:**
  - Stories: `WebFetch("http://hn.algolia.com/api/v1/search?query=<url-encoded terms>&tags=story", prompt)`
  - Comments: same URL with `&tags=comment`
  - No `site:` restriction needed — this is a direct API, not going through WebSearch.
  - Good query terms found to work: `claude code token cost`, `claude code compaction prompt caching`, `claude code subagent context`.
- **Notes from use:** Consistently returned relevant, concrete results (tool names, point/comment counts, direct quotes) — e.g. surfaced CodeBurn (token-usage-by-task analyzer, "56% of spend was on conversation turns with no tool usage"), a context-pollution MCP multiplexer claiming 19x reduction, and a token-tracking dashboard. This is the single best-performing source in this pass. Always ask the WebFetch prompt to extract **story title + URL + points + comments + one relevant quote/stat** — that shape reliably strips the noise.

### 2. GitHub REST Search API for anthropics/claude-code issues (Bash + curl, no auth needed for public search)
- **Good for:** Ground-truth bug reports and feature requests about compaction, context, token usage — including real user-reported pain points (compaction corruption, no persistent memory, etc.) with comment counts as a signal-strength proxy.
- **Access pattern:**
  ```
  curl -s "https://api.github.com/search/issues?q=repo:anthropics/claude-code+<TERM>+in:title,body&sort=comments&order=desc&per_page=10"
  ```
  Pipe through `python3 -c "import json,sys; d=json.load(sys.stdin); [print(i['number'], i['title'], i['html_url'], 'comments:', i['comments']) for i in d['items']]"` to get a scannable list instead of raw JSON.
  Fetch one issue body: `curl -s "https://api.github.com/repos/anthropics/claude-code/issues/<NUMBER>"` then `.body` field.
- **Notes from use:** Worked immediately, no auth required for public read search. Sorting by `comments` desc is the key trick — surfaces the highest-engagement threads first (found a 176-comment auto-compact bug thread, a 61-comment "Feature Request: Persistent Memory Across Context Compactions" thread with a detailed field report of a 3-tier memory architecture someone built by hand). Rate limits apply unauthenticated (60/hr) — batch queries, don't loop per-term.
- **Caveat:** `anthropics/claude-code` GitHub **Discussions are disabled** (confirmed via API: `410 Discussions are disabled for this repo`) — don't waste a call on `/discussions`; issues are the only GitHub-native community channel for this repo.

### 3. WebSearch with no `site:` restriction, phrased as a normal query (not a Boolean/site query)
- **Good for:** Surfacing blog posts, newsletters, and aggregator content that themselves summarize or quote Reddit/Discord/Twitter discussion — this is the practical workaround for the Reddit block (see Skip list below). Also directly surfaces dedicated cost-optimization guides (KDnuggets, Analytics Vidhya, Substack, MindStudio, etc.) that read as practitioner-sourced rather than official-doc restatement.
- **Access pattern:** `WebSearch({query: "Claude Code reduce token usage subagents reddit"})` — include the word "reddit" or "community" in the query text itself (not as a `site:` filter) to bias toward aggregator/summary content that references those communities.
- **Notes from use:** Reliably surfaced high-quality, concrete guides: "7 Practical Ways to Reduce Claude Code Token Usage" (KDnuggets), "23 Tips for Smart Claude Code Token Saving" (Analytics Vidhya), "Claude Code Token Optimization: Stop the $1,600 Bill" (Substack). These read as genuinely practitioner-sourced (specific commands, specific env vars, specific benchmarked %s) rather than marketing copy. Always WebFetch the actual article afterward — the WebSearch snippet alone is too thin to cite confidently.

### 4. WebFetch on the specific articles surfaced by #3
- **Good for:** Extracting the actual concrete tips/commands/numbers once WebSearch has located a promising URL.
- **Access pattern:** `WebFetch(url, "extract concrete/actionable tips, especially anything with specific numbers, env vars, or commands, and flag anything that reads as practitioner experience rather than a restatement of official docs")`
- **Notes from use:** This is where the real payload lives — e.g. `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70` env var, the `grep -A5 -E "FAIL|ERROR"` log-prefiltering pattern, "keep CLAUDE.md under 200 lines," "check `/context` before optimizing." Treat env-var-level claims from these blogs as **unverified against official docs** unless cross-checked — flag rather than assert as fact.

---

## LOW-SIGNAL / SKIP — tried, not worth repeating

### Reddit direct access (both `site:reddit.com` in WebSearch query text, and `allowed_domains: ["reddit.com"]` parameter)
- **Result:** Zero results both ways. The `allowed_domains` parameter attempt returned an explicit **API error**: `"The following domains are not accessible to our user agent: ['reddit.com']"` (Anthropic's crawler is blocked by Reddit's robots.txt / site policy — this is a hard block, not a fluke).
- **Verdict:** Do not spend time on direct Reddit queries via WebSearch or WebFetch — it will not work. If Reddit-sourced opinion is specifically required, the only viable path is a query phrased to surface *articles that quote Reddit threads* (see High-Signal #3) — you get secondhand Reddit signal, never the thread itself.

### `site:reddit.com` combined with multi-term Boolean-style queries generally
- **Result:** WebSearch appears to silently return zero results for `site:` restricted queries on blocked domains rather than erroring — easy to mistake for "no discussion exists" when it's actually "domain inaccessible." Don't conclude "no community discussion on this topic" just because a `site:reddit.com` search came back empty — try High-Signal #3 instead before concluding the topic isn't discussed.

### GitHub Discussions tab for anthropics/claude-code
- **Result:** Disabled entirely (confirmed via API, not a search fluke). Don't attempt `gh api repos/anthropics/claude-code/discussions` or the Discussions UI — go straight to Issues.

### X/Twitter
- **Not tested this pass** — WebSearch did not surface any X/Twitter links organically for these queries, and there's no equivalent free API access analogous to HN Algolia. Deprioritize unless a query specifically returns X links; don't proactively try to construct X search URLs (they require auth to view most content anyway).

---

## Quick-reference query bank (proven to return usable results, reuse verbatim as starting points)

- HN Algolia: `claude code token cost`, `claude code compaction prompt caching`, `claude code subagent context`
- GitHub issues: `repo:anthropics/claude-code compaction in:title,body`, `repo:anthropics/claude-code token cost in:title,body` (both sorted `sort=comments&order=desc`)
- WebSearch: `Claude Code reduce token usage subagents reddit`, `Claude Code token cost optimization dev.to blog post`, `Claude Code context window management tips community reddit` (this last one returned nothing directly but is worth retrying periodically as indexing changes)
