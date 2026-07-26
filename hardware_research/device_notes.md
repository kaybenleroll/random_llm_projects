# Device Notes: Samsung Galaxy Tab A9

## Purchased Device
**Samsung Galaxy Tab A9 8.7" (SM-X110)** — bought following the recommendation in
[dublin_tablet_research_2026-04-22.md](dublin_tablet_research_2026-04-22.md), which called it
"the clear winner for performance and longevity."

- **Chipset:** MediaTek Helio G99 (Mali-G57 MC2 GPU)
- **Dimensions:** 210mm × ~124–129mm × 6.9mm
- **HEVC/H.265 hardware decode:** Supported, capped at 2K@30fps / 1080p@60fps / 720p@120fps.
  Hardware decoder is **8-bit HEVC only** — no hardware path for 10-bit HEVC (Main10), which is
  common in scene-release video files.

## Known Issue: Blank video in Stremio with H.265 files
**Symptom:** Audio plays, video stays blank/black when playing certain `.mkv`/H.265 files in Stremio.

**Root cause:** 10-bit HEVC content exceeds the Helio G99's hardware decoder capability. Stremio's
default internal player engine (ExoPlayer) relies on the device's hardware MediaCodec path and
fails ungracefully on unsupported 10-bit streams. This is a documented, recurring issue across
MediaTek-chipset Android devices (see Stremio's own GitHub bug tracker, e.g. issues #319, #2026, #175).

**Attempted fix that did NOT work:** Switching Stremio's internal player engine to VLC
(Settings → Player → Player engine). Still blank — libVLC on Android also leans on hardware
MediaCodec decode and doesn't reliably fall back to software for 10-bit HEVC.

**Fix that worked:** Switching Stremio's internal player engine to **MPV**
(Settings → Player → Player engine → MPV). MPV uses libmpv, which decodes via FFmpeg/libavcodec —
a much more robust software fallback for 10-bit HEVC than ExoPlayer or libVLC's hardware-first paths.

**Important distinction:** This is Stremio's *internal player engine* setting (ExoPlayer / VLC / MPV
choice, added to Stremio mid-2026), which renders inside Stremio's own UI. It is **not** the
separate "external player" feature, which hands the file off via Android intent to a standalone
app (e.g. a separately installed VLC or mpv-android app) and exits Stremio's UI. No external app
installation was needed — the fix is purely a Stremio in-app settings change.

## Superseded research
- [dublin_small_tablet_research_2026-06-28.md](dublin_small_tablet_research_2026-06-28.md) — broader
  market survey (CeX, DoneDeal, Adverts.ie, Refurbed.ie, Back Market, new retail) done after the
  purchase, exploring alternatives/companion devices. Notable finding: Samsung Galaxy Tab A11 8.7"
  (successor to the A9, released Oct 2025) is now the current-generation equivalent, ~€179 new.
