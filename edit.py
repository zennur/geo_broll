"""Timeline editing helpers for geo_broll.

A scene spec may declare source-clock keep ranges; the rest of the pipeline
then works on the concatenated edited timeline.

    "edit": {
      "keep_ranges": [[5.15, 27.80]],
      "crossfade": 0.03,
      "timebase": "source",
      "video_fade_out": 0.28,
      "layout_fade": 0.25
    }

`keep_ranges` are [start, end] intervals in seconds on the *source* clock.
The edited timeline is those intervals concatenated. Internal joins (when
there is more than one range) get a short audio crossfade and a matching
video fade, default 30 ms, so speaker audio stays continuous.

If `edit.keep_ranges` is omitted, `source.offset` + `source.duration` is
treated as a single keep range and existing specs behave as before.

`timebase` (default `"source"` whenever keep_ranges is present) tells the
compositor whether `scenes[].start` / `scenes[].end` are source times
(they will be mapped) or already on the edited clock (`"edited"`).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def keep_ranges_from_spec(spec: dict) -> list[tuple[float, float]]:
    """Return source-clock keep ranges, falling back to source offset/duration."""
    edit = spec.get("edit") or {}
    raw = edit.get("keep_ranges") or edit.get("keep") or None
    if raw:
        ranges = []
        for item in raw:
            if not item or len(item) < 2:
                raise ValueError(f"bad keep range: {item!r}")
            a, b = float(item[0]), float(item[1])
            if b <= a:
                raise ValueError(f"keep range end must be after start: {item!r}")
            ranges.append((a, b))
        ranges.sort()
        for (a, b), (c, d) in zip(ranges, ranges[1:]):
            if c < b:
                raise ValueError(f"keep_ranges overlap: ({a},{b}) and ({c},{d})")
        return ranges

    src = spec.get("source") or {}
    offset = float(src.get("offset") or src.get("start") or 0)
    duration = float(src.get("duration") or 0)
    if duration <= 0:
        path = src.get("path")
        if not path:
            raise ValueError("source.path or edit.keep_ranges required")
        probe = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "json", str(path),
        ])
        duration = float(json.loads(probe)["format"]["duration"]) - offset
    return [(offset, offset + duration)]


def crossfade_from_spec(spec: dict, default: float = 0.03) -> float:
    edit = spec.get("edit") or {}
    if "crossfade" in edit:
        return max(0.0, float(edit["crossfade"]))
    if "audio_crossfade" in edit:
        return max(0.0, float(edit["audio_crossfade"]))
    return default if len(keep_ranges_from_spec(spec)) > 1 else 0.0


def timebase_from_spec(spec: dict) -> str:
    edit = spec.get("edit") or {}
    if edit.get("timebase"):
        return str(edit["timebase"])
    if edit.get("keep_ranges") or edit.get("keep"):
        return "source"
    return "edited"


def edited_duration(ranges: list[tuple[float, float]], crossfade: float = 0.0) -> float:
    if not ranges:
        return 0.0
    total = sum(b - a for a, b in ranges)
    if len(ranges) > 1 and crossfade > 0:
        total -= crossfade * (len(ranges) - 1)
    return total


def source_to_edited(
    t: float,
    ranges: list[tuple[float, float]],
    crossfade: float = 0.0,
) -> float | None:
    """Map a source timestamp into the edited clock, or None if it was trimmed."""
    acc = 0.0
    n = len(ranges)
    for i, (a, b) in enumerate(ranges):
        join = crossfade if (crossfade > 0 and i < n - 1) else 0.0
        if t < a:
            return None
        if t <= b:
            # During a join, the last `crossfade` of this range overlaps the
            # next range in the output; times in that overlap belong to the
            # next range so later events stay monotonic.
            if join and t > b - join and i < n - 1:
                acc += (b - a) - join
                continue
            return acc + (t - a)
        acc += (b - a) - join
    return None


def edited_to_source(
    t: float,
    ranges: list[tuple[float, float]],
    crossfade: float = 0.0,
) -> float | None:
    """Inverse of source_to_edited (points inside a crossfade map to the later range)."""
    acc = 0.0
    n = len(ranges)
    for i, (a, b) in enumerate(ranges):
        join = crossfade if (crossfade > 0 and i < n - 1) else 0.0
        seg = (b - a) - join
        if t <= acc + seg + 1e-9:
            return a + (t - acc)
        acc += seg
    return None


def clip_interval_to_ranges(
    start: float,
    end: float,
    ranges: list[tuple[float, float]],
    crossfade: float = 0.0,
) -> list[tuple[float, float]]:
    """Clip a source [start, end] to kept ranges and return edited-clock intervals."""
    out = []
    for a, b in ranges:
        lo, hi = max(start, a), min(end, b)
        if hi - lo <= 1e-4:
            continue
        s = source_to_edited(lo, ranges, crossfade)
        e = source_to_edited(hi - 1e-6, ranges, crossfade)
        if s is None or e is None:
            continue
        e = e + 1e-6
        if e > s:
            out.append((s, e))
    return out


def remap_scenes(
    scenes: list[dict],
    ranges: list[tuple[float, float]],
    crossfade: float = 0.0,
    timebase: str = "source",
) -> list[dict]:
    """Return scenes with start/end on the edited clock.

    Source times are preserved on `source_start` / `source_end`. Scenes that
    fall entirely outside keep_ranges are dropped. A scene that straddles a
    trim is clipped to the kept overlap.
    """
    out = []
    for scene in scenes:
        s = dict(scene)
        src_a = float(s.get("source_start", s["start"]))
        src_b = float(s.get("source_end", s["end"]))
        if timebase == "edited":
            # already on the edited clock; keep source_* if present
            s.setdefault("source_start", src_a)
            s.setdefault("source_end", src_b)
            out.append(s)
            continue
        s["source_start"] = src_a
        s["source_end"] = src_b
        parts = clip_interval_to_ranges(src_a, src_b, ranges, crossfade)
        if not parts:
            continue
        # A scene split by an internal trim keeps the first kept piece; the
        # renderer is one clip per scene. Callers who need both pieces should
        # author two scenes.
        s["start"], s["end"] = parts[0]
        out.append(s)
    return out


def format_ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def parse_ass_ts(ts: str) -> float:
    h, m, rest = ts.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def remap_ass(
    src: Path,
    dest: Path,
    ranges: list[tuple[float, float]],
    crossfade: float = 0.0,
    duration: float | None = None,
    style_for_time=None,
    title: str | None = None,
    extra_styles: list[str] | None = None,
) -> Path:
    """Shift an ASS file from the source clock onto the edited clock.

    Events that fall entirely outside keep_ranges are dropped. Times that
    overhang a cut are clamped. `style_for_time(edited_start)` may return a
    style name to swap in (e.g. Full vs Split).
    """
    src = Path(src)
    dest = Path(dest)
    if duration is None:
        duration = edited_duration(ranges, crossfade)
    lines = src.read_text().splitlines()
    out = []
    for line in lines:
        if line.startswith("Title:") and title:
            out.append(f"Title: {title}")
            continue
        if extra_styles and line.startswith("Style: Default,"):
            out.append(line)
            for st in extra_styles:
                out.append(st)
            continue
        if not line.startswith("Dialogue:"):
            out.append(line)
            continue
        # Dialogue: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
        prefix, rest = line.split(":", 1)
        parts = rest.split(",", 9)
        if len(parts) < 10:
            continue
        a = parse_ass_ts(parts[1].strip())
        b = parse_ass_ts(parts[2].strip())
        pieces = clip_interval_to_ranges(a, b, ranges, crossfade)
        if not pieces:
            continue
        ea, eb = pieces[0]
        if ea >= duration:
            continue
        eb = min(eb, duration)
        if eb - ea < 0.02:
            continue
        if style_for_time is not None:
            parts[3] = " " + str(style_for_time(ea)).strip()
        parts[1] = " " + format_ts(ea)
        parts[2] = " " + format_ts(eb)
        out.append("Dialogue:" + ",".join(parts))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out) + "\n")
    return dest


def materialize(
    video: Path,
    ranges: list[tuple[float, float]],
    dest: Path,
    crossfade: float = 0.03,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> Path:
    """Write a 1080×1920 trimmed source matching keep_ranges.

    A single range is a frame-accurate trim. Multiple ranges are concatenated
    with an audio/video crossfade of `crossfade` seconds at each join.
    """
    video = Path(video)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps={fps}"
    )
    af = "aformat=channel_layouts=stereo,aresample=48000"

    if len(ranges) == 1:
        a, b = ranges[0]
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-v", "error",
            "-i", str(video),
            "-ss", f"{a:.4f}",
            "-t", f"{(b - a):.4f}",
            "-vf", vf,
            "-af", af,
            "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(dest),
        ]
        subprocess.run(cmd, check=True)
        return dest

    # Multi-range: one decode, per-range trim, then concat or xfade.
    n = len(ranges)
    cf = float(crossfade) if n > 1 else 0.0
    # Guard: a segment shorter than the crossfade cannot be xfaded cleanly.
    if cf > 0:
        for a, b in ranges:
            if (b - a) <= cf * 2:
                raise ValueError(
                    f"keep range {a}-{b} is too short for crossfade={cf}"
                )

    args = [
        "ffmpeg", "-y", "-hide_banner", "-v", "error",
        "-i", str(video),
    ]
    fg = [
        f"[0:v]split={n}" + "".join(f"[vraw{i}]" for i in range(n)),
        f"[0:a]asplit={n}" + "".join(f"[araw{i}]" for i in range(n)),
    ]
    lengths = []
    for i, (a, b) in enumerate(ranges):
        lengths.append(b - a)
        fg.append(
            f"[vraw{i}]trim=start={a:.4f}:end={b:.4f},setpts=PTS-STARTPTS,{vf}[vs{i}]"
        )
        fg.append(
            f"[araw{i}]atrim=start={a:.4f}:end={b:.4f},asetpts=PTS-STARTPTS,{af}[as{i}]"
        )

    if cf <= 0:
        vcat = "".join(f"[vs{i}]" for i in range(n))
        acat = "".join(f"[as{i}]" for i in range(n))
        fg.append(f"{vcat}concat=n={n}:v=1:a=0[v]")
        fg.append(f"{acat}concat=n={n}:v=0:a=1[a]")
    else:
        cur_v, cur_a = "vs0", "as0"
        offset = lengths[0] - cf
        for i in range(1, n):
            nxt_v, nxt_a = f"vx{i}", f"ax{i}"
            fg.append(
                f"[{cur_v}][vs{i}]xfade=transition=fade:duration={cf:.4f}:offset={offset:.4f}[{nxt_v}]"
            )
            fg.append(
                f"[{cur_a}][as{i}]acrossfade=d={cf:.4f}[{nxt_a}]"
            )
            cur_v, cur_a = nxt_v, nxt_a
            if i < n - 1:
                offset += lengths[i] - cf
        fg.append(f"[{cur_v}]format=yuv420p[v]")
        fg.append(f"[{cur_a}]aformat=channel_layouts=stereo[a]")

    args += [
        "-filter_complex", ";".join(fg),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(dest),
    ]
    subprocess.run(args, check=True)
    return dest


def materialize_from_spec(spec: dict, dest: Path, width: int = 1080, height: int = 1920, fps: int = 30) -> Path:
    src = spec.get("source") or {}
    video = Path(src["path"])
    ranges = keep_ranges_from_spec(spec)
    cf = crossfade_from_spec(spec)
    return materialize(video, ranges, dest, crossfade=cf, width=width, height=height, fps=fps)


def prepare_timeline(spec: dict, workdir: Path) -> dict:
    """Ready a spec for compositing on the edited clock.

    Returns a dict with:
      video      – path to use as the talking-head source (trimmed if needed)
      offset     – always 0 when a trim was materialized, else source.offset
      duration   – edited duration
      ranges     – source-clock keep ranges
      crossfade  – join crossfade used
      scenes     – scenes remapped onto the edited clock
      materialized – True if a trimmed intermediate was written
    """
    from style import W, H, FPS

    src = spec.get("source") or {}
    video = Path(src["path"])
    ranges = keep_ranges_from_spec(spec)
    cf = crossfade_from_spec(spec)
    tb = timebase_from_spec(spec)
    duration = edited_duration(ranges, cf)
    scenes = remap_scenes(list(spec.get("scenes") or []), ranges, cf, timebase=tb)

    # Materialize when the keep window is not "the whole file from offset".
    raw_offset = float(src.get("offset") or src.get("start") or 0)
    raw_duration = float(src.get("duration") or 0)
    needs_materialize = bool((spec.get("edit") or {}).get("keep_ranges") or (spec.get("edit") or {}).get("keep"))
    if needs_materialize:
        dest = Path(workdir) / "edited_source.mp4"
        materialize(video, ranges, dest, crossfade=cf, width=W, height=H, fps=FPS)
        return {
            "video": dest,
            "offset": 0.0,
            "duration": duration,
            "ranges": ranges,
            "crossfade": cf,
            "scenes": scenes,
            "materialized": True,
        }
    return {
        "video": video,
        "offset": raw_offset,
        "duration": raw_duration or duration,
        "ranges": ranges,
        "crossfade": cf,
        "scenes": list(spec.get("scenes") or []),
        "materialized": False,
    }


def merge_windows(windows: list[tuple[float, float]], gap: float = 0.05) -> list[tuple[float, float]]:
    """Merge overlapping or nearly-adjacent [start, end] windows."""
    if not windows:
        return []
    items = sorted((float(a), float(b)) for a, b in windows if b > a)
    out = [items[0]]
    for a, b in items[1:]:
        pa, pb = out[-1]
        if a <= pb + gap:
            out[-1] = (pa, max(pb, b))
        else:
            out.append((a, b))
    return out


def split_windows_from_scenes(
    scenes: list[dict],
    default_layout: str = "full",
    cutaway_layout: str = "split",
) -> list[tuple[float, float]]:
    """Edited-clock windows that should use the cutaway (usually split) layout."""
    windows = []
    for s in scenes:
        layout = (s.get("layout") or cutaway_layout).lower()
        if layout != cutaway_layout:
            continue
        windows.append((float(s["start"]), float(s["end"])))
    return merge_windows(windows)
