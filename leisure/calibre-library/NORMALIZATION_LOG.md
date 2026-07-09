# Calibre Library Normalization Log

Library: `/home/mcooney/Calibre Library` (263 books)

## 2026-07-06 — Final metadata standardization pass (titles, series, identifiers, publishers, languages)

### What was done

Applied the final consolidated metadata proposal covering title prefixes,
series/index corrections, identifier cleanup, publisher canonicalization,
and language tagging — the closing stage of the metadata standardization
project. A fresh backup of the metadata database was taken before any
edits:

- `/home/mcooney/workspace/random_llm_projects/leisure/.scratch/metadata_backup_finalpass_20260706T203328Z.db`

74 distinct books received at least one field edit (several books needed
multiple field updates — title, series, publisher, etc. — applied in a
single `calibredb set_metadata` call per book). Every change was verified
against a re-dump of the library after the pass; 0 mismatches between
proposed and actual values.

### Canonical title-prefix format adopted

`{Series Name} Book {N} - {Title}` (N = plain integer, no zero-padding,
single ` - ` separator). Chosen because, among the pre-existing prefix
styles already baked into 19/34 series-indexed titles, this format was the
most common (8 uses: all 5 Agent Cormac + all 3 Spatterjay titles) — more
than double the next most common variants (Baroque Cycle, LOTR, Thrawn
Trilogy — 3 uses each) — and it avoids the punctuation quirks of the
runner-up styles (no colons, no zero-padding, no hash signs).

### Counts applied

- **Title changes:** 41 (reformats of existing prefixes to the canonical
  style, plus new prefixes added to previously bare titles)
- **Series/index fixes:** 25 (Culture x10, Mickey Haller x3, The Years of
  Lyndon Johnson x4, Discworld index correction, Gibraltar x3 suffix
  strip, Polity Universe rename, Silo assignment, Sword of Shannara and
  Belgariad/Malloreon omnibus reclassification to no-series, plus the
  Night Manager erroneous-series clear below)
- **Manual-review "fix" resolutions applied:** 4 (books 221, 255, 266,
  304 — all already folded into the title/series counts above; the
  remaining manual-review items were correctly left as "leave-as-is" and
  not touched)
- **Identifier fixes:** 3 (books 14, 236 — malformed `urnisbn/<isbn>` keys
  corrected to standard `isbn` key; book 244 — see low-confidence flag
  below)
- **Publisher canonicalizations:** 11 variant groups, 16 books total
  (HarperCollins x4 variants/6 books, Simon & Schuster x3 variants/4
  books, Barnes & Noble, Penguin, Grove/Atlantic, Broad Reach Publishing)
- **Language fixes:** 20 (19 previously-blank + 1 mistagged `rus`→`eng`
  for *The Pragmatic Programmer*), all set to `eng`

### The Night Manager (book 195) — erroneous series correction

