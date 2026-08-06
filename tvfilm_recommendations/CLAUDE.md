# tvfilm_recommendations
TV/film recommendation tooling.

## Seen/unseen tracking

`data/films_seen.json` is the source of truth for which suggested films the user has already seen. Read it at the start of a recommendation session to avoid resurfacing seen titles; update it whenever the user confirms a title watched (in conversation, or via the watchlist artifact's "Copy JSON" export pasted back into the session — the artifact itself only persists to browser localStorage, which is not visible across sessions).
