"""Render a scene (or a full spec) to 9:16 1080x1920 H.264 clips."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from style import W, H, FPS
from templates import render_frame, TEMPLATES

ROOT = Path(__file__).resolve().parent


def scene_duration(scene: dict, default: float = 4.0) -> float:
    if scene.get("duration"):
        return float(scene["duration"])
    if scene.get("start") is not None and scene.get("end") is not None:
        return max(0.5, float(scene["end"]) - float(scene["start"]))
    return default


def render_scene_mp4(scene: dict, dest: Path, fps: int = FPS, crf: int = 18) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dur = scene_duration(scene)
    nframes = max(1, int(round(dur * fps)))
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(crf),
        "-preset", "fast", "-an", "-movflags", "+faststart",
        str(dest),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(nframes):
            t = i / fps
            frame = render_frame(scene, t)
            if frame.size != (W, H):
                frame = frame.resize((W, H))
            if frame.mode != "RGB":
                frame = frame.convert("RGB")
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        rc = proc.wait()
    except Exception:
        proc.kill()
        raise
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed rendering {dest} (exit {rc})")
    return dest


def preview_frames(scene: dict, dest_dir: Path, times=None) -> list[Path]:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dur = scene_duration(scene)
    if times is None:
        times = [min(0.6, dur * 0.2), dur * 0.55, max(0, dur - 0.15)]
    sid = scene.get("id") or scene.get("template") or "scene"
    paths = []
    for t in times:
        t = min(max(0, t), max(0, dur - 0.001))
        im = render_frame(scene, t)
        p = dest_dir / f"{sid}_t{t:.2f}.jpg"
        im.convert("RGB").save(p, quality=92)
        paths.append(p)
    return paths
