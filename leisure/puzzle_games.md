# Linux Puzzle Games — Research Report

*Research run: 2026-06-14. 107 agents, 24 sources fetched, 25 claims adversarially verified.*

---

## What You Already Have

- **Simon Tatham's Portable Puzzle Collection** (`sgt-puzzles`) — the benchmark; already installed
- **Aisleriot** — GNOME solitaire, ~80 variants
- **GNOME Sudoku**, **Hitori**, **Atomix**, **Hex-a-hop**, **BrainParty**, **2048-qt** — already installed

---

## Community Top Pick

### Patrick's Parabox — *Recursive Sokoban*
**99% positive on Steam (4,735+ reviews). The clearest community consensus pick for Linux puzzle gaming.**

A mind-bending twist on Sokoban where boxes contain entire levels, and you can push yourself into boxes to recurse through puzzles. Nothing else does what this does.

- Native Linux build, Steam Deck Playable
- **Steam:** `store.steampowered.com/app/1260520/` — ~£15
- **itch.io:** `patricktraynor.itch.io/patricks-parabox` — $20 minimum (pay-what-you-want above)

---

## Free Options by Genre

### Sokoban
| Game | Install | Notes |
|------|---------|-------|
| **Simple Sokoban** | `flatpak install flathub io.osdn.simplesok` | Clean, minimal; good starting point |
| **Berusky** | `sudo apt install berusky` | Sokoban variant with a visual style; bug theme |
| **Fish Fillets NG** | `sudo apt install fillets-ng` | Sokoban-style with story and production quality |
| **xsok** | `sudo apt install xsok` | Classic bare-bones Sokoban for X11 |

### Logic Puzzles (SGT-adjacent)
| Game | Install | Notes |
|------|---------|-------|
| **Einstein** | `sudo apt install einstein` | Constraint logic (Zebra puzzle style); good brain workout |
| **Pipewalker** | `sudo apt install pipewalker` | Pipe-connection puzzle; similar to sgt-net |
| **Enigma** | `sudo apt install enigma` | Marble physics/logic; Oxyd family. One of the better apt games |
| **KNetwalk** | `sudo apt install knetwalk` | Wire puzzle; KDE but runs fine on GNOME |

### Nonograms / Picross
| Game | Install | Notes |
|------|---------|-------|
| **Picmi** | `flatpak install flathub org.kde.picmi` | KDE project, actively maintained (2024 releases); recommended starting point |
| **Super Nonogram** | `flatpak install flathub com.adilhanney.super_nonogram` | Procedurally generated, unlimited puzzles, gets harder as you go |

*Note: FreeNono (sometimes recommended online) is effectively dead — 5 GitHub stars, last updated 2021, not available via apt. Skip it.*

### Jigsaw
| Game | Install | Notes |
|------|---------|-------|
| **Palapeli** | `sudo apt install palapeli` | KDE jigsaw; decent quality |
| **Tetzle** | `sudo apt install tetzle` | Alternative jigsaw; simpler |

### Physics Puzzles
| Game | Install | Notes |
|------|---------|-------|
| **Numpty Physics** | `flatpak install flathub io.thp.numptyphysics` | Draw shapes to solve physics puzzles; quite different feel |

### Sliding Tile / Other
| Game | Install | Notes |
|------|---------|-------|
| **GNOME Klotski** | `sudo apt install gnome-klotski` | Sliding block (Rush Hour style) |
| **GNOME Taquin** | `flatpak install flathub org.gnome.Taquin` | Tile-sliding; clean GNOME quality |

### Solitaire (Beyond Aisleriot)
| Game | Install | Notes |
|------|---------|-------|
| **KPatience** | `flatpak install flathub org.kde.kpat` | KDE's solitaire suite; different set of variants to Aisleriot |

---

## Paid Options Worth Considering

### Sokoban
- **Bonfire Peaks** (~$20, itch.io / Steam) — Voxel-art sokoban; polished, well-reviewed. DLC available ('Lost Memories', ~$15). Native Linux build. `draknek.itch.io/bonfire-peaks`
- **Puzzledorf** (Steam) — Added native Linux support July 2024; Steam Deck compatible. Vibrant visual style.

### Nonograms
- **Pictopix** (Steam, ~96% positive) — Leading paid nonogram on Linux. Confirmed Ubuntu 12.04+ support. `store.steampowered.com/app/568320/`

---

## Best Discovery Point Going Forward

**Flathub Logic Games subcategory** lists 53 installable puzzle games covering most genres above, all one `flatpak install` away:

```
https://flathub.org/apps/category/Game/subcategories/LogicGame/1
```

Worth browsing directly when you want to explore further.

---

## Quick Priority Install List

If I had to pick five things to try first:

1. `flatpak install flathub org.kde.picmi` — nonograms, if you've never played them
2. `sudo apt install enigma` — best of the apt logic games by quality
3. `sudo apt install einstein` — constraint puzzle; short sessions, satisfying
4. **Patrick's Parabox** (Steam/itch.io) — if you want to spend money on one thing, this is it
5. `flatpak install flathub io.osdn.simplesok` — clean Sokoban before committing to Bonfire Peaks

---

*Caveats: Community forum data (Reddit, BoardGameGeek) wasn't directly fetchable during verification — consensus claims rest on Steam review data and GamingOnLinux. Prices are minimums. Flathub count (53) will drift.*
