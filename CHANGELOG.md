# Changelog

## 0.1.0 — 2026-11-13

Initial public packaging of geo_broll.

- Programmatic 9:16 motion-graphics B-roll (Python + Pillow → ffmpeg), not AI video.
- Scene templates: the v3 geometric/UI set plus the v4 UI-story templates (`live_scan`, `shield`, `artifact_morph`, `merge_toggle`).
- `edit.keep_ranges` trims a source on its original clock; `geo_broll.py edit` can preview the cut. Multiple ranges are concatenated with a short audio/video crossfade.
- `composite.layout`: `full` (default), `split` (whole clip), or `auto` (full-screen hook and close, split-screen only while a cutaway is on).
- Karaoke captions via ASS, optional music bed with sidechain ducking (you supply a track you have rights to).
- `geo_broll.py contact` builds a contact-sheet JPEG for visual QA.
- Configurable safe-area insets and palette; default theme is the dark poster look with six accent colors.
- Bundled SIL OFL fonts (Inter, JetBrains Mono, Liberation Sans/Mono).
- Generic fictional example under `examples/`, driven by a synthetic talking-head stand-in.
