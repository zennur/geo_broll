# geo_broll

Programmatic motion-graphics B-roll for talking-head short videos.

You transcribe a 9:16 talking-head clip, write a JSON scene spec from what
the speaker actually said, and geo_broll renders sharp UI/motion cutaways
and composites them over the video. **This is not AI video generation.**
Frames are drawn with Python and Pillow and encoded with ffmpeg, so on-screen
labels stay crisp and spelled correctly. Speaker audio stays continuous.

Typical use is a vertical short: a full-screen hook, split-screen graphics
in the top ~55% while the speaker stays in the lower pane during the
explanation, and a full-screen or crisp close.

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) on your `PATH` (needed for render, edit, and composite)
- Optional: the venv packages in `requirements.txt` (Pillow is required to
  render; `faster-whisper` is required only for `transcribe`; `cairosvg` is
  required only to rasterize [Simple Icons](https://simpleicons.org) SVGs)

```bash
git clone https://github.com/<owner>/geo_broll.git
cd geo_broll
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

System Pillow also works for render/composite if you already have it. A
bundled copy of Inter, JetBrains Mono, and Liberation Sans/Mono (all SIL OFL
1.1) lives in `fonts/`, so typography does not depend on a particular machine.

## Quick start (synthetic example)

The repo does not ship private footage. A generator builds a short stylized
avatar clip so the pipeline can be exercised end to end:

```bash
python3 examples/make_demo_source.py
python3 geo_broll.py run examples/example_scenes.json -o examples/example_out.mp4
python3 geo_broll.py contact examples/example_scenes.json --video examples/example_out.mp4 -o examples/example_contact.jpg
```

The example trims lead-in and trailing dead air with `edit.keep_ranges`,
uses `layout: auto` (full-screen hook, split-screen during three UI-story
cutaways), and burns karaoke captions. Intermediate scene mp4s are written
under `out/`.

## Pipeline

Work in this order. Labels and on-screen claims must come from a proofread
transcript, not from a first-pass automatic caption.

### 1. Transcribe

```bash
.venv/bin/python geo_broll.py transcribe /path/to/video.mp4 -o transcript.json
# optional: --offset 3.6 --duration 15.5 --model small --language en
```

The JSON has `segments` with `start`, `end`, `text`, and `words` (`w`,
`start`, `end`) in seconds.

### 2. Proofread

Automatic captions routinely misspeak product names and drop small words.
Correct the transcript before you write a spec or a caption file. Every
label in the scene spec must come from this corrected text (shorten
phrases if needed; do not invent replacements).

### 3. Edit / trim pass

Drop mic-check chatter, false starts, and trailing dead air. Add an `edit`
block with source-clock `keep_ranges`. Scene `start` / `end` can stay on
the original source clock (`timebase: "source"`); `run` and `composite`
map them onto the trimmed timeline.

```json
"edit": {
  "keep_ranges": [[2.0, 14.0]],
  "crossfade": 0.03,
  "timebase": "source",
  "video_fade_out": 0.35,
  "layout_fade": 0.0
}
```

Several ranges are concatenated. Internal joins get a short audio and
video crossfade (default 30 ms when more than one range is present) so
speaker audio stays continuous. Preview just the cut with:

```bash
python3 geo_broll.py edit path/to/spec.json -o trimmed.mp4
```

### 4. Creative director pass

Choose where a graphic actually helps — usually mid-sentence beats, not
the hook or the close. Aim for graphics on about half the runtime. A
cutaway of ~4 s should have two visual beats (a state change around
1.5–3 s). Set `"beats": [0.0, 2.0]` or leave `beats` out and the renderer
will split a cutaway of 3 s or longer in half.

Write the JSON spec (see the schema below). Pick templates that match
what was said, not a generic decoration.

### 5. Motion designer pass

Render typography stills first, then the motion:

```bash
python3 geo_broll.py preview path/to/spec.json -o /tmp/preview
python3 geo_broll.py run path/to/spec.json -o out.mp4
```

Or step by step: `render` (writes one mp4 per scene) then `composite`.

### 6. Composite, layout, and captions

`composite.layout`:

- omitted or `"full"` — cutaways over a full-frame talking head
- `"split"` — split-screen for the whole clip (graphics in the top ~55%,
  speaker cropped into a rounded card in the bottom ~45%)
- `"auto"` or `"mixed"` — full-screen talking head for the hook and close,
  split-screen **only while a cutaway is on**. Adjacent cutaways merge into
  one split window so you never hold an empty dark-grid top pane

`split_y` (default 1056), `speaker_crop` (`y`, `h`), and the inset/gap keys
configure the lower pane. Render split cutaways with `style.safe_bottom` at
the split line so the graphic fills the top pane with padding and no
clipping.

Karaoke captions are an `.ass` file (or an `.srt`, windowed to the clip).
Use a **Full** style (lower safe zone, ~MarginV 250) on the hook/close and
a **Split** style (on the speaker’s chest, below the chin, ~MarginV 220)
during split-screen. Times in the example captions file are on the
**edited** clock.

Optional `composite.music` is mixed under the speaker with sidechain
ducking. Supply a track you have the rights to; this repo does not ship
music.

### 7. Contact-sheet QA

```bash
python3 geo_broll.py contact path/to/spec.json --video out.mp4 -o contact.jpg
```

Inspect the hook, both beats of every cutaway, and the close: face framing,
caption placement (never over the face), no clipping, no empty top pane.

## Scene spec

```json
{
  "version": 5,
  "source": { "path": "talking_head.mp4", "offset": 0.0, "duration": 20.0 },
  "output": "out.mp4",
  "edit": {
    "keep_ranges": [[1.5, 18.0]],
    "timebase": "source"
  },
  "style": {
    "safe_top": 48,
    "safe_bottom": 1036,
    "safe_left": 40,
    "safe_right": 1040
  },
  "composite": {
    "captions": "captions.ass",
    "layout": "auto",
    "split_y": 1056,
    "speaker_crop": { "y": 320, "h": 864 }
  },
  "scenes": [
    {
      "id": "s1_scan",
      "template": "live_scan",
      "start": 4.5,
      "end": 8.0,
      "beats": [0.0, 1.4, 2.4],
      "title": "short heading taken from the transcript"
    }
  ]
}
```

With `timebase: "source"` (the default whenever `keep_ranges` is set),
`scenes[].start` / `end` are on the original source clock. Use
`"edited"` if you already authored times on the trimmed clock.

Relative paths in `source.path`, `composite.captions`, `composite.music`,
and `output` are resolved against the spec file’s directory and the
current working directory.

`style.safe_*` insets tighten the content box. Defaults keep the top ~12%
and the bottom ~20% clear for platform UI and captions; the example tightens
`safe_bottom` to the split line.

### Style and palette

The default look is a dark poster theme: black / near-black surfaces, a
faint drifting grid, and six accent colors.

| Name | Hex |
| --- | --- |
| blue | `#1580FF` |
| orange | `#FF6A00` |
| pink | `#FF2E9A` |
| amber | `#FF9A00` |
| teal | `#00B8A5` |
| violet | `#8B5CF6` |

Override any entry (or add keys) from the spec:

```json
"style": {
  "palette": {
    "blue": "#1580FF",
    "card": "#111318"
  }
}
```

Values may be `#RRGGBB` or RGB tuples. The rest of the palette is left as
the dark-theme default.

## Content rules

- **No invented statistics.** A ticking `value` / counter / percent is
  allowed only when that number was spoken. Counters may also count items
  the speaker actually listed. Relative bar heights (one bar taller, no
  numerals) are a visual metaphor for “more”, not a statistic — never
  label them with invented figures.
- **Labels come from the transcript.** Shorten phrases, but do not invent
  agent names, roles, brands, or quotes. Generic QA-runner UI chrome
  (module names, branch pills, stylized snippets) is allowed as storytelling
  dress, not as claimed product data.
- **Logos only for named brands.** Set `"logo": "instagram"` (or a label
  that matches a known [Simple Icons](https://simpleicons.org) slug) to
  pull a CC0 glyph, cached under `icons/`. Unknown names and **Grok Bot**
  always render as a styled text badge, never a third-party mark. Do not
  add platform logos the speaker did not name.
- Do not repeat the caption track word-for-word as a headline if a short
  label will do.

## Template catalog

All templates use the dark theme above, Inter (Liberation Sans fallback),
and JetBrains Mono for code in the UI-story templates. Content stays inside
the configured safe area.

### Geometric / UI cards

- **`network`** — org-chart or node network. Center card, staggered
  children, orthogonal connectors. Optional `outputs` on beat 2.
- **`pipeline`** — vertical step flow with a traveling packet. Step
  numbers are structural (1, 2, 3), not claimed statistics. Beat 2
  emphasizes the last step.
- **`compare`** — two sides, before/after or a spoken conjunction
  (`or`, `and`, `to`, `vs`) only if that word is in the transcript.
- **`cards`** — keyword or stat cards. Set `value` / `from` / `suffix`
  only for a number the speaker said.
- **`checklist`** — rows that tick off in sequence. Beat 2 finishes
  remaining checks.
- **`emphasis`** — a large phrase in the center, with optional support
  chips. Words reveal in order.
- **`counter`** — a large ticking number, only for a spoken figure.
- **`donut`** / **`progress`** — circular or bar progress. Do not label
  with an invented percent.
- **`gauge`** — needle swing; labels from the spec / transcript.
- **`before_after`** — two-state card, state change on beat 2.
- **`chat_mockup`** — a message thread. `messages` are only phrases from
  the spec / transcript.
- **`profile_card`** — identity card with optional logo/badge.
- **`icon_grid_highlight`** — a grid of tools or roles; one cell
  highlights on the later beat.
- **`bar_compare`** — unlabeled relative bars (visual “more”, no invented
  figures).
- **`logo_card`** — a featured named brand (Simple Icons) plus supporting
  text.
- **`feature_grid_checks`** — a grid of features that tick on.
- **`messy_to_clean`** — a cluttered board that resolves into a clean
  layout on beat 2.
- **`doc_timeline`** — a document or timeline that fills in over beats.

### UI-story templates

Reusable product-UI scenes (good for software / QA explainers):

- **`live_scan`** — a QA runner window, a scanner beam, and pass/fail
  ticks. Fields: `title`, `kicker`, `summary`, `modules[]` (`label`,
  `sub`, `color`, `snippet`), `fail_index`.
- **`shield`** — issues stream from a codebase toward a users device; a
  shield traps them in a Caught tray and the device goes Safe. Fields:
  `title`, `caught_label`, `safe_label`, `bugs`.
- **`artifact_morph`** — a bug ticket wipes into a pull-request card.
  Fields: `title`, `ticket_title`, `ticket_sub`, `assignee`,
  `pr_title`, `branch`, `checks`.
- **`merge_toggle`** — a reviewer toggle (left / right), an Approved
  stamp, and branch lines that meet at a Merged badge. Fields: `title`,
  `left`, `right`, `pr_title`, `branch`, `checks`, `merged_label`.

See `examples/example_scenes.json` for a complete `live_scan` + `shield` +
`merge_toggle` spec with `keep_ranges` and `layout: auto`.

## Commands

```bash
python3 geo_broll.py transcribe VIDEO -o transcript.json
python3 geo_broll.py edit SPEC.json -o trimmed.mp4
python3 geo_broll.py preview SPEC.json -o /tmp/preview
python3 geo_broll.py render SPEC.json -o /tmp/clips
python3 geo_broll.py composite SPEC.json --clips /tmp/clips -o out.mp4
python3 geo_broll.py run SPEC.json -o out.mp4
python3 geo_broll.py contact SPEC.json --video out.mp4 -o contact.jpg
```

`run` writes intermediate scene mp4s under `out/<output-stem>/` unless you
pass `--clips`.

Helpers live in `edit.py` (`keep_ranges_from_spec`, `source_to_edited`,
`materialize`, `remap_ass`, `remap_scenes`) so the trim step stays generic.

## License

The geo_broll source is MIT, copyright Zehra Nur. Bundled fonts remain
under the SIL Open Font License 1.1 (see `fonts/`). Brand marks fetched
into `icons/` come from Simple Icons (CC0) and are not redistributed in
this repository.
