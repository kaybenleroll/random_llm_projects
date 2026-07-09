# Games Setup Summary

## What Was Set Up

### PySolFC (already installed)
- Flatpak: `io.sourceforge.pysolfc.PySolFC`
- Playing Two Suit Spider Solitaire via the app menu

### Simon Tatham's Portable Puzzle Collection

**Install:** `flatpak install flathub uk.org.greenend.chiark.sgtatham.puzzles`

**Launch individual games:**
```
flatpak run --command=loopy uk.org.greenend.chiark.sgtatham.puzzles
flatpak run --command=tracks uk.org.greenend.chiark.sgtatham.puzzles
flatpak run --command=solo uk.org.greenend.chiark.sgtatham.puzzles
flatpak run --command=slant uk.org.greenend.chiark.sgtatham.puzzles
flatpak run --command=bridges uk.org.greenend.chiark.sgtatham.puzzles
flatpak run --command=pearl uk.org.greenend.chiark.sgtatham.puzzles
```

**Launch via GUI launcher:** `/usr/games/sgt-launcher` (pinned to GNOME dock)

**Recommended games to try first:**
- `loopy` — draw a closed loop around dots, logic deduction
- `tracks` — deduce a train track path through a grid
- `solo` — Sudoku plus variants (Killer, Jigsaw, etc.)
- `slant` — fill grid with diagonal lines to form a consistent tree
- `bridges` — connect islands with the right number of bridges
- `pearl` — loop that bends/goes-straight at clue cells

#### Why Flatpak, not the apt version

The apt version (20230410) has a resize/click misalignment bug on this machine. Root cause: 3840x2400 display with 1.333x fractional Wayland scaling + `xwayland-native-scaling` enabled in mutter. GTK3 can only apply integer scale factors, so it rounds 1.333 → 1 and discards the remainder. After a window resize, the Cairo drawing surface and the event coordinate space diverge by that fractional remainder, so clicks land in the wrong place.

The Flatpak version (20241229) runs as a native Wayland GTK3 app — bypasses XWayland entirely and gets proper fractional scaling support from the Wayland compositor. No click misalignment regardless of window size.

#### sgt-launcher fixes applied

The apt `sgt-launcher` had two issues fixed via user-level overrides:

1. **Blank game list** — system `.desktop` files had `Exec=env GDK_DPI_SCALE=2 sgt-loopy` etc. The launcher's binary-existence check passes the whole string as a filename, finds nothing, shows empty list. Fixed by creating `~/.local/share/applications/sgt-*.desktop` overrides with bare `Exec=sgt-loopy-scaled`.

2. **Wrapper scripts** — `~/.local/bin/sgt-*-scaled` scripts now call `flatpak run --command=GAME uk.org.greenend.chiark.sgtatham.puzzles` so the launcher launches the Flatpak versions.

### Aisleriot Solitaire

**Install:** `sudo apt install aisleriot`  
**Launch:** `sol` or from app menu as "Aisleriot Solitaire"  
~80 solitaire card game variants.

## GNOME Dock

sgt-launcher pinned to dock via:
```
gsettings set org.gnome.shell favorite-apps '[..., "org.bluesabre.SgtLauncher.desktop"]'
```

If the icon is not visible, the dock may be scrolled — mousewheel on the dock to reveal it.

## Other Games Available (not yet installed)

Via apt:
- `gnome-mahjongg` — tile-matching, 10–20 min sessions
- `gnome-mines` — minesweeper
- `gnome-sudoku` — already installed
- `gnome-klotski` — sliding block puzzles
- `einstein` — zebra-style logic deduction puzzle (one-off)

Via Flatpak:
- `com.adilhanney.super_nonogram` — Picross/nonogram grid logic
- `org.kde.kmahjongg` — KDE mahjong
