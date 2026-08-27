# TV/film recommendations

This is a small, data-driven workspace for maintaining TV and film recommendations.

## Project guidance

Read [`CLAUDE.md`](CLAUDE.md) before working in the project. It contains the existing recommendation-session rules and is retained for Claude Code compatibility. `AGENTS.md` provides the corresponding entry point for Codex.

## Data files

- [`data/films_seen.json`](data/films_seen.json) is the source of truth for suggested films and whether they have been seen.
- [`stremioExport.json`](stremioExport.json) is a raw Stremio export used as personal viewing context. It may contain credentials and should not be shared or edited casually.
- [`gemini_chat_recommendations.md`](gemini_chat_recommendations.md) contains longer-lived viewing preferences and thematic analysis.
- `curated_recommendations_*.md` files are dated recommendation outputs and historical context.

## Recommendation workflow

1. Read `data/films_seen.json` before making recommendations.
2. Do not resurface films marked `"seen": true`.
3. Preserve the year and identity of a specific film, especially when originals and remakes exist.
4. Update the seen list only after the user explicitly confirms that a title has been watched.

## Working with Codex

Start Codex from this directory, or use:

```bash
codex --cd tvfilm_recommendations
```

After editing JSON, validate it with:

```bash
jq -e . data/films_seen.json
```

There is currently no application build or test suite; this repository is primarily a curated data and notes workspace.
