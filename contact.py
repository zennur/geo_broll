"""Build a contact-sheet JPEG from a composited render and its scene spec."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from edit import (
    keep_ranges_from_spec,
    crossfade_from_spec,
    remap_scenes,
    timebase_from_spec,
    edited_duration,
)
from style import W, H, LIBERATION_BOLD, LIBERATION


def _probe_duration(video: Path) -> float:
    import json
    probe = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(video),
    ])
    return float(json.loads(probe)["format"]["duration"])


def _pick_times(spec: dict, duration: float) -> list[tuple[str, float]]:
    ranges = keep_ranges_from_spec(spec)
    cf = crossfade_from_spec(spec)
    tb = timebase_from_spec(spec)
    scenes = remap_scenes(list(spec.get("scenes") or []), ranges, cf, timebase=tb)
    dur = min(duration, edited_duration(ranges, cf) or duration)
    labels: list[tuple[str, float]] = []
    first = float(scenes[0]["start"]) if scenes else dur
    if first > 0.25:
        labels.append(("hook", min(0.35, first * 0.4)))
        if first > 1.4:
            labels.append(("hook", first - 0.25))
    for scene in scenes:
        a, b = float(scene["start"]), float(scene["end"])
        mid = a + (b - a) * 0.28
        late = a + (b - a) * 0.82
        sid = scene.get("id") or scene.get("template") or "scene"
        labels.append((f"{sid}", mid))
        if late - mid > 0.4:
            labels.append((f"{sid}", late))
    last_end = float(scenes[-1]["end"]) if scenes else 0.0
    if dur - last_end > 0.3:
        labels.append(("close", min(dur - 0.12, last_end + (dur - last_end) * 0.6)))
    elif dur > 0.4:
        labels.append(("close", max(0.0, dur - 0.25)))
    # de-dupe nearly identical times
    out, seen = [], []
    for name, t in labels:
        t = min(max(0.0, t), max(0.0, dur - 0.05))
        if any(abs(t - s) < 0.08 for s in seen):
            continue
        out.append((name, t))
        seen.append(t)
    return out


def write_contact_sheet(spec: dict, video: Path, dest: Path, thumb_w: int = 270) -> Path:
    video = Path(video)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    duration = _probe_duration(video)
    picks = _pick_times(spec, duration)
    if not picks:
        picks = [("frame", 0.0)]

    thumb_h = int(thumb_w * H / W)
    cols = min(4, max(1, len(picks)))
    rows = (len(picks) + cols - 1) // cols
    gutter, label_h, title_h, pad = 14, 28, 48, 18
    cw = pad + cols * thumb_w + (cols - 1) * gutter + pad
    ch = title_h + pad + rows * (thumb_h + label_h) + (rows - 1) * gutter + pad
    canvas = Image.new("RGB", (cw, ch), (10, 11, 16))
    draw = ImageDraw.Draw(canvas)
    font_path = LIBERATION_BOLD or LIBERATION
    title_font = ImageFont.truetype(font_path, 20) if font_path else ImageFont.load_default()
    label_font = ImageFont.truetype(font_path, 14) if font_path else ImageFont.load_default()
    title = f"{video.name}  ·  {W}×{H}  ·  {duration:.2f}s"
    draw.text((pad, 14), title, fill=(220, 225, 235), font=title_font)

    with tempfile.TemporaryDirectory(prefix="geo_broll_contact_") as tmp:
        tmp = Path(tmp)
        for i, (name, t) in enumerate(picks):
            frame = tmp / f"f{i:02d}.jpg"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-hide_banner", "-v", "error",
                    "-i", str(video), "-ss", f"{t:.3f}",
                    "-frames:v", "1", "-q:v", "3", str(frame),
                ],
                check=True,
            )
            r, c = divmod(i, cols)
            x = pad + c * (thumb_w + gutter)
            y = title_h + pad + r * (thumb_h + label_h + gutter)
            im = Image.open(frame).convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            canvas.paste(im, (x, y))
            draw.rectangle([x, y, x + thumb_w - 1, y + thumb_h - 1], outline=(40, 44, 56))
            draw.text((x, y + thumb_h + 6), f"{name}  {t:.2f}s", fill=(170, 178, 190), font=label_font)

    canvas.save(dest, quality=92, optimize=True)
    return dest