Series field was set to `John le Carré` (the author's name) with
`series_index: 14`, evidently meaning "the author's 14th book" rather
than a position in a real series. *The Night Manager* is a standalone
novel with no genuine series. Cleared both `series` and `series_index`
per explicit orchestrator decision. Confirmed via OPF export — no
`<dc:series>` field remains on this record.

### Book 244 identifier — flagged for manual verification

Applied the tentative relabel of the malformed `urn: 1264706017`
identifier to `goodreads: 1264706017` on *Go Like Hell*. **Low
confidence** — the value failed ISBN-10 checksum validation, and
"Goodreads work/book id" was a plausible but unconfirmed guess based on
the raw-numeric pattern common to calibre metadata-plugin imports. **This
needs manual verification** against the book's actual Goodreads/online
record before being treated as settled; if wrong, the key should be
corrected to whatever the real identifier scheme turns out to be (OCLC,
LCCN, ASIN-adjacent, etc.).

### Wool / Silo possible-duplicate-ownership flag

Book 221 (`Wool`, standalone) and book 248 (`Wool Omnibus Edition (Wool
1-5)`) were both metadata-fixed independently and neither was merged or
deleted:

- Book 221 → title `Silo Book 1 - Wool`, series `Silo` #1 (the standalone
  first full novel of Hugh Howey's Silo trilogy: Wool/Shift/Dust).
- Book 248 → left as a no-series omnibus per its existing proposal
  (covers Wool parts 1-5 specifically, not the full 3-book trilogy).

**Flagged for future user review:** whether keeping both records
represents genuine redundant ownership (same content, different
edition/bundling scope) is a content-ownership decision, not a metadata
fix, and was deliberately left untouched here.

### Source files (for re-derivation / audit)

- Proposal applied: `.scratch/calibre_final_metadata_proposal.json`
- Earlier audit (publisher_fixes source list): `.scratch/calibre_metadata_audit.json`
- Pre-edit library dump (ground truth before this pass): `.scratch/calibre_library_dump_final.json`
- Post-edit full library dump: `.scratch/calibre_library_dump_v2final.json`
- DB backup taken before edits: `.scratch/metadata_backup_finalpass_20260706T203328Z.db`
- Generated calibredb command batch: `.scratch/apply_metadata_commands.sh`

## 2026-07-06 — Aggressive cull pass (fold narrow tags into broader parents)

### What was done

Applied the full aggressive-cull proposal: folded 56 narrow/redundant tags
into an existing broader parent tag already present on the same book, for
tags used by only 1-2 books that added no real classification value beyond
the parent. Rule applied: fold a narrow tag into an existing broader parent
already on the book unless the narrow tag is irreplaceable (names a specific
person, place, work, date-scoped historical event, or is a core thematic
subject of the book) — in which case it was explicitly excluded and left
alone.

A fresh backup of the Calibre metadata database was taken before any edits:

- `/home/mcooney/workspace/random_llm_projects/leisure/.scratch/metadata_backup_cull_20260706T200447Z.db`

### Scope of the change

- 29 books had tags edited (56 fold operations; several books had multiple
  narrow tags folded in the same pass)
- Distinct tags: 194 before this pass → 138 after (56 narrow tags removed;
  no fold-into parent introduced a tag that wasn't already in the distinct
  tag set, so the count drops by exactly the fold count)

### Folds applied (56)

Narrow tag → parent it was folded into:

| Narrow tag | Folded into |
|---|---|
| Adventure and adventurers -- Fiction | Historical Fiction |
| Swordsmen -- Fiction | Historical Fiction |
| 1888-1981 | Biography & Autobiography |
| 18th Century | History |
| Wars & Conflicts (Other) | Military |
| Campaigns | Military |
| Regimental histories | Military |
| Adventure fiction | Thrillers |
| Code and cipher stories | Espionage |
| Data encryption (Computer science) | High Tech |
| World Wide Web | High Tech |
| Intrigue | Thrillers |
| Fall of man -- Poetry | Epic |
| Adventure | Science Fiction |
| Popular astronomy & space | Astronomy |
| Astronautics & Space Science | Science |
| Aeronautics | Science |
| TV Tie-Ins | Motion pictures |
| American Horror Fiction | Horror |
| Horror & Ghost Stories | Horror |
| Adventure stories | Thrillers |
| Autobiography | Biography & Autobiography |
| Ball Games: Field & Outdoor | Sports & Recreation |
| Economic Conditions | Business & Economics |
| American football | Football |
| Epic poetry | Epic |
| Barnes And Noble Classics | Classics |
| Criticism | Literary Criticism |
| Literary studies: general | Literary Criticism |
| Literature - Classics | Classics |
| Classic fiction (pre c 1945) | Classics |
| Biography & Autobiography / Personal Memoirs | Biography & Autobiography |
| Computers / Internet / General | Business & Economics |
| Business & Economics / E-Commerce / General (See Also Computers / Electronic Commerce) | Business & Economics |
| Computers / Electronic Commerce (See Also Headings Under Business & Economics / E- | Business & Economics |
| Nuclear | Nuclear Physics |
| Physicists | Physics |
| Science & Technology | Science |
| Political Aspects | History |
| Games & Activities | Role Playing & Fantasy |
| Performing Arts | Fantasy |
| Screenplays | Fantasy |
| Social & Cultural Studies | Social Science |
| Traditional British | Mystery & Detective |
| Legal History | History |
| Law | Criminal Law |
| International | International Finance |
| Social History | History |
| Corporate & Business History | Economic History |
| Cyberspace | Cyberpunk culture |
| Psychological | Horror |
| Islamic Studies | Religion |
| Presidents & Heads of State | Presidents |
| Political Parties | Politics |
| Political Process | Politics |
| Role-playing games; Dungeons & Dragons; fan culture; theory; philosophy; Gygax; Arneson; Blacow; Pulsipher; Lortz; Simbalist; fanzine; zine; Tunnels & Trolls; Chivalry & Sorcery; abilities; alignment; progression; experience; stories; narrative; in character; out of character; dungeon master; referee; role-playing | Role Playing & Fantasy |

Full detail (reasoning per fold, affected book ids/titles) preserved in
`.scratch/calibre_aggressive_cull_proposal.json`.

### Excluded as irreplaceable (50 tags, deliberately left alone)

The following categories of tags were considered for folding but excluded
because they carry real classification value that a parent tag would lose:

- **Specific historical dates/events/campaigns** — e.g. `1610-1643 --
  Fiction`, `1939-1945`, `1939-1945 - Campaigns - Western Front`, `Western
  Front`, `World War II`, `World War`, `United States - Politics and
  Government - 1933-1945`, `Texas - Politics and Government - 1865-1950`.
- **Geography-scoped LOC subdivisions paired with their plain parent on the
  same book** (documented intentional pattern, see below) — e.g. `United
  States - History`, `College sports - United States`, `Football players -
  United States`, `Presidents - United States`, `International Finance -
  History`, `Finance - History`, `Money - History`.
- **Named real people, places, or specific works/franchises** — e.g.
  `Johnson; Lyndon B`, `Adam (Biblical figure) -- Poetry`, `Eve (Biblical
  figure) -- Poetry`, `Bible. Genesis -- History of Biblical events --
  Poetry`, `Baggins; Frodo (Fictitious Character)`, `Middle Earth (Imaginary
  Place)`, `Polity Universe`, `Arkham Horror`, `University of Mississippi -
  Football`, `Assyro-Babylonian`.
- **Core thematic subjects central to a book's actual plot/content**, not
  redundant genre chaff — e.g. `Extraterrestrial beings`, `Interplanetary
  voyages`, `Interstellar communication`, `Space Opera` (all on *Contact*),
  `Television game shows` (*The Running Man*), `Nuclear Warfare` and `Atomic
  Bomb` (*American Prometheus*), `Antiquarian booksellers` and `Rare books`
  variants (already-resolved on *The Shadow of the Wind*).
- **Generic geography (book setting) with no suitable broader parent** — e.g.
  `Spain`, `Barcelona`, `Colombia`, `New York (N.Y.)`, `Middle East`, `Asia`,
  `Europe`, `Great Britain`, `India & South Asia`, `England`.

Full list with per-tag reasoning: `excluded_as_irreplaceable` in
`.scratch/calibre_aggressive_cull_proposal.json`.

### Source files (for re-derivation / audit)

- Proposal (folds/exclusions considered): `.scratch/calibre_aggressive_cull_proposal.json`
- Pre-edit library dump (194-tag ground truth): `.scratch/calibre_library_dump_after3.json`
- Post-edit full library dump: `.scratch/calibre_library_dump_final.json`
- DB backup taken before edits: `.scratch/metadata_backup_cull_20260706T200447Z.db`

See `TAG_TAXONOMY.md` in this directory for the resulting canonical tag list.

## 2026-07-06 — Tag and author normalization pass

### What was done

Ran a one-off cleanup pass over the tag and author metadata to collapse
duplicate/variant tags into single canonical forms, fix two malformed author
names, and delete tags that were data-quality artifacts rather than real
subject headings. No books, formats, or other metadata fields were touched.

A full backup of the Calibre metadata database was taken before any edits:

- `/home/mcooney/workspace/random_llm_projects/leisure/.scratch/metadata.db.backup-20260706T193914Z`

### Scope of the change

- 25 books had tags edited
- 2 books had authors edited
- Distinct tags: 240 before → 212 after
- Distinct authors: 180 before → 178 after

### Tag merges applied (13 groups)

Canonical tag ← variant(s) folded into it:

| Canonical | Variants merged in |
|---|---|
| Science Fiction | Sci-Fi; Science Fiction - General; Fiction - Science Fiction |
| Fantasy | Fiction - Fantasy; Fiction:Fantasy |
| Thrillers | Thriller |
| Mystery & Detective | Detective and mystery stories; Mystery Fiction |
| Biography & Autobiography | Biography And Autobiography |
| Non-Fiction | Nonfiction |
| Historical | Historical - General |
| Economic History | Economics - History |
| Barcelona | Barcelona (Spain) |
| Horror | Horror - General |
| Literature - Classics | Literature: Classics |
| Football | Football - General |
| Sports | Sports - General |

These were all cases of pure capitalization/punctuation/suffix variants of
the same concept (e.g. trailing "- General", `Fiction - X` prefixing, colon
vs space) with no semantic difference — safe to collapse.

### Author merges applied (2)

- `Harris, Robert` → `Robert Harris` (format normalization to the
  library's dominant "First Last" convention)
- `John Le Carre` → `John le Carré` (correct diacritic/capitalization of
  the author's actual name)

### Deletions (11 tags, deleted entirely — not replaced)

**8 orphaned comma-split fragments** — these were not real tags. Calibre's
importer appears to have split original comma-containing subject headings
(e.g. `King, Stephen`, `Moses, Robert`, `Oher, Michael`, `Education, Higher`)
on the comma, leaving two meaningless single-word tag fragments per book
instead of one real tag. Deleted rather than merged because there was no
correct single canonical form to merge them into without reconstructing the
original heading, and reconstructing risked misattribution:

- `King`, `Stephen` (fragment of "King, Stephen" — Stephen King)
- `Moses`, `Robert` (fragment of "Moses, Robert" — subject of Caro's *The
  Power Broker*)
- `Oher`, `Michael` (fragment of "Oher, Michael" — subject of *The Blind
  Side*)
- `Education`, `Higher` (fragment of the LOC heading "Education, Higher")

Note: this is a systemic import bug (comma-splitting), not isolated bad
data. Related fragments flagged but **not** touched in this pass because
they involve more than a simple 2-way split and need manual review:
`Stephen - Prose & Criticism`, `Bachman`, `Richard` (from "Bachman,
Richard", Stephen King's pseudonym) — still present in the library, see
`flagged_for_manual_review` in the proposal file for detail.

**3 junk tags** — not subject headings at all:

- `FIC028010` — a raw, unresolved BISAC subject code (not looked up /
  translated to its human-readable label)
- `26NEWBIE` — workflow/scraper artifact, not a subject
- `ebookoid` — workflow/scraper artifact, not a subject

Note: other raw BISAC codes (`FIC000000`, `FIC031000`, `FIC050000`) and the
`working` tag are still present in the library — they were flagged for
review but not deleted in this pass; treat as open cleanup items, not as
having been judged acceptable.

### Deliberately left alone (not a miss — a decision)

- **`bought-and-paid-for`** — encodes real provenance information (purchase
  status), not a duplicate/junk tag. Keep.
- **BISAC-hierarchy tag pairs**, e.g. `Football` / `Sports`, `Money` /
  `Finance`, `World War` / `1939-1945`, `Rare books` / `Rare books - Spain -
  Barcelona`, `Historical` / `Historical Fiction`, `Biography` /
  `Autobiography` / `Biography & Autobiography` — these look like
  duplicates but are actually different facets of a LOC/BISAC subject
  hierarchy (general topic vs. geographically- or period-scoped variant, or
  genuinely distinct concepts). Collapsing them would destroy real
  granularity. See `flagged_for_manual_review` in
  `calibre_normalization_proposal.json` for the full reasoning on each
  cluster — these need an explicit policy decision on tag granularity, not
  a mechanical merge, and were intentionally left out of scope here.
- **Malformed multi-author strings and `Last, First` outliers** (e.g.
  `Hunt, Andrew;Thomas, David`; `Tom Chivers; and Cat Bohannon;`; several
  `Last, First` single-author entries with no duplicate to merge against) —
  flagged but not fixed; each requires checking against source book
  metadata rather than a blind rename.

### Source files (for re-derivation / audit)

- Proposal (merges/deletions considered): `.scratch/calibre_normalization_proposal.json`
- Pre-edit tag frequency snapshot: `.scratch/calibre_tag_frequency.json`
- Post-edit full library dump: `.scratch/calibre_library_dump_after.json`
- DB backup taken before edits: `.scratch/metadata.db.backup-20260706T193914Z`

See `TAG_TAXONOMY.md` in this directory for the resulting canonical tag list.
