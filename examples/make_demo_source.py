#!/usr/bin/env python3
"""Generate a synthetic 9:16 talking-head stand-in for the example spec.

The clip is a stylized avatar on a dark backdrop — not a recording of a
person. It exists so `geo_broll.py run examples/example_scenes.json` works
without any private footage. 16 seconds, 1080×1920, 30 fps, with a quiet
synthetic tone as a stand-in for speaker audio.

Usage (from the repo root):

    python3 examples/make_demo_source.py
"""
from __future__ import annotations

import math
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

W, H, FPS, DURATION = 1080, 1920, 30, 16.0
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "demo_source.mp4"


def frame(t: float) -> Image.Image:
    im = Image.new("RGB", (W, H), (22, 24, 32))
    d = ImageDraw.Draw(im)
    # soft studio gradient
    for y in range(H):
        shade = int(18 + 16 * (y / H))
        d.line((0, y, W, y), fill=(shade, shade + 2, shade + 8))
    # backdrop panel
    d.rounded_rectangle((80, 220, W - 80, H - 80), 40, fill=(36, 40, 52))

    bob = 10 * math.sin(t * 2.1)
    talk = 0.5 + 0.5 * math.sin(t * 9.0)
    cx, cy = 540, 700 + bob

    # shoulders / shirt
    body = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(body)
    bd.rounded_rectangle((240, cy + 160, 840, H - 40), 80, fill=(30, 80, 150, 255))
    # collar
    bd.polygon(
        [(470, cy + 170), (540, cy + 230), (610, cy + 170)],
        fill=(18, 48, 96, 255),
    )
    im = Image.alpha_composite(im.convert("RGBA"), body).convert("RGB")
    d = ImageDraw.Draw(im)

    # head
    r = 196
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(214, 170, 124))
    # hair
    d.pieslice((cx - r - 8, cy - r - 18, cx + r + 8, cy + 40), 180, 0, fill=(46, 36, 32))
    d.ellipse((cx - r + 24, cy - r + 10, cx + r - 24, cy - 20), fill=(46, 36, 32))
    # ears
    d.ellipse((cx - r - 22, cy - 20, cx - r + 18, cy + 70), fill=(206, 160, 116))
    d.ellipse((cx + r - 18, cy - 20, cx + r + 22, cy + 70), fill=(206, 160, 116))
    # eyes
    ey = cy - 10
    for ex in (cx - 62, cx + 62):
        d.ellipse((ex - 22, ey - 14, ex + 22, ey + 16), fill=(250, 246, 240))
        d.ellipse((ex - 10, ey - 8, ex + 10, ey + 10), fill=(40, 32, 28))
        d.ellipse((ex - 4, ey - 6, ex + 2, ey), fill=(250, 250, 250))
    # brows
    d.arc((cx - 90, ey - 44, cx - 30, ey - 8), 200, 340, fill=(70, 50, 40), width=5)
    d.arc((cx + 30, ey - 44, cx + 90, ey - 8), 200, 340, fill=(70, 50, 40), width=5)
    # nose
    d.polygon(((cx, cy - 8), (cx - 10, cy + 28), (cx + 10, cy + 28)), fill=(198, 150, 108))
    # mouth — opens slightly so the stills feel like speech
    mw, mh = 46, 8 + int(10 * talk)
    d.rounded_rectangle((cx - mw, cy + 58, cx + mw, cy + 58 + mh), 8, fill=(140, 70, 70))

    return im.filter(ImageFilter.SMOOTH)


def main(dest: Path = OUT):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    n = int(DURATION * FPS)
    with tempfile.TemporaryDirectory(prefix="demo_src_") as tmp:
        tmp = Path(tmp)
        for i in range(n):
            t = i / FPS
            frame(t).save(tmp / f"f{i:05d}.png")
        # quiet 220 Hz tone as synthetic "speech" energy (not music)
        wav = tmp / "tone.wav"
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-v", "error",
                "-f", "lavfi",
                "-i", f"sine=frequency=220:sample_rate=48000:duration={DURATION},volume=-22dB",
                "-c:a", "pcm_s16le", str(wav),
            ],
            check=True,
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-v", "error",
                "-framerate", str(FPS),
                "-i", str(tmp / "f%05d.png"),
                "-i", str(wav),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "fast",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                "-t", str(DURATION),
                str(dest),
            ],
            check=True,
        )
    print(f"wrote {dest}  ({DURATION:.0f}s, {W}x{H}, {FPS} fps)")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    main(out)
